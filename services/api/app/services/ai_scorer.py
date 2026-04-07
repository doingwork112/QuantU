"""
QuantifyU — AI Looksmaxxing 综合评分引擎

五维评分体系 (满分100):
  面部   40分  →  ViT-FBP美学 + MediaPipe对称性 + 黄金比例
  身材   25分  →  MediaPipe Pose (WHR/SHR) + BMI + 体态
  身高   15分  →  高斯分布评分 (非对称, 略高加分)
  生殖器官 10分  →  纯用户自测数值, 统计百分位映射
  皮肤头发 10分  →  CV图像质量分析

输出: {"total_score": 85.5, "breakdown": {...}, "percentile": "top 15%"}
"""

from __future__ import annotations

import math
from typing import Optional

import cv2
import numpy as np
from loguru import logger
from PIL import Image

from app.services.face_analyzer import (
    FaceBeautyModel,
    FaceLandmarkAnalyzer,
    FaceScoreResult,
    analyze_skin_quality,
    download_image,
)
from app.services.body_analyzer import BodyPoseAnalyzer, BodyScoreResult


# ================================================================
# 权重常量
# ================================================================
W_FACE = 40
W_BODY = 25
W_HEIGHT = 15
W_GENITAL = 10
W_SKIN_HAIR = 10

# 身高基准
HEIGHT_IDEAL = {"male": 183.0, "female": 168.0}
HEIGHT_SIGMA = 8.0

# 百分位表 (基于模拟正态分布)
PERCENTILE_TABLE = [
    (95, "top 5%"),
    (90, "top 10%"),
    (85, "top 15%"),
    (80, "top 20%"),
    (70, "top 30%"),
    (60, "top 40%"),
    (50, "top 50%"),
    (40, "top 60%"),
    (30, "top 70%"),
    (0, "top 100%"),
]


