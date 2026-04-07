"""
QuantifyU — 评分相关Pydantic模型 (v2 — 对应LooksmaxxingEngine)
"""

from pydantic import BaseModel, field_validator
from typing import Any, Optional
from datetime import datetime


class SelfMeasurements(BaseModel):
    """用户自测数据（生殖器官相关 — 发送后立即加密）"""
    # 男性字段
    penis_length_cm: Optional[float] = None
    penis_girth_cm: Optional[float] = None
    penis_erect_length_cm: Optional[float] = None
    penis_erect_girth_cm: Optional[float] = None

    # 女性字段
    breast_cup: Optional[str] = None
    breast_band_size: Optional[float] = None
    breast_shape: Optional[str] = None

    # 通用
    grooming_level: Optional[int] = None  # 1-5
    self_rating: Optional[int] = None     # 1-10

    @field_validator("penis_length_cm", "penis_erect_length_cm")
    @classmethod
    def validate_length(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (3.0 <= v <= 35.0):
            raise ValueError("长度数据范围: 3-35 cm")
        return v

    @field_validator("penis_girth_cm", "penis_erect_girth_cm")
    @classmethod
    def validate_girth(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (3.0 <= v <= 30.0):
            raise ValueError("周长数据范围: 3-30 cm")
        return v

    @field_validator("breast_cup")
    @classmethod
    def validate_cup(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            allowed = {"AA", "A", "B", "C", "D", "DD", "DDD", "E", "F", "G", "H"}
            if v.upper() not in allowed:
                raise ValueError(f"罩杯必须为: {allowed}")
            return v.upper()
        return v

    @field_validator("grooming_level")
    @classmethod
    def validate_grooming(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (1 <= v <= 5):
            raise ValueError("修饰程度范围: 1-5")
        return v

    @field_validator("self_rating")
    @classmethod
    def validate_self_rating(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (1 <= v <= 10):
            raise ValueError("自评分范围: 1-10")
        return v


class CalculateScoreRequest(BaseModel):
    """评分请求 (v2)"""
    face_photo_url: str                                    # 正面面部照片URL (必须)
    body_photo_url: Optional[str] = None                   # 正面全身照URL
    body_side_photo_url: Optional[str] = None              # 侧面全身照URL (体态检测)
    height_cm: float                                       # 身高cm
    weight_kg: Optional[float] = None                      # 体重kg
    ethnicity: Optional[str] = None                        # 族裔 (用于东亚脸优化)
    self_measurements: Optional[SelfMeasurements] = None   # 生殖器官自测

    @field_validator("height_cm")
    @classmethod
    def validate_height(cls, v: float) -> float:
        if not (100 <= v <= 250):
            raise ValueError("身高范围: 100-250 cm")
        return v

    @field_validator("weight_kg")
    @classmethod
    def validate_weight(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (30 <= v <= 300):
            raise ValueError("体重范围: 30-300 kg")
        return v


class FaceDetail(BaseModel):
    """面部评分详情"""
    weighted_score: float    # 加权后 /40
    max: int = 40
    raw_0_10: float          # 原始0-10分
    aesthetic: float         # 美学分 0-10 (ViT-FBP)
    symmetry: float          # 对称性 0-10
    golden_ratio: float      # 黄金比例 0-10
    detail: dict = {}


class BodyDetail(BaseModel):
    """身材评分详情"""
    weighted_score: float    # 加权后 /25
    max: int = 25
    raw_0_10: float
    proportions: float       # 比例分 0-10
    bmi: float               # BMI分 0-10
    posture: float           # 体态分 0-10
    metrics: dict = {}       # shr, whr, leg_body_ratio, bmi
    detail: dict = {}


class HeightDetail(BaseModel):
    """身高评分详情"""
    weighted_score: float    # /15
    max: int = 15
    height_cm: float


class SkinHairDetail(BaseModel):
    """皮肤头发评分详情"""
    weighted_score: float    # /10
    max: int = 10
    raw_0_10: float


class GenitalDetail(BaseModel):
    """生殖器官评分详情"""
    weighted_score: float    # /10
    max: int = 10
    note: str = "基于用户自测数值，非AI视觉评分"


class ScoreBreakdown(BaseModel):
    """五维评分breakdown"""
    face: FaceDetail
    body: BodyDetail
    height: HeightDetail
    skin_hair: SkinHairDetail
    genital: GenitalDetail


class ScoreResponse(BaseModel):
    """评分响应 (v2)"""
    rating_id: str
    total_score: float                     # 总分 /100
    percentile: str                        # "top 15%"
    score_label: str                       # "优秀" etc
    breakdown: ScoreBreakdown
    face_feedback: str
    body_feedback: str
    height_feedback: str
    skin_hair_feedback: str
    genital_feedback: str
    improvement_tips: list[str] = []
    east_asian_notes: list[str] = []
    model_version: str
    scored_at: datetime = datetime.utcnow()
