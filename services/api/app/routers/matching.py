"""
QuantifyU — 匹配路由
GET  /matches              返回当前用户的匹配列表（含兼容百分比）
POST /matches/compatibility 计算与指定用户的兼容度
POST /matches/daily-batch   触发每日 Top 50 批量计算 (管理员)
"""

from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger

from app.middleware.auth import AuthenticatedUser, get_current_user
from app.schemas.matching import (
    CompatibilityBreakdown,
    ComputeCompatibilityRequest,
    ComputeCompatibilityResponse,
    DailyBatchResponse,
    MatchItem,
    MatchListResponse,
)
from app.schemas.base import BaseResponse
from app.services.supabase_client import get_supabase
from app.services.matching_engine import (
    DailyMatchQueue,
    MatchingEngine,
    PreferenceWeights,
    ScoreVector,
)
from app.services.response_builder import build_response

router = APIRouter(prefix="/matches", tags=["匹配"])

_engine = MatchingEngine()
_daily_queue = DailyMatchQueue()


# ================================================================
# GET /matches — 匹配列表
# ================================================================
@router.get("", response_model=BaseResponse)
async def get_matches(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    status_filter: str = Query(
        default="matched", description="matched|pending|all"
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
):
    """
    获取匹配列表
    每条匹配记录包含:
    - 对方基础资料
    - 兼容百分比 + 五维breakdown + 解释文本
    - AI参考分（仅双方同意时）
    """
    logger.info(
        f"获取匹配列表 | user={user.user_id} | "
        f"status={status_filter} | page={page}"
    )

    sb = get_supabase()
    uid = user.user_id

    # ---- 查询匹配记录 ----
    query = sb.table("matches").select("*")
    query = query.or_(f"user_a.eq.{uid},user_b.eq.{uid}")

    if status_filter != "all":
        query = query.eq("status", status_filter)

    query = query.order("created_at", desc=True)

    offset = (page - 1) * page_size
    query = query.range(offset, offset + page_size - 1)

    try:
        resp = query.execute()
    except Exception as e:
        logger.error(f"查询matches失败 | user={uid} | error={e}")
        raise HTTPException(status_code=500, detail="查询匹配记录失败")

    matches_data = resp.data or []

    # ---- 收集所有对方用户ID ----
    other_ids = set()
    for m in matches_data:
        other_id = m["user_b"] if m["user_a"] == uid else m["user_a"]
        other_ids.add(other_id)

    # ---- 批量查询对方资料 ----
    profiles_map: dict = {}
    users_map: dict = {}
    if other_ids:
        try:
            profiles_resp = (
                sb.table("profiles")
                .select("user_id, avatar_url, latest_overall_score")
                .in_("user_id", list(other_ids))
                .execute()
            )
            for p in profiles_resp.data or []:
                profiles_map[p["user_id"]] = p

            users_resp = (
                sb.table("users")
                .select("id, display_name, date_of_birth")
                .in_("id", list(other_ids))
                .execute()
            )
            for u in users_resp.data or []:
                users_map[u["id"]] = u
        except Exception as e:
            logger.warning(f"批量查询用户信息失败 | error={e}")

    # ---- 查询当前用户的隐私设置 ----
    try:
        prefs_resp = (
            sb.table("user_preferences")
            .select("show_score_to_matches")
            .eq("user_id", uid)
            .maybe_single()
            .execute()
        )
        my_show_score = (
            prefs_resp.data.get("show_score_to_matches", False)
            if prefs_resp.data
            else False
        )
    except Exception:
        my_show_score = False

    # ---- 构建匹配列表 ----
    items: list[MatchItem] = []
    for m in matches_data:
        is_user_a = m["user_a"] == uid
        other_id = m["user_b"] if is_user_a else m["user_a"]

        other_profile = profiles_map.get(other_id, {})
        other_user = users_map.get(other_id, {})

        # 计算年龄
        other_age = _calculate_age(other_user.get("date_of_birth"))

        # 对方评分（仅双方都同意公开时显示）
        other_score = None
        if my_show_score and m["status"] == "matched":
            other_score = other_profile.get("latest_overall_score")

        # 兼容性数据 (v2 格式)
        compat_pct = m.get("compatibility_pct") or 0
        breakdown_raw = m.get("compatibility_breakdown") or {}

        breakdown = CompatibilityBreakdown(
            cosine_similarity=breakdown_raw.get("cosine_similarity", 0),
            weighted_dot_product=breakdown_raw.get("weighted_dot_product", 0),
            dimension_scores=breakdown_raw.get("dimension_scores", {}),
            preference_match=breakdown_raw.get("preference_match", 50),
            age_compatibility=breakdown_raw.get("age_compatibility", 50),
            distance_score=breakdown_raw.get("distance_score", 50),
            score_similarity=breakdown_raw.get("score_similarity"),
            distance_km=breakdown_raw.get("distance_km"),
            explanation=breakdown_raw.get("explanation", ""),
            highlights=breakdown_raw.get("highlights", []),
            algorithm_version=breakdown_raw.get("algorithm_version", "v1.0"),
        )

        my_action = (
            m.get("user_a_action") if is_user_a else m.get("user_b_action")
        )
        their_action = None
        if m["status"] == "matched":
            their_action = (
                m.get("user_b_action") if is_user_a else m.get("user_a_action")
            )

        items.append(
            MatchItem(
                match_id=m["id"],
                other_user_id=other_id,
                other_display_name=other_user.get("display_name", "用户"),
                other_avatar_url=other_profile.get("avatar_url"),
                other_age=other_age,
                other_overall_score=other_score,
                status=m["status"],
                compatibility_pct=compat_pct,
                compatibility_breakdown=breakdown,
                my_action=my_action,
                their_action=their_action,
                matched_at=m.get("matched_at"),
                created_at=m["created_at"],
            )
        )

    match_list = MatchListResponse(
        matches=items,
        total=len(items),
        page=page,
        page_size=page_size,
    )

    logger.info(
        f"匹配列表返回 | user={uid} | count={len(items)} | "
        f"status={status_filter}"
    )

    return await build_response(
        success=True,
        message=f"找到 {len(items)} 条匹配记录",
        data=match_list.model_dump(),
        user_id=uid,
    )


# ================================================================
# POST /matches/compatibility — 计算与指定用户的兼容度
# ================================================================
@router.post("/compatibility", response_model=BaseResponse)
async def compute_compatibility(
    request: Request,
    body: ComputeCompatibilityRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    实时计算当前用户与目标用户的兼容性百分比
    返回: 兼容百分比 + 五维breakdown + 解释文本 + 亮点
    """
    sb = get_supabase()
    uid = user.user_id
    target_id = body.target_user_id

    if uid == target_id:
        raise HTTPException(status_code=400, detail="不能与自己计算兼容度")

    logger.info(f"计算兼容度 | user={uid} | target={target_id}")

    # ---- 获取双方最新评分 ----
    my_rating = await _get_latest_rating(sb, uid)
    their_rating = await _get_latest_rating(sb, target_id)

    if not my_rating:
        raise HTTPException(status_code=404, detail="你尚未完成评分")
    if not their_rating:
        raise HTTPException(status_code=404, detail="对方尚未完成评分")

    my_scores = ScoreVector.from_dict(my_rating)
    their_scores = ScoreVector.from_dict(their_rating)

    # ---- 获取对方偏好权重 ----
    their_prefs = await _get_user_prefs(sb, target_id)
    their_weights = PreferenceWeights.from_dict(their_prefs)

    # ---- 获取双方年龄 ----
    my_age = await _get_user_age(sb, uid)
    their_age = await _get_user_age(sb, target_id)

    # ---- 偏好匹配度 ----
    my_prefs = await _get_user_prefs(sb, uid)
    their_profile = await _get_user_profile_for_pref(sb, target_id)
    pref_pct = _engine.calculate_preference_match(my_prefs, their_profile)

    # ---- 核心计算 ----
    result = _engine.compute_compatibility(
        my_scores=my_scores,
        their_scores=their_scores,
        their_weights=their_weights,
        my_age=my_age,
        their_age=their_age,
        distance_km=None,  # TODO: 从PostGIS计算
        preference_match_pct=pref_pct,
    )

    response = ComputeCompatibilityResponse(
        my_user_id=uid,
        target_user_id=target_id,
        compatibility_pct=result.compatibility_pct,
        breakdown=CompatibilityBreakdown(
            cosine_similarity=result.cosine_similarity,
            weighted_dot_product=result.weighted_dot_product,
            dimension_scores=result.dimension_scores,
            preference_match=result.preference_match,
            age_compatibility=result.age_compatibility,
            distance_score=result.distance_score,
            explanation=result.explanation,
            highlights=result.highlights,
            algorithm_version=result.algorithm_version,
        ),
        explanation=result.explanation,
        highlights=result.highlights,
    )

    logger.info(
        f"兼容度计算完成 | user={uid} | target={target_id} | "
        f"pct={result.compatibility_pct}%"
    )

    return await build_response(
        success=True,
        message=f"兼容度: {result.compatibility_pct}%",
        data=response.model_dump(),
        user_id=uid,
    )


# ================================================================
# POST /matches/daily-batch — 触发每日批量匹配
# ================================================================
@router.post("/daily-batch", response_model=BaseResponse)
async def trigger_daily_batch(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    触发每日 Top 50 匹配批量计算
    (生产环境应由 cron/scheduler 调用, 此端点供管理员手动触发)
    """
    sb = get_supabase()
    uid = user.user_id

    # TODO: 加管理员权限检查
    logger.info(f"手动触发每日批量匹配 | triggered_by={uid}")

    try:
        stats = await _daily_queue.run_daily_batch(sb)
    except Exception as e:
        logger.error(f"每日批量匹配失败 | error={e}")
        raise HTTPException(status_code=500, detail=f"批量计算失败: {str(e)}")

    batch_resp = DailyBatchResponse(**stats)

    logger.info(
        f"每日批量匹配完成 | users={stats['users_processed']} | "
        f"matches={stats['matches_created']}"
    )

    return await build_response(
        success=True,
        message=f"批量计算完成: 处理 {stats['users_processed']} 用户, 生成 {stats['matches_created']} 条匹配",
        data=batch_resp.model_dump(),
        user_id=uid,
    )


# ================================================================
# 内部辅助函数
# ================================================================

async def _get_latest_rating(sb, user_id: str) -> dict | None:
    """获取用户最新评分记录"""
    try:
        resp = (
            sb.table("ratings")
            .select("face_score, body_score, height_score, skin_hair_score, genital_score")
            .eq("user_id", user_id)
            .order("scored_at", desc=True)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception as e:
        logger.warning(f"获取评分失败 | user={user_id} | error={e}")
        return None


async def _get_user_prefs(sb, user_id: str) -> dict:
    """获取用户偏好设置"""
    try:
        resp = (
            sb.table("user_preferences")
            .select("*")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        return resp.data or {}
    except Exception:
        return {}


async def _get_user_age(sb, user_id: str) -> int | None:
    """获取用户年龄"""
    try:
        resp = (
            sb.table("users")
            .select("date_of_birth")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        if resp.data and resp.data.get("date_of_birth"):
            return _calculate_age(resp.data["date_of_birth"])
        return None
    except Exception:
        return None


async def _get_user_profile_for_pref(sb, user_id: str) -> dict:
    """获取用于偏好匹配计算的用户资料"""
    profile: dict = {}
    try:
        user_resp = (
            sb.table("users")
            .select("gender, date_of_birth")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        if user_resp.data:
            profile["gender"] = user_resp.data.get("gender")
            profile["age"] = _calculate_age(user_resp.data.get("date_of_birth"))

        prof_resp = (
            sb.table("profiles")
            .select("looking_for")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        if prof_resp.data:
            profile["looking_for"] = prof_resp.data.get("looking_for", [])
    except Exception:
        pass
    return profile


def _calculate_age(dob_str: str | None) -> int | None:
    """从出生日期字符串计算年龄"""
    if not dob_str:
        return None
    try:
        born = date.fromisoformat(str(dob_str))
        today = date.today()
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    except (ValueError, TypeError):
        return None
