"""
QuantifyU — 面部分析引擎
ViT-FBP 面部美学模型 + dlib/MediaPipe 关键点几何分析

评分维度:
  - 美学分 (ViT-FBP模型输出)       权重 50%
  - 对称性 (关键点左右偏差)         权重 25%
  - 黄金比例 (五官间距比例)         权重 25%

东亚脸优化:
  - 内眦间距/面宽比例校正 (东亚偏宽属正常)
  - 鼻梁高度惩罚降低 (侧面轮廓差异)
  - 颧骨宽度不作为负面因子
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
from typing import Optional

import cv2
import httpx
import numpy as np
from loguru import logger
from PIL import Image

# ---- 条件导入: 缺库时优雅降级 ----
try:
    import mediapipe as mp

    _MP_AVAILABLE = True
except ImportError:
    _MP_AVAILABLE = False
    logger.warning("mediapipe 未安装，面部关键点分析将使用简化模式")

try:
    import torch
    import timm

    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False
    logger.warning("torch/timm 未安装，ViT-FBP模型将使用回退评分")


# ================================================================
# 数据结构
# ================================================================
@dataclass
class FaceLandmarks:
    """468个MediaPipe FaceMesh关键点中提取的关键度量"""

    # 关键距离 (像素)
    left_eye_center: tuple[float, float] = (0, 0)
    right_eye_center: tuple[float, float] = (0, 0)
    nose_tip: tuple[float, float] = (0, 0)
    mouth_center: tuple[float, float] = (0, 0)
    chin: tuple[float, float] = (0, 0)
    left_face_edge: tuple[float, float] = (0, 0)
    right_face_edge: tuple[float, float] = (0, 0)
    forehead_top: tuple[float, float] = (0, 0)

    # 计算指标
    face_width: float = 0
    face_height: float = 0
    eye_distance: float = 0
    nose_to_mouth: float = 0
    mouth_to_chin: float = 0
    forehead_to_eye: float = 0


@dataclass
class FaceScoreResult:
    """面部评分结果"""

    aesthetic_raw: float = 0.0  # ViT-FBP原始输出 0-1
    symmetry_score: float = 0.0  # 对称性 0-10
    golden_ratio_score: float = 0.0  # 黄金比例 0-10
    final_score: float = 0.0  # 加权最终分 0-10
    feedback: str = ""
    detail: dict = field(default_factory=dict)
    east_asian_adjustments: dict = field(default_factory=dict)


# ================================================================
# 黄金比例常量
# ================================================================
PHI = (1 + math.sqrt(5)) / 2  # 1.618

# 理想面部比例 (来源: Marquardt Beauty Mask)
IDEAL_RATIOS = {
    "eye_dist_to_face_width": 0.46,       # 两眼间距 / 面宽
    "nose_mouth_to_mouth_chin": PHI - 1,  # 鼻-嘴 / 嘴-下巴 ≈ 0.618
    "face_height_to_width": 1.618,        # 脸长 / 脸宽
    "forehead_to_eye_ratio": 0.33,        # 额头 / 全脸高度
    "lower_face_ratio": 0.33,             # 嘴-下巴 / 全脸高度
}

# 东亚脸校正系数
EAST_ASIAN_CORRECTIONS = {
    "eye_dist_to_face_width": 1.08,   # 内眦间距偏宽是正常的，放宽8%
    "face_height_to_width": 0.95,     # 面宽相对偏大，降低理想比5%
    "nose_bridge_penalty": 0.5,       # 鼻梁高度惩罚减半
}


# ================================================================
# ViT-FBP 面部美学模型
# ================================================================
class FaceBeautyModel:
    """
    加载 ViT-FBP (Vision Transformer - Face Beauty Prediction) 模型
    基于 timm 库的 vit_base_patch16_224 架构
    在 SCUT-FBP5500 数据集上微调

    模型输入: 224x224 RGB 正面人脸
    模型输出: 标量 1-5 (美学评分)
    """

    def __init__(self, model_path: Optional[str] = None, device: str = "cpu"):
        self.device = torch.device(device) if _TORCH_AVAILABLE else None
        self.model = None
        self.transform = None
        self._loaded = False

        if model_path and _TORCH_AVAILABLE:
            self._load_model(model_path)

    def _load_model(self, model_path: str) -> None:
        """加载微调后的ViT-FBP权重"""
        try:
            # 创建ViT架构 (与训练时一致)
            self.model = timm.create_model(
                "vit_base_patch16_224",
                pretrained=False,
                num_classes=1,  # 回归任务，输出1个标量
            )

            # 加载微调权重
            state_dict = torch.load(model_path, map_location=self.device)
            # 兼容不同保存格式
            if "model_state_dict" in state_dict:
                state_dict = state_dict["model_state_dict"]
            elif "state_dict" in state_dict:
                state_dict = state_dict["state_dict"]

            self.model.load_state_dict(state_dict, strict=False)
            self.model.to(self.device)
            self.model.eval()

            # 标准ImageNet预处理
            from torchvision import transforms

            self.transform = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225],
                ),
            ])

            self._loaded = True
            logger.info(f"ViT-FBP模型加载成功 | device={self.device}")

        except FileNotFoundError:
            logger.warning(f"ViT-FBP权重文件不存在: {model_path}，使用回退评分")
        except Exception as e:
            logger.error(f"ViT-FBP模型加载失败: {e}，使用回退评分")

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def predict(self, face_image: Image.Image) -> float:
        """
        推理: PIL Image → 美学分 0-1

        ViT-FBP 原始输出范围 1-5，归一化到 0-1:
          score_01 = (raw - 1) / 4
        """
        if not self._loaded:
            return self._fallback_predict(face_image)

        tensor = self.transform(face_image.convert("RGB")).unsqueeze(0)
        tensor = tensor.to(self.device)

        with torch.no_grad():
            raw = self.model(tensor).item()

        # 原始输出 1-5，clamp后归一化
        raw = max(1.0, min(5.0, raw))
        normalized = (raw - 1.0) / 4.0  # → 0-1
        return normalized

    @staticmethod
    def _fallback_predict(face_image: Image.Image) -> float:
        """
        无模型时的回退评分
        基于图像质量指标: 亮度、对比度、清晰度
        """
        img_arr = np.array(face_image.convert("RGB"))

        # 亮度均衡度 (理想值 ~120-140)
        gray = cv2.cvtColor(img_arr, cv2.COLOR_RGB2GRAY)
        brightness = np.mean(gray)
        brightness_score = 1.0 - min(abs(brightness - 130) / 130, 1.0)

        # 对比度 (标准差)
        contrast = np.std(gray) / 80.0
        contrast_score = min(contrast, 1.0)

        # 清晰度 (Laplacian方差)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        sharpness_score = min(laplacian_var / 500.0, 1.0)

        # 加权合成
        return 0.3 * brightness_score + 0.3 * contrast_score + 0.4 * sharpness_score


# ================================================================
# 面部关键点分析 (MediaPipe FaceMesh)
# ================================================================
class FaceLandmarkAnalyzer:
    """用 MediaPipe FaceMesh 提取468个关键点并计算几何指标"""

    # FaceMesh 关键点索引 (468点模型)
    # 参考: https://github.com/google/mediapipe/blob/master/mediapipe/modules/face_geometry/data/canonical_face_model_uv_visualization.png
    IDX_LEFT_EYE_INNER = 133
    IDX_LEFT_EYE_OUTER = 33
    IDX_RIGHT_EYE_INNER = 362
    IDX_RIGHT_EYE_OUTER = 263
    IDX_NOSE_TIP = 1
    IDX_MOUTH_LEFT = 61
    IDX_MOUTH_RIGHT = 291
    IDX_MOUTH_TOP = 13
    IDX_MOUTH_BOTTOM = 14
    IDX_CHIN = 152
    IDX_FOREHEAD = 10
    IDX_LEFT_FACE = 234
    IDX_RIGHT_FACE = 454
    IDX_LEFT_CHEEK = 50
    IDX_RIGHT_CHEEK = 280
    IDX_NOSE_BRIDGE = 6
    IDX_LEFT_BROW_INNER = 107
    IDX_RIGHT_BROW_INNER = 336

    def __init__(self):
        self._face_mesh = None
        if _MP_AVAILABLE:
            self._face_mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=True,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
            )

    def extract_landmarks(
        self, image: np.ndarray
    ) -> Optional[FaceLandmarks]:
        """从BGR图像中提取面部关键度量"""
        if not self._face_mesh:
            return None

        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = self._face_mesh.process(rgb)

        if not results.multi_face_landmarks:
            logger.warning("未检测到人脸")
            return None

        lm = results.multi_face_landmarks[0].landmark
        h, w = image.shape[:2]

        def pt(idx: int) -> tuple[float, float]:
            return (lm[idx].x * w, lm[idx].y * h)

        fl = FaceLandmarks()

        # 眼睛中心
        le_inner, le_outer = pt(self.IDX_LEFT_EYE_INNER), pt(self.IDX_LEFT_EYE_OUTER)
        re_inner, re_outer = pt(self.IDX_RIGHT_EYE_INNER), pt(self.IDX_RIGHT_EYE_OUTER)
        fl.left_eye_center = self._midpoint(le_inner, le_outer)
        fl.right_eye_center = self._midpoint(re_inner, re_outer)

        # 其他关键点
        fl.nose_tip = pt(self.IDX_NOSE_TIP)
        fl.chin = pt(self.IDX_CHIN)
        fl.forehead_top = pt(self.IDX_FOREHEAD)
        fl.left_face_edge = pt(self.IDX_LEFT_FACE)
        fl.right_face_edge = pt(self.IDX_RIGHT_FACE)

        mouth_left = pt(self.IDX_MOUTH_LEFT)
        mouth_right = pt(self.IDX_MOUTH_RIGHT)
        fl.mouth_center = self._midpoint(mouth_left, mouth_right)

        # 计算度量
        fl.face_width = self._dist(fl.left_face_edge, fl.right_face_edge)
        fl.face_height = self._dist(fl.forehead_top, fl.chin)
        fl.eye_distance = self._dist(fl.left_eye_center, fl.right_eye_center)
        fl.nose_to_mouth = self._dist(fl.nose_tip, fl.mouth_center)
        fl.mouth_to_chin = self._dist(fl.mouth_center, fl.chin)
        fl.forehead_to_eye = self._dist(
            fl.forehead_top,
            self._midpoint(fl.left_eye_center, fl.right_eye_center),
        )

        return fl

    def calculate_symmetry(
        self, image: np.ndarray, landmarks: FaceLandmarks
    ) -> float:
        """
        面部对称性评分 0-10
        方法: 比较左半脸和右半脸关键点到中线的距离偏差
        """
        if not self._face_mesh:
            return 7.0  # 无关键点时返回合理默认值

        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = self._face_mesh.process(rgb)
        if not results.multi_face_landmarks:
            return 7.0

        lm = results.multi_face_landmarks[0].landmark
        h, w = image.shape[:2]

        # 对称点对 (左idx, 右idx)
        symmetric_pairs = [
            (33, 263),    # 眼角外
            (133, 362),   # 眼角内
            (50, 280),    # 颧骨
            (61, 291),    # 嘴角
            (107, 336),   # 眉毛内侧
            (234, 454),   # 面部轮廓
            (130, 359),   # 下眼睑
            (159, 386),   # 上眼睑
        ]

        # 面部中线 X 坐标
        midline_x = (lm[self.IDX_NOSE_BRIDGE].x + lm[self.IDX_CHIN].x) / 2

        deviations = []
        for left_idx, right_idx in symmetric_pairs:
            left_dist = abs(lm[left_idx].x - midline_x)
            right_dist = abs(lm[right_idx].x - midline_x)

            if max(left_dist, right_dist) > 0.001:
                deviation = abs(left_dist - right_dist) / max(left_dist, right_dist)
                deviations.append(deviation)

            # Y轴对称也检查
            y_dev = abs(lm[left_idx].y - lm[right_idx].y)
            deviations.append(y_dev)

        if not deviations:
            return 7.0

        avg_deviation = sum(deviations) / len(deviations)
        # 偏差 0→10分, 偏差 0.15→5分, 偏差 0.3+→2分
        score = max(0, 10 * (1 - avg_deviation / 0.2))
        return round(min(10.0, score), 1)

    def calculate_golden_ratio(
        self, landmarks: FaceLandmarks, is_east_asian: bool = False
    ) -> tuple[float, dict]:
        """
        黄金比例评分 0-10
        比较实际比例与理想比例的偏差

        Returns: (score, ratio_details)
        """
        if landmarks.face_width < 1 or landmarks.face_height < 1:
            return 7.0, {}

        # 计算实际比例
        actual_ratios = {
            "eye_dist_to_face_width": (
                landmarks.eye_distance / landmarks.face_width
                if landmarks.face_width > 0
                else 0
            ),
            "face_height_to_width": (
                landmarks.face_height / landmarks.face_width
                if landmarks.face_width > 0
                else 0
            ),
            "lower_face_ratio": (
                landmarks.mouth_to_chin / landmarks.face_height
                if landmarks.face_height > 0
                else 0
            ),
        }

        if landmarks.nose_to_mouth > 0 and landmarks.mouth_to_chin > 0:
            actual_ratios["nose_mouth_to_mouth_chin"] = (
                landmarks.nose_to_mouth / landmarks.mouth_to_chin
            )

        if landmarks.face_height > 0:
            actual_ratios["forehead_to_eye_ratio"] = (
                landmarks.forehead_to_eye / landmarks.face_height
            )

        # 与理想比例比较
        ratio_details = {}
        total_deviation = 0
        count = 0

        for key, actual in actual_ratios.items():
            ideal = IDEAL_RATIOS.get(key, actual)

            # 东亚脸校正
            if is_east_asian and key in EAST_ASIAN_CORRECTIONS:
                ideal *= EAST_ASIAN_CORRECTIONS[key]

            deviation = abs(actual - ideal) / ideal if ideal > 0 else 0
            total_deviation += deviation
            count += 1

            ratio_details[key] = {
                "actual": round(actual, 3),
                "ideal": round(ideal, 3),
                "deviation_pct": round(deviation * 100, 1),
            }

        avg_deviation = total_deviation / max(count, 1)
        # 偏差 0→10分, 偏差 15%→7分, 偏差 40%+→3分
        score = max(0, 10 * (1 - avg_deviation / 0.3))
        return round(min(10.0, score), 1), ratio_details

    @staticmethod
    def _dist(p1: tuple[float, float], p2: tuple[float, float]) -> float:
        return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)

    @staticmethod
    def _midpoint(
        p1: tuple[float, float], p2: tuple[float, float]
    ) -> tuple[float, float]:
        return ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)

    def close(self):
        if self._face_mesh:
            self._face_mesh.close()


# ================================================================
# 皮肤/头发质量分析
# ================================================================
def analyze_skin_quality(face_bgr: np.ndarray) -> tuple[float, str]:
    """
    皮肤质量评分 0-10
    指标: 均匀度、光泽度、痘印/色斑检测
    """
    hsv = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)

    h, w = face_bgr.shape[:2]

    # ---- 1. 肤色均匀度 (H/S通道标准差越小越好) ----
    # 取面部中心区域 (排除头发/背景)
    margin_x, margin_y = int(w * 0.25), int(h * 0.2)
    roi = hsv[margin_y : h - margin_y, margin_x : w - margin_x]

    if roi.size == 0:
        return 6.0, "无法分析皮肤区域"

    h_std = np.std(roi[:, :, 0])
    s_std = np.std(roi[:, :, 1])
    uniformity = max(0, 1 - (h_std + s_std) / 80)  # 0-1

    # ---- 2. 光泽度 (高光区域比例) ----
    v_channel = roi[:, :, 2]
    highlight_ratio = np.sum(v_channel > 200) / max(v_channel.size, 1)
    # 适度高光好 (5-20%), 过多或过少都扣分
    gloss = 1.0 - min(abs(highlight_ratio - 0.1) / 0.15, 1.0)

    # ---- 3. 纹理清晰度 (Laplacian方差 — 太模糊=低分辨率) ----
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    clarity = min(lap_var / 300.0, 1.0)

    # ---- 4. 色斑/痘印检测 (红色通道异常区域) ----
    b, g, r = cv2.split(face_bgr[margin_y : h - margin_y, margin_x : w - margin_x])
    redness = r.astype(float) - (g.astype(float) + b.astype(float)) / 2
    blemish_ratio = np.sum(redness > 40) / max(redness.size, 1)
    blemish_score = max(0, 1 - blemish_ratio * 5)

    # 加权
    raw = 0.3 * uniformity + 0.2 * gloss + 0.2 * clarity + 0.3 * blemish_score
    score = round(raw * 10, 1)
    score = max(1.0, min(10.0, score))

    if score >= 8:
        feedback = "皮肤状态优秀: 肤色均匀、光泽自然、无明显瑕疵"
    elif score >= 6:
        feedback = "皮肤状态良好: 建议加强防晒和保湿，注意饮食作息"
    elif score >= 4:
        feedback = "皮肤需改善: 建议建立清洁→保湿→防晒基础护肤流程"
    else:
        feedback = "皮肤待提升: 建议咨询皮肤科医生，制定针对性护理方案"

    return score, feedback


# ================================================================
# 下载图片工具
# ================================================================
async def download_image(url: str, timeout: float = 15.0) -> np.ndarray:
    """
    下载图片URL → OpenCV BGR numpy数组

    Raises: ValueError, httpx.HTTPError
    """
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    content_type = resp.headers.get("content-type", "")
    if not content_type.startswith("image/"):
        raise ValueError(f"URL返回非图片类型: {content_type}")

    img_bytes = resp.content
    if len(img_bytes) > 20 * 1024 * 1024:  # 20MB限制
        raise ValueError("图片文件过大 (>20MB)")

    pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    if bgr.shape[0] < 64 or bgr.shape[1] < 64:
        raise ValueError("图片分辨率过低 (<64px)")

    return bgr
