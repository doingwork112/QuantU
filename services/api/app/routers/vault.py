"""
QuantifyU — Private Vault路由
POST /private-vault/save  加密存储生殖器官自测数据
"""

import base64
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger

from app.middleware.auth import AuthenticatedUser, get_current_user, get_client_ip
from app.schemas.vault import VaultSaveRequest, VaultSaveResponse
from app.schemas.base import BaseResponse
from app.services.supabase_client import get_supabase
from app.services.response_builder import build_response
from app.utils.encryption import EncryptionService
from app.config import get_settings

router = APIRouter(prefix="/private-vault", tags=["隐私保险库"])


@router.post("/save", response_model=BaseResponse)
async def save_vault_data(
    body: VaultSaveRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    加密保存生殖器官自测数据

    流程:
    1. 验证consent_genital_data
    2. 提取所有非None的敏感字段
    3. 对每个字段独立AES-256-GCM加密
    4. 存入private_vault表（UPSERT）
    5. 记录审计日志
    6. 内存中立即清除明文数据
    """
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "unknown")
    logger.info(
        f"[VAULT] 保存请求 | user={user.user_id} | ip={client_ip}"
    )

    sb = get_supabase()
    settings = get_settings()

    # ---- 1. 验证consent ----
    user_resp = (
        sb.table("users")
        .select("consent_genital_data")
        .eq("id", user.user_id)
        .single()
        .execute()
    )
    if not user_resp.data or not user_resp.data.get("consent_genital_data"):
        logger.warning(
            f"[VAULT] 用户未同意生殖器官数据存储 | user={user.user_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="保存生殖器官数据需要先同意隐私条款 (consent_genital_data=true)",
        )

    # ---- 2. 提取敏感字段 ----
    sensitive_fields = {
        "penis_length_cm": body.penis_length_cm,
        "penis_girth_cm": body.penis_girth_cm,
        "penis_erect_length_cm": body.penis_erect_length_cm,
        "penis_erect_girth_cm": body.penis_erect_girth_cm,
        "breast_cup": body.breast_cup,
        "breast_band_size": body.breast_band_size,
        "breast_shape": body.breast_shape,
        "grooming_level": body.grooming_level,
        "self_rating": body.self_rating,
        "additional_notes": body.additional_notes,
    }

    # 过滤None值
    fields_to_encrypt = {
        k: v for k, v in sensitive_fields.items() if v is not None
    }

    if not fields_to_encrypt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="至少提供一个需要保存的敏感字段",
        )

    logger.info(
        f"[VAULT] 加密字段 | user={user.user_id} | "
        f"fields={list(fields_to_encrypt.keys())}"
    )

    # ---- 3. 加密每个字段 ----
    try:
        crypto = EncryptionService(
            settings.ENCRYPTION_MASTER_KEY, settings.ENCRYPTION_KEY_VERSION
        )
        encrypted_fields, field_ivs, shared_iv = crypto.encrypt_vault_data(
            fields_to_encrypt,
            user_id=user.user_id,  # AAD 绑定防止数据替换攻击
        )
        data_hash = crypto.compute_data_hash(fields_to_encrypt)
    except Exception as e:
        logger.error(
            f"[VAULT] 加密失败 | user={user.user_id} | error={e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="数据加密失败，请稍后重试",
        )

    # ---- 4. 构建DB行 ----
    vault_row: dict = {
        "user_id": user.user_id,
        "encryption_key_version": settings.ENCRYPTION_KEY_VERSION,
        "encryption_algorithm": "AES-256-GCM",
        "iv": base64.b64encode(shared_iv).decode(),
        "field_ivs": field_ivs,
        "data_hash": data_hash,
        "measured_at": (
            body.measured_at.isoformat()
            if body.measured_at
            else datetime.now(timezone.utc).isoformat()
        ),
    }

    # 将加密后的字段写入对应列
    for field_name, ciphertext in encrypted_fields.items():
        vault_row[field_name] = base64.b64encode(ciphertext).decode()

    # ---- 5. UPSERT（每个用户只保留最新一条） ----
    try:
        resp = (
            sb.table("private_vault")
            .upsert(vault_row, on_conflict="user_id")
            .execute()
        )
        vault_id = resp.data[0]["id"] if resp.data else "unknown"
    except Exception as e:
        logger.error(
            f"[VAULT] 写入数据库失败 | user={user.user_id} | error={e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="保存加密数据失败",
        )

    # ---- 6. 审计日志 ----
    try:
        sb.table("scoring_audit_log").insert({
            "user_id": user.user_id,
            "action": "vault_updated",
            "ip_address": client_ip,
            "user_agent": user_agent,
            "metadata": {
                "encrypted_fields": list(encrypted_fields.keys()),
                "field_count": len(encrypted_fields),
                "key_version": settings.ENCRYPTION_KEY_VERSION,
                "algorithm": "AES-256-GCM",
            },
        }).execute()
    except Exception as e:
        logger.warning(
            f"[VAULT] 审计日志写入失败（非致命） | user={user.user_id} | error={e}"
        )

    # ---- 7. 清除内存中的明文 ----
    del fields_to_encrypt
    del sensitive_fields

    logger.info(
        f"[VAULT] 保存成功 | user={user.user_id} | vault_id={vault_id} | "
        f"encrypted={len(encrypted_fields)}个字段 | algo=AES-256-GCM"
    )

    vault_resp = VaultSaveResponse(
        vault_id=str(vault_id),
        encrypted_fields=list(encrypted_fields.keys()),
        encryption_algorithm="AES-256-GCM",
        key_version=settings.ENCRYPTION_KEY_VERSION,
        saved_at=datetime.now(timezone.utc),
    )

    return await build_response(
        success=True,
        message=f"已加密保存 {len(encrypted_fields)} 个敏感字段 (AES-256-GCM)",
        data=vault_resp.model_dump(),
        user_id=user.user_id,
    )
