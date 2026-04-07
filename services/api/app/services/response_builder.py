"""
QuantifyU — 统一响应构建器
所有API响应自动附加 AI参考分 + 匹配兼容度
"""

from typing import Any, Optional

from loguru import logger

from app.schemas.base import (
    AIScoreRef,
    BaseResponse,
    MatchCompatibilityRef,
)
from app.services.supabase_client import get_supabase
from app.services.ai_scorer import AIScorer


async def build_response(
    success: bool,
    message: str,
    data: Any = None,
    user_id: Optional[str] = None,
) -> BaseResponse:
    """
    构建统一响应，自动查询并附加:
    - AI参考分（用户最新评分）
    - 匹配兼容度摘要
    """
    ai_ref = None
    match_ref = None

    if user_id:
        try:
            sb = get_supabase()

            # 查询用户最新评分
            score_resp = (
                sb.table("profiles")
                .select("latest_overall_score, score_updated_at")
                .eq("user_id", user_id)
                .maybe_single()
                .execute()
            )
            if score_resp.data:
                overall = score_resp.data.get("latest_overall_score")
                ai_ref = AIScoreRef(
                    overall_score=overall,
                    score_label=AIScorer.score_to_label(overall) if overall else None,
                    last_scored_at=score_resp.data.get("score_updated_at"),
                )

            # 查询匹配摘要
            match_resp = (
                sb.table("matches")
                .select("compatibility_pct, status")
                .or_(f"user_a.eq.{user_id},user_b.eq.{user_id}")
                .eq("status", "matched")
                .execute()
            )
            if match_resp.data:
                pcts = [
                    m["compatibility_pct"]
                    for m in match_resp.data
                    if m.get("compatibility_pct") is not None
                ]
                match_ref = MatchCompatibilityRef(
                    active_matches=len(match_resp.data),
                    avg_compatibility_pct=(
                        round(sum(pcts) / len(pcts), 1) if pcts else None
                    ),
                    top_compatibility_pct=max(pcts) if pcts else None,
                )

        except Exception as e:
            logger.warning(f"构建响应附加数据失败 | user={user_id} | error={e}")

    return BaseResponse(
        success=success,
        message=message,
        data=data,
        ai_score_ref=ai_ref,
        match_compatibility_ref=match_ref,
    )
