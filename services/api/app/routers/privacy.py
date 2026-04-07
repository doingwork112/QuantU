"""
QuantifyU — 隐私管理路由
  POST /privacy/consent/update      更新同意状态
  GET  /privacy/consent/status       查询当前同意状态
  DELETE /privacy/vault              永久删除私密数据
  POST /privacy/photo/upload         上传加密照片（仅存哈希）
  GET  /privacy/data-export          导出个人数据 (GDPR)
  DELETE /privacy/account            永久删除账号 (GDPR 被遗忘权)
"""

import base64
import gc
import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status
from loguru import logger
from pydantic import BaseModel, Field
from typing import Optional

from app.middleware.auth import AuthenticatedUser, get_current_user, get_client_ip
from app.schemas.base import BaseResponse
from app.services.supabase_client import get_supabase
from app.services.response_builder import build_response
from app.utils.encryption import (
    EncryptionService,
    PhotoHashService,
    generate_request_id,
    secure_delete_dict,
)
from app.config import get_settings

router = APIRouter(prefix="/privacy", tags=["隐私管理"])


# ================================================================
# Schemas
# ================================================================

class ConsentUpdateRequest(BaseModel):
    consent_ai_scoring: Optional[bool] = None
    consent_genital_data: Optional[bool] = None
    consent_data_sharing: Optional[bool] = None
    consent_marketing: Optional[bool] = None
    # 注：terms_of_service 和 privacy_policy 不可撤回（撤回 = 删除账号）


class ConsentStatusResponse(BaseModel):
    consent_terms_of_service: bool
    consent_privacy_policy: bool
    consent_ai_scoring: bool
    consent_genital_data: bool
    consent_data_sharing: bool
    consent_marketing: bool
    consent_updated_at: Optional[str] = None


class PhotoUploadResponse(BaseModel):
    photo_hash_id: str
    sha256_hash: str
    photo_type: str
    client_encrypted: bool
    message: str


class DataExportResponse(BaseModel):
    user: dict
    profile: dict
    ratings: list
    preferences: dict
    consent_history: list
    photo_hashes: list
    # vault 数据需要解密，单独处理
    vault_encrypted_fields: list[str]
    exported_at: str