class LooksmaxxingEngine:
    """
    Looksmaxxing AI评分引擎 (单例)

    使用方式:
        engine = LooksmaxxingEngine(model_path="...", device="cpu")
        result = await engine.calculate(face_url="...", height_cm=178, ...)
    """

    MODEL_VERSION = "v2.0-vit-mediapipe"

    def __init__(
        self,
        vit_model_path: Optional[str] = None,
        device: str = "cpu",
    ):
        logger.info(
            f"LooksmaxxingEngine初始化 | "
            f"model={vit_model_path} | device={device}"
        )
        self._face_model = FaceBeautyModel(vit_model_path, device)
        self._face_landmarks = FaceLandmarkAnalyzer()
        self._body_analyzer = BodyPoseAnalyzer()
        self._device = device

    @property
    def is_model_loaded(self) -> bool:
        return self._face_model.is_loaded

    # ================================================================
    # 主入口
    # ================================================================
    async def calculate(
        self,
        face_photo_url: str,
        height_cm: float,
        gender: str = "male",
        ethnicity: Optional[str] = None,
        body_photo_url: Optional[str] = None,
        body_side_photo_url: Optional[str] = None,
        weight_kg: Optional[float] = None,
        # 生殖器官自测 (不做AI评分)
        penis_length_cm: Optional[float] = None,
        penis_girth_cm: Optional[float] = None,
        breast_cup: Optional[str] = None,
        grooming_level: Optional[int] = None,
        self_rating: Optional[int] = None,
    ) -> dict:
        """
        计算完整五维评分

        Returns: {
            "total_score": 85.5,
            "breakdown": { ... },
            "percentile": "top 15%",
            "face": { ... },
            "body": { ... },
            "height": { ... },
            "genital": { ... },
            "skin_hair": { ... },
            "improvement_tips": [...],
            "east_asian_notes": [...],
            "model_version": "v2.0-vit-mediapipe"
        }
        """
        is_east_asian = self._detect_east_asian(ethnicity)

        # ---- 1. 下载图片 ----
        face_bgr = await self._safe_download(face_photo_url, "face")

        body_front_bgr = None
        if body_photo_url:
            body_front_bgr = await self._safe_download(body_photo_url, "body_front")

        body_side_bgr = None
        if body_side_photo_url:
            body_side_bgr = await self._safe_download(
                body_side_photo_url, "body_side"
            )

        # ---- 2. 面部评分 /40 ----
        face_result = await self._score_face(face_bgr, is_east_asian)
        face_weighted = round(face_result.final_score / 10 * W_FACE, 1)

        # ---- 3. 身材评分 /25 ----
        body_result = self._score_body(
            body_front_bgr, body_side_bgr, height_cm, weight_kg, gender
        )
        body_weighted = round(body_result.final_score / 10 * W_BODY, 1)

        # ---- 4. 身高评分 /15 ----
        height_score, height_feedback = self._score_height(height_cm, gender)

        # ---- 5. 皮肤/头发评分 /10 ----
        skin_score, skin_feedback = self._score_skin_hair(face_bgr)
        skin_weighted = round(skin_score / 10 * W_SKIN_HAIR, 1)

        # ---- 6. 生殖器官评分 /10 (纯数值, 非AI) ----
        genital_score, genital_feedback = self._score_genital(
            gender=gender,
            penis_length_cm=penis_length_cm,
            penis_girth_cm=penis_girth_cm,
            breast_cup=breast_cup,
            grooming_level=grooming_level,
            self_rating=self_rating,
        )

        # ---- 7. 汇总 ----
        total = round(
            face_weighted + body_weighted + height_score
            + skin_weighted + genital_score,
            1,
        )
        total = max(0, min(100, total))
        percentile = self._score_to_percentile(total)

        # ---- 8. 东亚脸专项建议 ----
        east_asian_notes = []
        if is_east_asian:
            east_asian_notes = self._east_asian_tips(face_result, body_result)

        # ---- 9. 改善建议 ----
        tips = self._improvement_tips(
            face_weighted, body_weighted, height_score,
            skin_weighted, genital_score, face_result, body_result,
        )

        result = {
            # 顶层汇总
            "total_score": total,
            "percentile": percentile,
            "score_label": self.score_to_label(total),
            "model_version": self.MODEL_VERSION,
            # 加权后分数 (用于写入DB)
            "face_score": face_weighted,
            "body_score": body_weighted,
            "height_score": height_score,
            "skin_hair_score": skin_weighted,
            "genital_score": genital_score,
            "overall_score": total,
            # 详细breakdown
            "breakdown": {
                "face": {
                    "weighted_score": face_weighted,
                    "max": W_FACE,
                    "raw_0_10": face_result.final_score,
                    "aesthetic": round(face_result.aesthetic_raw * 10, 1),
                    "symmetry": face_result.symmetry_score,
                    "golden_ratio": face_result.golden_ratio_score,
                    "detail": face_result.detail,
                },
                "body": {
                    "weighted_score": body_weighted,
                    "max": W_BODY,
                    "raw_0_10": body_result.final_score,
                    "proportions": body_result.proportions_score,
                    "bmi": body_result.bmi_score,
                    "posture": body_result.posture_score,
                    "metrics": {
                        "shr": round(body_result.metrics.shr, 2) if body_result.metrics.shr else None,
                        "whr": round(body_result.metrics.whr, 2) if body_result.metrics.whr else None,
                        "leg_body_ratio": (
                            round(body_result.metrics.leg_body_ratio, 3)
                            if body_result.metrics.leg_body_ratio
                            else None
                        ),
                        "bmi": body_result.metrics.bmi,
                    },
                    "detail": body_result.detail,
                },
                "height": {
                    "weighted_score": height_score,
                    "max": W_HEIGHT,
                    "height_cm": height_cm,
                },
                "skin_hair": {
                    "weighted_score": skin_weighted,
                    "max": W_SKIN_HAIR,
                    "raw_0_10": skin_score,
                },
                "genital": {
                    "weighted_score": genital_score,
                    "max": W_GENITAL,
                    "note": "基于用户自测数值，非AI视觉评分",
                },
            },
            # 反馈
            "face_feedback": face_result.feedback,
            "body_feedback": body_result.feedback,
            "height_feedback": height_feedback,
            "skin_hair_feedback": skin_feedback,
            "genital_feedback": genital_feedback,
            "improvement_tips": tips,
            "east_asian_notes": east_asian_notes,
            "scoring_model_version": self.MODEL_VERSION,
        }

        logger.info(
            f"评分完成 | total={total}/100 | percentile={percentile} | "
            f"face={face_weighted}/{W_FACE} body={body_weighted}/{W_BODY} "
            f"height={height_score}/{W_HEIGHT} skin={skin_weighted}/{W_SKIN_HAIR} "
            f"genital={genital_score}/{W_GENITAL}"
        )

        return result

    # ================================================================
    # 面部评分
    # ================================================================
    async def _score_face(
        self, face_bgr: Optional[np.ndarray], is_east_asian: bool
    ) -> FaceScoreResult:
        """
        面部综合评分 0-10
        = 美学50% + 对称性25% + 黄金比例25%
        """
        result = FaceScoreResult()

        if face_bgr is None:
            result.final_score = 5.0
            result.feedback = "无法加载面部照片，使用默认中位分"
            return result

        # 1. ViT-FBP 美学分
        try:
            pil_img = Image.fromarray(cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB))
            result.aesthetic_raw = self._face_model.predict(pil_img)
        except Exception as e:
            logger.error(f"ViT-FBP推理失败: {e}")
            result.aesthetic_raw = 0.5

        aesthetic_10 = round(result.aesthetic_raw * 10, 1)

        # 2. 对称性
        landmarks = self._face_landmarks.extract_landmarks(face_bgr)
        if landmarks:
            result.symmetry_score = self._face_landmarks.calculate_symmetry(
                face_bgr, landmarks
            )
            result.golden_ratio_score, ratio_detail = (
                self._face_landmarks.calculate_golden_ratio(landmarks, is_east_asian)
            )
            result.detail["golden_ratios"] = ratio_detail
        else:
            result.symmetry_score = 6.5
            result.golden_ratio_score = 6.5
            result.detail["note"] = "未检测到面部关键点，对称性和比例使用估算值"

        # 3. 东亚脸修正
        if is_east_asian:
            adj = self._apply_east_asian_face_correction(result)
            result.east_asian_adjustments = adj

        # 4. 加权最终分
        result.final_score = round(
            aesthetic_10 * 0.50
            + result.symmetry_score * 0.25
            + result.golden_ratio_score * 0.25,
            1,
        )
        result.final_score = max(1.0, min(10.0, result.final_score))

        # 5. 反馈
        result.feedback = self._face_feedback(result)

        return result

    def _apply_east_asian_face_correction(
        self, result: FaceScoreResult
    ) -> dict:
        """
        东亚脸校正

        ViT-FBP 在 SCUT-FBP5500 数据集上训练时包含亚洲面孔,
        但欧美审美标准仍有偏置. 校正:
        - 宽面型不扣分 (已在golden_ratio中通过EAST_ASIAN_CORRECTIONS处理)
        - 单眼皮/内双不作为负面因子 → 美学分+0.3补偿
        - 低鼻梁不额外惩罚 → 已在黄金比例中降低鼻梁权重
        """
        adjustments = {}

        # 美学分东亚补偿 (消除训练数据集的欧美偏置)
        aesthetic_boost = 0.3
        result.aesthetic_raw = min(1.0, result.aesthetic_raw + aesthetic_boost / 10)
        adjustments["aesthetic_boost"] = aesthetic_boost
        adjustments["reason"] = "补偿ViT-FBP训练数据集的西方审美偏置"

        return adjustments

    @staticmethod
    def _face_feedback(result: FaceScoreResult) -> str:
        s = result.final_score
        parts = []

        if result.aesthetic_raw >= 0.8:
            parts.append("面部美学评分优秀，五官立体协调")
        elif result.aesthetic_raw >= 0.6:
            parts.append("面部美学良好")
        else:
            parts.append("面部美学有提升空间")

        if result.symmetry_score >= 8:
            parts.append("对称性极佳")
        elif result.symmetry_score < 6:
            parts.append("建议关注面部对称性（咀嚼习惯、睡姿可能影响）")

        if result.golden_ratio_score >= 8:
            parts.append("五官比例接近黄金比例")
        elif result.golden_ratio_score < 6:
            parts.append("五官比例可通过发型和眉形微调优化视觉效果")

        return "；".join(parts)

    # ================================================================
    # 身材评分
    # ================================================================
    def _score_body(
        self,
        front_bgr: Optional[np.ndarray],
        side_bgr: Optional[np.ndarray],
        height_cm: float,
        weight_kg: Optional[float],
        gender: str,
    ) -> BodyScoreResult:
        """身材评分 0-10"""
        if front_bgr is not None:
            return self._body_analyzer.analyze(
                front_image=front_bgr,
                side_image=side_bgr,
                height_cm=height_cm,
                weight_kg=weight_kg,
                gender=gender,
            )

        # 无身材照片 → BMI回退
        result = BodyScoreResult()
        if weight_kg and height_cm:
            bmi = weight_kg / ((height_cm / 100) ** 2)
            result.metrics.bmi = round(bmi, 1)

            if 18.5 <= bmi <= 24.9:
                result.final_score = 7.0 + (1 - abs(bmi - 22) / 3) * 2
            elif 16 <= bmi < 18.5 or 25 <= bmi <= 30:
                result.final_score = 5.0
            else:
                result.final_score = 3.0

            result.final_score = round(min(10, max(1, result.final_score)), 1)
            result.bmi_score = result.final_score
            result.feedback = (
                f"BMI={bmi:.1f}，仅基于BMI评估。"
                f"上传全身站立照（正面+侧面）可获得WHR/SHR体态完整分析"
            )
        else:
            result.final_score = 5.0
            result.feedback = "缺少身材数据，建议补充照片和体重获得准确评分"

        return result

    # ================================================================
    # 身高评分
    # ================================================================
    def _score_height(
        self, height_cm: float, gender: str
    ) -> tuple[float, str]:
        """
        身高评分 /15
        非对称高斯: 略高于理想值的惩罚更小
        """
        ideal = HEIGHT_IDEAL.get(gender, 178)
        z = (height_cm - ideal) / HEIGHT_SIGMA

        if height_cm > ideal:
            z *= 0.6  # 高于理想值惩罚减40%

        raw = math.exp(-0.5 * z * z)
        score = round(raw * W_HEIGHT, 1)

        if abs(height_cm - ideal) <= 3:
            feedback = f"身高{height_cm}cm，处于理想范围 ({ideal-3}~{ideal+5}cm)"
        elif height_cm > ideal:
            feedback = f"身高{height_cm}cm，高于理想值{ideal}cm，具有显著优势"
        elif height_cm > ideal - 10:
            feedback = f"身高{height_cm}cm，可通过增高鞋垫(+3~5cm)和直立体态优化视觉身高"
        else:
            feedback = f"身高{height_cm}cm，建议强化上半身训练，配合垂直条纹穿搭拉长视觉比例"

        return score, feedback

    # ================================================================
    # 皮肤/头发
    # ================================================================
    def _score_skin_hair(
        self, face_bgr: Optional[np.ndarray]
    ) -> tuple[float, str]:
        """皮肤质量评分 0-10"""
        if face_bgr is None:
            return 5.0, "无法分析皮肤状态"
        return analyze_skin_quality(face_bgr)

    # ================================================================
    # 生殖器官 (纯数值, 不做AI)
    # ================================================================
    def _score_genital(
        self,
        gender: str,
        penis_length_cm: Optional[float] = None,
        penis_girth_cm: Optional[float] = None,
        breast_cup: Optional[str] = None,
        grooming_level: Optional[int] = None,
        self_rating: Optional[int] = None,
    ) -> tuple[float, str]:
        """
        生殖器官评分 /10
        纯用户自测数值 → 统计百分位映射
        不接受照片, 不做AI视觉评分
        """
        sub_scores: list[tuple[float, float]] = []  # (score, weight)

        if gender == "male":
            # 阴茎长度 — 全球勃起均值13.1cm (BJU International 2015 meta)
            if penis_length_cm is not None:
                z = (penis_length_cm - 13.1) / 2.5
                sub_scores.append((self._sigmoid(z), 0.35))

            # 阴茎周长 — 勃起均值11.7cm
            if penis_girth_cm is not None:
                z = (penis_girth_cm - 11.7) / 1.5
                sub_scores.append((self._sigmoid(z), 0.35))

        elif gender == "female":
            if breast_cup:
                # 审美偏好分布 (非线性, C-D峰值)
                cup_map = {
                    "AA": 0.35, "A": 0.50, "B": 0.65, "C": 0.80,
                    "D": 0.85, "DD": 0.75, "DDD": 0.65, "E": 0.55,
                    "F": 0.45, "G": 0.35, "H": 0.30,
                }
                sub_scores.append((cup_map.get(breast_cup, 0.5), 0.50))

        # 通用: 修饰程度
        if grooming_level is not None:
            sub_scores.append((grooming_level / 5.0, 0.20))

        # 自评 (权重低, 防止inflation)
        if self_rating is not None:
            sub_scores.append((self_rating / 10.0, 0.10))

        if not sub_scores:
            return 5.0, "未提供自测数据，使用默认中位分 (5.0/10)"

        # 加权平均
        total_w = sum(w for _, w in sub_scores)
        raw = sum(s * w for s, w in sub_scores) / total_w
        score = round(raw * W_GENITAL, 1)
        score = max(0, min(float(W_GENITAL), score))

        if score >= 8:
            feedback = "该维度评分优秀"
        elif score >= 6:
            feedback = "该维度评分良好，处于中上水平"
        elif score >= 4:
            feedback = "该维度评分中等，自信心态比数值更重要"
        else:
            feedback = "该维度评分偏低，但记住：整体吸引力远不止单一维度"

        return score, feedback

    # ================================================================
    # 百分位 & 标签
    # ================================================================
    @staticmethod
    def _score_to_percentile(total: float) -> str:
        for threshold, label in PERCENTILE_TABLE:
            if total >= threshold:
                return label
        return "top 100%"

    @staticmethod
    def score_to_label(score: float) -> str:
        if score >= 85:
            return "卓越"
        if score >= 70:
            return "优秀"
        if score >= 55:
            return "良好"
        if score >= 40:
            return "中等"
        return "待提升"

    # ================================================================
    # 东亚脸优化建议
    # ================================================================
    @staticmethod
    def _east_asian_tips(
        face: FaceScoreResult, body: BodyScoreResult
    ) -> list[str]:
        """针对东亚面孔的专项Looksmaxxing建议"""
        tips = []

        if face.symmetry_score < 7:
            tips.append(
                "东亚脸型: 面部略宽属正常特征，不影响对称性评分。"
                "可通过修眉和鬓角造型优化面部轮廓线条"
            )

        if face.aesthetic_raw < 0.6:
            tips.append(
                "东亚面部提升: 重点关注眉眼区域——"
                "自然双眼皮贴/正确修眉可显著提升五官立体感，"
                "无需追求高鼻梁的西方标准"
            )

        tips.append(
            "东亚肤质优势: 东亚皮肤衰老速度通常较慢，"
            "坚持防晒(SPF50+)可长期保持皮肤年轻状态"
        )

        if body.metrics.bmi and body.metrics.bmi < 20:
            tips.append(
                "东亚体型: 东亚人群BMI偏低较常见，"
                "可通过渐进式力量训练(每周3-4次)增加肌肉量，"
                "优化肩宽和上身线条"
            )

        return tips

    # ================================================================
    # 改善建议
    # ================================================================
    @staticmethod
    def _improvement_tips(
        face_w: float, body_w: float, height_s: float,
        skin_w: float, genital_s: float,
        face_r: FaceScoreResult, body_r: BodyScoreResult,
    ) -> list[str]:
        """根据各维度分数差距生成优先级排序的改善建议"""
        gaps = [
            ("face", face_w / W_FACE, W_FACE),
            ("body", body_w / W_BODY, W_BODY),
            ("height", height_s / W_HEIGHT, W_HEIGHT),
            ("skin", skin_w / W_SKIN_HAIR, W_SKIN_HAIR),
        ]
        # 按 (1-ratio)*weight 排序 → 提升空间最大的优先
        gaps.sort(key=lambda x: (1 - x[1]) * x[2], reverse=True)

        tips = []
        for name, ratio, weight in gaps:
            if ratio >= 0.8:
                continue
            if name == "face":
                tips.append(
                    f"[面部 {round(ratio*100)}%] "
                    f"护肤 + 眉形设计 + 发型调整是ROI最高的提升方向"
                )
            elif name == "body":
                if body_r.metrics.bmi and body_r.metrics.bmi > 25:
                    tips.append(
                        f"[身材 {round(ratio*100)}%] "
                        f"优先减脂: 每周4次有氧 + 热量缺口300kcal/天"
                    )
                else:
                    tips.append(
                        f"[身材 {round(ratio*100)}%] "
                        f"增肌塑形: 复合动作为主(深蹲/硬拉/卧推)，每周4次"
                    )
            elif name == "height":
                tips.append(
                    f"[身高 {round(ratio*100)}%] "
                    f"内增高鞋垫(+3-5cm) + 直立体态 + 垂直条纹穿搭"
                )
            elif name == "skin":
                tips.append(
                    f"[皮肤 {round(ratio*100)}%] "
                    f"基础三步: 氨基酸洁面→烟酰胺精华→SPF50防晒"
                )

        if not tips:
            tips.append("各项评分均衡优秀，保持当前状态即可！")

        return tips[:5]  # 最多5条建议

    # ================================================================
    # 工具函数
    # ================================================================
    @staticmethod
    def _sigmoid(x: float) -> float:
        return 1.0 / (1.0 + math.exp(-x))

    @staticmethod
    def _detect_east_asian(ethnicity: Optional[str]) -> bool:
        if not ethnicity:
            return False
        ea_keywords = {
            "chinese", "japanese", "korean", "east asian", "asian",
            "中国", "日本", "韩国", "东亚", "亚洲", "华人", "汉族",
        }
        return ethnicity.lower().strip() in ea_keywords

    @staticmethod
    async def _safe_download(url: str, label: str) -> Optional[np.ndarray]:
        """安全下载图片，失败时返回None而非抛异常"""
        try:
            return await download_image(url)
        except Exception as e:
            logger.error(f"下载{label}图片失败 | url={url[:60]} | error={e}")
            return None

    def close(self):
        self._face_landmarks.close()
        self._body_analyzer.close()
