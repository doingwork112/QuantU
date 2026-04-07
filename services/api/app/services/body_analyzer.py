"""
QuantifyU — 身材分析引擎
MediaPipe Pose 关键点 → WHR/SHR/BMI → 0-10分

输入: 正面照 + 侧面照 (侧面可选)
方法:
  1. MediaPipe Pose 提取33个身体关键点
  2. 从关键点估算:
     - WHR (Waist-to-Hip Ratio): 腰臀比
     - SHR (Shoulder-to-Hip Ratio): 肩臀比
     - 腿身比 (下肢长度/总身高)
     - 体态评估 (头部前倾、圆肩检测)
  3. 结合 BMI 和视觉指标加权出 0-10 分
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np
from loguru import logger

try:
    import mediapipe as mp

    _MP_AVAILABLE = True
except ImportError:
    _MP_AVAILABLE = False


# ================================================================
# 数据结构
# ================================================================
@dataclass
class BodyMetrics:
    """从照片中估算的身体指标"""

    # 原始关键点度量 (像素比例)
    shoulder_width_px: float = 0
    hip_width_px: float = 0
    waist_width_px: float = 0  # 估算
    torso_length_px: float = 0
    leg_length_px: float = 0
    total_height_px: float = 0

    # 计算比例
    shr: float = 0         # Shoulder-to-Hip Ratio
    whr: float = 0         # Waist-to-Hip Ratio (估算)
    leg_body_ratio: float = 0  # 腿身比
    bmi: Optional[float] = None

    # 体态
    head_forward_angle: float = 0  # 头部前倾角度
    shoulder_slope: float = 0      # 肩部斜度 (高低肩)
    posture_score: float = 0       # 体态评分 0-10

    # 置信度
    pose_confidence: float = 0


@dataclass
class BodyScoreResult:
    """身材评分结果"""

    proportions_score: float = 0    # 身材比例 0-10
    bmi_score: float = 0            # BMI健康度 0-10
    posture_score: float = 0        # 体态 0-10
    final_score: float = 0          # 加权最终分 0-10
    metrics: BodyMetrics = field(default_factory=BodyMetrics)
    feedback: str = ""
    detail: dict = field(default_factory=dict)


# ================================================================
# 理想比例常量 (基于人体测量学研究)
# ================================================================
IDEAL_METRICS = {
    "male": {
        "shr": (1.40, 1.60),     # 男性理想肩臀比 (V-taper)
        "whr": (0.80, 0.95),     # 男性健康腰臀比
        "leg_ratio": (0.45, 0.52),  # 腿身比
        "bmi_optimal": (21.0, 25.0),
    },
    "female": {
        "shr": (1.15, 1.35),     # 女性理想肩臀比
        "whr": (0.65, 0.80),     # 女性健康腰臀比 (WHO标准)
        "leg_ratio": (0.45, 0.53),
        "bmi_optimal": (18.5, 23.5),
    },
}


# ================================================================
# MediaPipe Pose 分析器
# ================================================================
class BodyPoseAnalyzer:
    """
    使用 MediaPipe Pose 从照片中提取身体比例和体态指标

    MediaPipe Pose 关键点索引:
      0: nose, 11: left_shoulder, 12: right_shoulder
      23: left_hip, 24: right_hip, 25: left_knee, 26: right_knee
      27: left_ankle, 28: right_ankle, 31: left_foot, 32: right_foot
    """

    def __init__(self):
        self._pose = None
        if _MP_AVAILABLE:
            self._pose = mp.solutions.pose.Pose(
                static_image_mode=True,
                model_complexity=2,  # 最高精度
                min_detection_confidence=0.5,
            )

    def analyze(
        self,
        front_image: np.ndarray,
        side_image: Optional[np.ndarray] = None,
        height_cm: Optional[float] = None,
        weight_kg: Optional[float] = None,
        gender: str = "male",
    ) -> BodyScoreResult:
        """
        分析身材照片

        Args:
            front_image: 正面照 (BGR)
            side_image: 侧面照 (BGR, 可选)
            height_cm: 身高
            weight_kg: 体重
            gender: male | female
        """
        result = BodyScoreResult()

        # ---- 1. 提取正面关键点 ----
        front_metrics = self._extract_pose_metrics(front_image)
        if front_metrics is None:
            logger.warning("正面照未检测到身体姿态，使用BMI回退评分")
            return self._bmi_only_score(height_cm, weight_kg, gender)

        result.metrics = front_metrics

        # ---- 2. 侧面体态分析 (如有) ----
        if side_image is not None:
            posture = self._analyze_side_posture(side_image)
            if posture:
                result.metrics.head_forward_angle = posture["head_forward"]
                result.metrics.posture_score = posture["score"]

        # ---- 3. BMI ----
        if height_cm and weight_kg:
            result.metrics.bmi = round(
                weight_kg / ((height_cm / 100) ** 2), 1
            )

        # ---- 4. 综合评分 ----
        ideals = IDEAL_METRICS.get(gender, IDEAL_METRICS["male"])

        # 4a. 身材比例分 (SHR + WHR + 腿身比)
        proportion_scores = []

        if front_metrics.shr > 0:
            shr_score = self._range_score(
                front_metrics.shr, ideals["shr"][0], ideals["shr"][1]
            )
            proportion_scores.append(shr_score)
            result.detail["shr"] = {
                "value": round(front_metrics.shr, 2),
                "ideal_range": list(ideals["shr"]),
                "score": shr_score,
            }

        if front_metrics.whr > 0:
            whr_score = self._range_score(
                front_metrics.whr, ideals["whr"][0], ideals["whr"][1]
            )
            proportion_scores.append(whr_score)
            result.detail["whr"] = {
                "value": round(front_metrics.whr, 2),
                "ideal_range": list(ideals["whr"]),
                "score": whr_score,
            }

        if front_metrics.leg_body_ratio > 0:
            leg_score = self._range_score(
                front_metrics.leg_body_ratio,
                ideals["leg_ratio"][0],
                ideals["leg_ratio"][1],
            )
            proportion_scores.append(leg_score)
            result.detail["leg_body_ratio"] = {
                "value": round(front_metrics.leg_body_ratio, 3),
                "ideal_range": list(ideals["leg_ratio"]),
                "score": leg_score,
            }

        result.proportions_score = round(
            sum(proportion_scores) / max(len(proportion_scores), 1), 1
        )

        # 4b. BMI分
        if result.metrics.bmi:
            result.bmi_score = round(
                self._range_score(
                    result.metrics.bmi,
                    ideals["bmi_optimal"][0],
                    ideals["bmi_optimal"][1],
                ),
                1,
            )
        else:
            result.bmi_score = 6.0  # 无BMI数据，给中等分

        # 4c. 体态分
        if result.metrics.posture_score > 0:
            result.posture_score = result.metrics.posture_score
        else:
            result.posture_score = 7.0  # 无侧面照默认

        # 4d. 加权
        #   比例 50% + BMI 30% + 体态 20%
        result.final_score = round(
            result.proportions_score * 0.50
            + result.bmi_score * 0.30
            + result.posture_score * 0.20,
            1,
        )
        result.final_score = max(1.0, min(10.0, result.final_score))

        # ---- 5. 生成反馈 ----
        result.feedback = self._generate_feedback(result, gender)

        return result

    def _extract_pose_metrics(
        self, image_bgr: np.ndarray
    ) -> Optional[BodyMetrics]:
        """从正面照提取身体关键点度量"""
        if not self._pose:
            return None

        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        results = self._pose.process(rgb)

        if not results.pose_landmarks:
            return None

        lm = results.pose_landmarks.landmark
        h, w = image_bgr.shape[:2]

        def px(idx: int) -> tuple[float, float]:
            return (lm[idx].x * w, lm[idx].y * h)

        def vis(idx: int) -> float:
            return lm[idx].visibility

        metrics = BodyMetrics()

        # 置信度: 关键点平均可见性
        key_indices = [11, 12, 23, 24, 25, 26, 27, 28]
        metrics.pose_confidence = sum(vis(i) for i in key_indices) / len(key_indices)

        if metrics.pose_confidence < 0.3:
            logger.warning(f"姿态检测置信度过低: {metrics.pose_confidence:.2f}")
            return None

        # 关键点
        l_shoulder = px(11)
        r_shoulder = px(12)
        l_hip = px(23)
        r_hip = px(24)
        l_knee = px(25)
        r_knee = px(26)
        l_ankle = px(27)
        r_ankle = px(28)
        nose = px(0)

        # ---- 度量 ----
        metrics.shoulder_width_px = self._dist(l_shoulder, r_shoulder)
        metrics.hip_width_px = self._dist(l_hip, r_hip)

        # 腰宽估算 (取肩-臀中点处的宽度，按比例缩小)
        # 实际为肩宽和臀宽的加权平均 (偏臀部)
        metrics.waist_width_px = (
            metrics.shoulder_width_px * 0.35 + metrics.hip_width_px * 0.65
        )

        # 躯干长度 (肩中点到臀中点)
        shoulder_mid = self._midpt(l_shoulder, r_shoulder)
        hip_mid = self._midpt(l_hip, r_hip)
        metrics.torso_length_px = self._dist(shoulder_mid, hip_mid)

        # 腿长 (臀中点到踝中点)
        ankle_mid = self._midpt(l_ankle, r_ankle)
        metrics.leg_length_px = self._dist(hip_mid, ankle_mid)

        # 总高度 (头顶估算到脚)
        # 头顶 ≈ 鼻子Y - 额头高度估算
        head_top_y = nose[1] - (shoulder_mid[1] - nose[1]) * 0.6
        metrics.total_height_px = ankle_mid[1] - head_top_y

        # ---- 比例计算 ----
        if metrics.hip_width_px > 0:
            metrics.shr = metrics.shoulder_width_px / metrics.hip_width_px
            metrics.whr = metrics.waist_width_px / metrics.hip_width_px

        if metrics.total_height_px > 0:
            metrics.leg_body_ratio = (
                metrics.leg_length_px / metrics.total_height_px
            )

        # ---- 肩部高低 ----
        metrics.shoulder_slope = abs(l_shoulder[1] - r_shoulder[1]) / max(
            metrics.shoulder_width_px, 1
        )

        return metrics

    def _analyze_side_posture(self, side_bgr: np.ndarray) -> Optional[dict]:
        """从侧面照分析体态 (头部前倾、驼背)"""
        if not self._pose:
            return None

        rgb = cv2.cvtColor(side_bgr, cv2.COLOR_BGR2RGB)
        results = self._pose.process(rgb)

        if not results.pose_landmarks:
            return None

        lm = results.pose_landmarks.landmark
        h, w = side_bgr.shape[:2]

        # 侧面: 用X坐标判断前倾
        ear = lm[7]      # 左耳 (侧面朝左时)
        shoulder = lm[11]  # 左肩

        # 头部前倾角 (耳朵相对于肩膀的前移量)
        head_forward_px = (ear.x - shoulder.x) * w
        shoulder_to_hip = abs(lm[11].y - lm[23].y) * h
        head_forward_angle = math.degrees(
            math.atan2(abs(head_forward_px), max(shoulder_to_hip, 1))
        )

        # 评分: 0°=完美, 15°+=较差
        posture = max(0, 10 - head_forward_angle * 0.5)

        return {
            "head_forward": round(head_forward_angle, 1),
            "score": round(min(10.0, posture), 1),
        }

    def _bmi_only_score(
        self,
        height_cm: Optional[float],
        weight_kg: Optional[float],
        gender: str,
    ) -> BodyScoreResult:
        """无法检测姿态时，仅用BMI评分"""
        result = BodyScoreResult()

        if height_cm and weight_kg:
            bmi = weight_kg / ((height_cm / 100) ** 2)
            result.metrics.bmi = round(bmi, 1)
            ideals = IDEAL_METRICS.get(gender, IDEAL_METRICS["male"])
            result.bmi_score = round(
                self._range_score(bmi, ideals["bmi_optimal"][0], ideals["bmi_optimal"][1]),
                1,
            )
            result.final_score = result.bmi_score
            result.feedback = (
                f"BMI={bmi:.1f}，仅基于BMI评分（未检测到身体姿态）。"
                f"建议上传全身站立正面照以获得完整评估。"
            )
        else:
            result.final_score = 5.0
            result.feedback = "缺少身材照片和体重数据，无法准确评分"

        return result

    @staticmethod
    def _range_score(value: float, low: float, high: float) -> float:
        """
        范围内评分:
        在理想范围内 → 8-10分
        偏离范围 → 按距离衰减
        """
        if low <= value <= high:
            # 在范围内: 越接近中心越高分
            mid = (low + high) / 2
            half_range = (high - low) / 2
            closeness = 1 - abs(value - mid) / half_range if half_range > 0 else 1
            return 8.0 + closeness * 2.0  # 8-10

        # 在范围外: 按距离衰减
        if value < low:
            distance = (low - value) / low
        else:
            distance = (value - high) / high

        return max(1.0, 8.0 - distance * 15)

    @staticmethod
    def _dist(p1: tuple[float, float], p2: tuple[float, float]) -> float:
        return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)

    @staticmethod
    def _midpt(
        p1: tuple[float, float], p2: tuple[float, float]
    ) -> tuple[float, float]:
        return ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)

    def _generate_feedback(self, result: BodyScoreResult, gender: str) -> str:
        """生成身材改善建议"""
        parts = []
        m = result.metrics
        ideals = IDEAL_METRICS.get(gender, IDEAL_METRICS["male"])

        if m.bmi:
            if m.bmi < ideals["bmi_optimal"][0]:
                parts.append(f"BMI={m.bmi}偏低，建议增加蛋白质摄入和力量训练增重")
            elif m.bmi > ideals["bmi_optimal"][1]:
                parts.append(f"BMI={m.bmi}偏高，建议结合有氧和控制饮食减脂")
            else:
                parts.append(f"BMI={m.bmi}在理想范围内")

        if m.shr > 0:
            if gender == "male" and m.shr < ideals["shr"][0]:
                parts.append(
                    f"肩臀比{m.shr:.2f}偏低，建议强化三角肌和背阔肌（哑铃侧平举、引体向上）"
                )
            elif gender == "female" and m.shr > ideals["shr"][1]:
                parts.append(
                    f"肩臀比{m.shr:.2f}，建议通过臀腿训练（臀推、深蹲）优化上下身比例"
                )

        if m.whr > 0 and m.whr > ideals["whr"][1]:
            parts.append(
                f"腰臀比{m.whr:.2f}偏高，核心训练（平板支撑、真空腹）有助于收紧腰线"
            )

        if m.posture_score > 0 and m.posture_score < 6:
            parts.append("体态需改善: 建议做颈部回缩、靠墙站立练习纠正头部前倾")

        if not parts:
            parts.append("身材各项指标均衡，保持当前训练和饮食习惯")

        return "；".join(parts)

    def close(self):
        if self._pose:
            self._pose.close()
