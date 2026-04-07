"""
QuantifyU — Consent 强制检查中间件
在路由层面拦截未获同意的操作
"""

from functools import wraps
from typing import Callable

from fastapi import HTTPException, status
from loguru import logger

from app.middleware.auth import AuthenticatedUser
from app.services.supabase_client import get_supabase


async def check_consent(
    user: AuthenticatedUser,
    required_consents: list[str],
) -> dict[str, bool]:
    """
    验证用户是否已同意所需的 consent 项

    Args:
        user: 已认证用户
        required_consents: 需要的 consent 字段列表
            如 ['consent_ai_scoring', 'consent_genital_data']

    Returns:
        {consent_field: bool} 映射

    Raises:
        HTTPException 403 如果任一 consent 未满足
    """
    sb = get_supabase()

    fields = ", ".join(required_consents + ["is_active", "banned_at"])
    resp = (
        sb.table("users")
        .select(fields)
        .eq("id", user.user_id)
        .single()
        .execute()
    )

    if not resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    user_data = resp.data

    # 检查账号状态
    if not user_data.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已停用",
        )
    if user_data.get("banned_at"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被封禁",
        )

    # 检查每个 consent
    missing = []
    consent_map = {}
    for field in required_consents:
        value = user_data.get(field, False)
        consent_map[field] = value
        if not value:
            missing.append(field)

    if missing:
        readable = {
            "consent_terms_of_service": "服务条款",
            "consent_privacy_policy": "隐私政策",
            "consent_ai_scoring": "AI评分",
            "consent_genital_data": "私密数据存储",
            "consent_data_sharing": "数据共享",
        }
        missing_names = [readable.get(f, f) for f in missing]
        logger.warning(
            f"[CONSENT] 用户未满足 consent | user={user.user_id} | "
            f"missing={missing}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"需要先同意以下条款：{', '.join(missing_names)}",
        )

    return consent_map


async def require_ai_scoring_consent(user: AuthenticatedUser) -> dict:
    """便捷方法：要求 AI 评分同意"""
    return await check_consent(user, [
        "consent_terms_of_service",
        "consent_privacy_policy",
        "consent_ai_scoring",
    ])


async def require_vault_consent(user: AuthenticatedUser) -> dict:
    """便捷方法：要求私密数据存储同意"""
    return await check_consent(user, [
        "consent_terms_of_service",
        "consent_privacy_policy",
        "consent_genital_data",
    ])


async def require_full_consent(user: AuthenticatedUser) -> dict:
    """便捷方法：要求所有核心同意"""
    return await check_consent(user, [
        "consent_terms_of_service",
        "consent_privacy_policy",
        "consent_ai_scoring",
        "consent_genital_data",
    ])