# ================================================================
# POST /privacy/consent/update — 更新同意状态
# ================================================================
@router.post("/consent/update", response_model=BaseResponse)
async def update_consent(
    body: ConsentUpdateRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    更新用户同意状态

    重要行为：
    - 撤回 consent_genital_data → 自动删除 private_vault（由 DB 触发器执行）
    - 撤回 consent_ai_scoring → 自动删除 photo_hashes（由 DB 触发器执行）
    - 每次变更记录到 consent_audit_log（由 DB 触发器执行）
    """
    sb = get_supabase()
    uid = user.user_id
    client_ip = get_client_ip(request)
    request_id = generate_request_id()

    logger.info(
        f"[PRIVACY] Consent 更新请求 | user={uid} | "
        f"request_id={request_id} | ip={client_ip}"
    )

    # 构建更新字段
    update_fields: dict = {}
    updates = body.model_dump(exclude_none=True)

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请提供至少一个需要更新的 consent 字段",
        )

    for field, value in updates.items():
        update_fields[field] = value

    # 查询当前状态（用于日志）
    current = (
        sb.table("users")
        .select("consent_ai_scoring, consent_genital_data, consent_data_sharing, consent_marketing")
        .eq("id", uid)
        .single()
        .execute()
    )

    changes = []
    for field, new_val in update_fields.items():
        old_val = current.data.get(field) if current.data else None
        if old_val != new_val:
            changes.append(f"{field}: {old_val} → {new_val}")

    if not changes:
        return await build_response(
            success=True,
            message="Consent 状态未发生变更",
            data={"changed": []},
            user_id=uid,
        )

    # 撤回 genital consent 时的显式警告日志
    if update_fields.get("consent_genital_data") is False:
        logger.warning(
            f"[PRIVACY] ⚠️ 用户撤回 genital consent — 将级联删除 vault 数据 | "
            f"user={uid} | request_id={request_id}"
        )

    # 执行更新（触发器自动记录审计 + 级联清除）
    try:
        sb.table("users").update(update_fields).eq("id", uid).execute()
    except Exception as e:
        logger.error(f"[PRIVACY] Consent 更新失败 | user={uid} | error={e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新 consent 失败",
        )

    # 后端也记录审计（补充 IP 和 user_agent）
    try:
        sb.table("scoring_audit_log").insert({
            "user_id": uid,
            "action": "consent_updated",
            "ip_address": client_ip,
            "user_agent": request.headers.get("User-Agent", ""),
            "metadata": {
                "changes": changes,
                "request_id": request_id,
                "fields_updated": list(update_fields.keys()),
            },
        }).execute()
    except Exception:
        pass  # 审计日志写入失败不阻塞主流程

    logger.info(
        f"[PRIVACY] Consent 更新成功 | user={uid} | "
        f"changes={changes} | request_id={request_id}"
    )

    return await build_response(
        success=True,
        message=f"已更新 {len(changes)} 项同意设置",
        data={"changed": changes, "request_id": request_id},
        user_id=uid,
    )


# ================================================================
# GET /privacy/consent/status — 查询同意状态
# ================================================================
@router.get("/consent/status", response_model=BaseResponse)
async def get_consent_status(
    user: AuthenticatedUser = Depends(get_current_user),
):
    sb = get_supabase()
    resp = (
        sb.table("users")
        .select(
            "consent_terms_of_service, consent_privacy_policy, "
            "consent_ai_scoring, consent_genital_data, "
            "consent_data_sharing, consent_marketing, consent_updated_at"
        )
        .eq("id", user.user_id)
        .single()
        .execute()
    )

    if not resp.data:
        raise HTTPException(status_code=404, detail="用户不存在")

    return await build_response(
        success=True,
        message="当前同意状态",
        data=ConsentStatusResponse(**resp.data).model_dump(),
        user_id=user.user_id,
    )


# ================================================================
# DELETE /privacy/vault — 永久删除私密数据
# ================================================================
@router.delete("/vault", response_model=BaseResponse)
async def delete_vault_data(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    永久删除用户的 private_vault 数据
    同时撤回 consent_genital_data
    """
    sb = get_supabase()
    uid = user.user_id
    client_ip = get_client_ip(request)
    request_id = generate_request_id()

    logger.warning(
        f"[PRIVACY] ⚠️ 请求永久删除 vault 数据 | user={uid} | "
        f"request_id={request_id}"
    )

    # 删除 vault
    try:
        sb.table("private_vault").delete().eq("user_id", uid).execute()
    except Exception as e:
        logger.error(f"[PRIVACY] Vault 删除失败 | user={uid} | error={e}")
        raise HTTPException(status_code=500, detail="删除失败")

    # 清除 ratings 中的加密 genital 字段
    try:
        sb.table("ratings").update({
            "genital_score": None,
            "genital_score_encrypted": None,
            "genital_score_iv": None,
        }).eq("user_id", uid).execute()
    except Exception:
        pass

    # 撤回 genital consent
    try:
        sb.table("users").update({
            "consent_genital_data": False,
        }).eq("id", uid).execute()
    except Exception:
        pass

    # 审计
    sb.table("scoring_audit_log").insert({
        "user_id": uid,
        "action": "vault_permanently_deleted",
        "ip_address": client_ip,
        "user_agent": request.headers.get("User-Agent", ""),
        "metadata": {
            "request_id": request_id,
            "genital_scores_cleared": True,
            "consent_revoked": True,
        },
    }).execute()

    logger.info(f"[PRIVACY] Vault 数据已永久删除 | user={uid}")

    return await build_response(
        success=True,
        message="私密数据已永久删除，consent_genital_data 已撤回",
        data={"deleted": True, "request_id": request_id},
        user_id=uid,
    )


# ================================================================
# POST /privacy/photo/upload — 上传照片（服务端只存哈希）
# ================================================================
@router.post("/photo/upload", response_model=BaseResponse)
async def upload_photo_hash_only(
    request: Request,
    photo: UploadFile = File(...),
    photo_type: str = "face",
    client_encrypted: bool = False,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    上传照片用于 AI 评分

    流程：
    1. 接收照片字节（客户端可选 E2E 加密）
    2. 计算 SHA-256 哈希
    3. 将哈希存入 photo_hashes 表
    4. 返回哈希用于后续评分请求
    5. 照片字节在内存中处理完毕后立即清除

    注：实际 AI 处理在 /rating/calculate 端点进行，
    此端点仅负责哈希记录和照片短暂暂存
    """
    sb = get_supabase()
    uid = user.user_id

    if photo_type not in ("face", "body", "body_side", "avatar"):
        raise HTTPException(status_code=400, detail="无效的 photo_type")

    # 检查 AI scoring consent
    consent_resp = (
        sb.table("users")
        .select("consent_ai_scoring, is_active")
        .eq("id", uid)
        .single()
        .execute()
    )
    if not consent_resp.data or not consent_resp.data.get("consent_ai_scoring"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要先同意 AI 评分条款",
        )

    # 读取照片字节
    photo_bytes = bytearray(await photo.read())

    # 计算哈希
    hash_info = PhotoHashService.compute_file_hash(bytes(photo_bytes))

    # 存入 photo_hashes 表
    try:
        resp = sb.table("photo_hashes").insert({
            "user_id": uid,
            "photo_type": photo_type,
            "sha256_hash": hash_info["sha256"],
            "file_size_bytes": hash_info["size_bytes"],
            "mime_type": photo.content_type,
            "client_encrypted": client_encrypted,
            "retention_hours": 1,  # 最多保留 1 小时
        }).execute()

        photo_hash_id = resp.data[0]["id"] if resp.data else "unknown"
    except Exception as e:
        PhotoHashService.secure_wipe(photo_bytes)
        logger.error(f"[PHOTO] 哈希记录失败 | user={uid} | error={e}")
        raise HTTPException(status_code=500, detail="照片处理失败")

    # 安全清除内存
    PhotoHashService.secure_wipe(photo_bytes)

    logger.info(
        f"[PHOTO] 照片哈希已记录 | user={uid} | type={photo_type} | "
        f"hash={hash_info['sha256'][:16]}... | size={hash_info['size_bytes']}"
    )

    upload_resp = PhotoUploadResponse(
        photo_hash_id=photo_hash_id,
        sha256_hash=hash_info["sha256"],
        photo_type=photo_type,
        client_encrypted=client_encrypted,
        message="照片哈希已记录，原图不会被持久化存储",
    )

    return await build_response(
        success=True,
        message="照片已处理，仅保存哈希指纹",
        data=upload_resp.model_dump(),
        user_id=uid,
    )


# ================================================================
# GET /privacy/data-export — GDPR 数据导出
# ================================================================
@router.get("/data-export", response_model=BaseResponse)
async def export_user_data(
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    导出用户的所有个人数据（GDPR 第 20 条 — 数据可携带权）
    不含加密字段的明文（需额外解密请求）
    """
    sb = get_supabase()
    uid = user.user_id

    logger.info(f"[PRIVACY] 数据导出请求 | user={uid}")

    # 并行查询所有表
    user_data = sb.table("users").select("*").eq("id", uid).single().execute()
    profile_data = sb.table("profiles").select("*").eq("user_id", uid).maybe_single().execute()
    ratings_data = sb.table("ratings").select("*").eq("user_id", uid).order("scored_at", desc=True).execute()
    prefs_data = sb.table("user_preferences").select("*").eq("user_id", uid).maybe_single().execute()
    consent_history = sb.table("consent_audit_log").select("*").eq("user_id", uid).order("created_at", desc=True).execute()
    photo_hashes = sb.table("photo_hashes").select("*").eq("user_id", uid).execute()

    # Vault：仅返回加密字段名列表（不含密文）
    vault_data = sb.table("private_vault").select("id, encryption_algorithm, encryption_key_version, measured_at, created_at").eq("user_id", uid).maybe_single().execute()

    vault_fields = []
    if vault_data.data:
        # 查询哪些字段有数据
        full_vault = sb.table("private_vault").select("*").eq("user_id", uid).single().execute()
        if full_vault.data:
            sensitive_cols = [
                "penis_length_cm", "penis_girth_cm", "penis_erect_length_cm",
                "penis_erect_girth_cm", "breast_cup", "breast_band_size",
                "breast_shape", "grooming_level", "self_rating", "additional_notes"
            ]
            vault_fields = [c for c in sensitive_cols if full_vault.data.get(c)]

    # 清理敏感字段
    user_export = user_data.data or {}
    for key in ["consent_updated_at"]:  # 保留 consent 字段
        pass
    # 不导出密码哈希等认证字段（由 Supabase Auth 管理）

    export = DataExportResponse(
        user={k: v for k, v in user_export.items() if k not in ["id"]},
        profile=profile_data.data or {},
        ratings=[
            {k: v for k, v in r.items()
             if k not in ["genital_score_encrypted", "genital_score_iv"]}
            for r in (ratings_data.data or [])
        ],
        preferences=prefs_data.data or {},
        consent_history=consent_history.data or [],
        photo_hashes=[
            {k: v for k, v in p.items()} for p in (photo_hashes.data or [])
        ],
        vault_encrypted_fields=vault_fields,
        exported_at=datetime.now(timezone.utc).isoformat(),
    )

    # 审计
    sb.table("scoring_audit_log").insert({
        "user_id": uid,
        "action": "data_exported",
        "metadata": {"tables_included": ["users", "profiles", "ratings", "preferences", "consent_history", "photo_hashes"]},
    }).execute()

    return await build_response(
        success=True,
        message="个人数据导出完成",
        data=export.model_dump(),
        user_id=uid,
    )


# ================================================================
# DELETE /privacy/account — GDPR 被遗忘权
# ================================================================
@router.delete("/account", response_model=BaseResponse)
async def delete_account(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    永久删除用户账号和所有数据（GDPR 第 17 条 — 被遗忘权）

    此操作不可逆。调用数据库函数 fn_gdpr_delete_user_data 级联删除。
    """
    sb = get_supabase()
    uid = user.user_id
    client_ip = get_client_ip(request)
    request_id = generate_request_id()

    logger.warning(
        f"[PRIVACY] ⚠️⚠️ 账号删除请求 | user={uid} | "
        f"request_id={request_id} | ip={client_ip}"
    )

    # 调用 GDPR 删除函数
    try:
        result = sb.rpc("fn_gdpr_delete_user_data", {"target_user_id": uid}).execute()
        deletion_result = result.data
    except Exception as e:
        logger.error(f"[PRIVACY] 账号删除失败 | user={uid} | error={e}")
        raise HTTPException(status_code=500, detail="账号删除失败，请稍后重试")

    logger.warning(
        f"[PRIVACY] ⚠️ 账号已永久删除 | user={uid} | "
        f"result={deletion_result}"
    )

    return await build_response(
        success=True,
        message="账号已永久删除，所有数据已清除",
        data={"deleted": True, "request_id": request_id},
        user_id=uid,
    )
