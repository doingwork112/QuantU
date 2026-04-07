"""
QuantifyU — 匹配相关Pydantic模型
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ---- 兼容性详情 (v2 — 含解释文本) ----

class DimensionMatchDetail(BaseModel):
    """单维度匹配分"""
    dimension: str
    label: str
    score: float         # 0-100
    their_weight_pct: float  # 对方权重占比 %


class CompatibilityBreakdown(BaseModel):
    # v2 字段
    cosine_similarity: float = 0.0
    weighted_dot_product: float = 0.0
    dimension_scores: dict[str, float] = {}   # {face: 82.5, body: 60.0, ...}
    preference_match: float = 50.0
    age_compatibility: float = 50.0
    distance_score: float = 50.0

    # v1 兼容 (旧字段别名)
    score_similarity: Optional[float] = None
    distance_km: Optional[float] = None

    # 解释
    explanation: str = ""
    highlights: list[str] = []
    algorithm_version: str = "v2.0"


class MatchItem(BaseModel):
    match_id: str
    other_user_id: str
    other_display_name: str
    other_avatar_url: Optional[str] = None
    other_age: Optional[int] = None
    other_overall_score: Optional[float] = None  # 仅双方同意时可见

    status: str  # pending | matched | rejected
    compatibility_pct: float
    compatibility_breakdown: CompatibilityBreakdown
    my_action: Optional[str] = None     # like | superlike | pass
    their_action: Optional[str] = None  # 仅matched后可见

    matched_at: Optional[datetime] = None
    created_at: datetime


class MatchListResponse(BaseModel):
    matches: list[MatchItem]
    total: int
    page: int
    page_size: int


# ---- 两人兼容性查询 ----

class ComputeCompatibilityRequest(BaseModel):
    target_user_id: str = Field(..., description="要计算兼容度的目标用户ID")


class ComputeCompatibilityResponse(BaseModel):
    my_user_id: str
    target_user_id: str
    compatibility_pct: float
    breakdown: CompatibilityBreakdown
    explanation: str
    highlights: list[str]


# ---- 每日批量结果 ----

class DailyBatchResponse(BaseModel):
    users_processed: int
    matches_created: int
