"""
QuantifyU — 通用响应模型
所有API响应统一包装，携带AI参考分和匹配兼容度
"""

from pydantic import BaseModel
from typing import Any, Optional
from datetime import datetime


class AIScoreRef(BaseModel):
    """AI参考分摘要 — 附加在每个响应中"""
    overall_score: Optional[float] = None        # 用户当前总分 /100
    score_label: Optional[str] = None            # "优秀" / "良好" / "中等" / "待提升"
    last_scored_at: Optional[datetime] = None


class MatchCompatibilityRef(BaseModel):
    """匹配兼容度摘要 — 附加在每个响应中"""
    active_matches: int = 0
    avg_compatibility_pct: Optional[float] = None  # 平均兼容度
    top_compatibility_pct: Optional[float] = None  # 最高兼容度


class BaseResponse(BaseModel):
    """所有API的统一响应包装"""
    success: bool
    message: str
    data: Optional[Any] = None
    ai_score_ref: Optional[AIScoreRef] = None
    match_compatibility_ref: Optional[MatchCompatibilityRef] = None
    timestamp: datetime = datetime.utcnow()


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    error_code: str
    detail: Optional[str] = None
    timestamp: datetime = datetime.utcnow()
