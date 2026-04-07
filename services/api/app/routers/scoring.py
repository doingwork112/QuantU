"""
QuantifyU — 评分路由 (v2)
POST /rating/calculate
  接收照片URL + 身体数据 + 自测数据
  → ViT-FBP面部 + MediaPipe身材 + 规则身高 + 纯数值生殖器官
  → 返回 {"total_score": 85.5, "breakdown": {...}, "percentile": "top 15%"}
"""

import base64
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger

from app.middleware.auth import AuthenticatedUser, get_current_user, get_client_ip
from app.schemas.scoring import (
    CalculateScoreRequest,
    ScoreBreakdown,
    ScoreResponse,
    FaceDetail,
    BodyDetail,
    HeightDetail,
    SkinHairDetail,
    GenitalDetail,
)
from app.schemas.base import BaseResponse
from app.services.ai_scorer import LooksmaxxingEngine
from app.services.supabase_client import get_supabase
from app.services.response_builder import build_response
from app.utils.encryption import EncryptionService
from app.config import get_settings

router = APIRouter(prefix="/rating", tags=["评分"])

# ================================================================
# 评分引擎单例 (应用启动时初始化)
# ================================================================
_engine: LooksmaxxingEngine | None = None


def get_engine() -> LooksmaxxingEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = LooksmaxxingEngine(
            vit_model_path=settings.VIT_FBP_MODEL_PATH,
            device=settings.MODEL_DEVICE,
        )
        logger.info(
            f"LooksmaxxingEngine已创建 | "
            f"model_loaded={_engine.is_model_loaded} | "
            f"device={settings.MODEL_DEVICE}"
        )
    return _engine


# ================================================================
# POST /rating/calculate
# ================================================================
@router.post("/calculate", response_model=BaseResponse)
async def calculate_score(
    body: CalculateScoreRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    AI Looksmaxxing 评分

    流程:
    1. 验证consent (ai_scoring + genital_data)
    2. 调用LooksmaxxingEngine五维评分
    3. 加密生殖器官分数
    4. 写入ratings表 (DB触发器自动计算总分/同步profile)
    5. 记录审计日志
    6. 返回 total_score + breakdown + percentile

    请求体:
    - face_photo_url: 正面面部照片 (必须)
    - body_photo_url: 正面全身照 (可选, 有则做MediaPipe Pose分析)
    - body_side_photo_url: 侧面全身照 (可选, 有则做体态检测)
    - height_cm: 身高
    - weight_kg: 体重 (可选)
    - ethnicity: 族裔 (可选, "chinese"/"korean"等触发东亚脸优化)
    - self_measurements: 生殖器官自测数值 (可选, 仅数值评分非AI)
    """
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "unknown")
    logger.info(
        f"评分请求 | user={user.user_id} | ip={client_ip} | "
        f"face={body.face_photo_url[:50]}... | "
        f"body={'有' if body.body_photo_url else '无'} | "
        f"side={'有' if body.body_side_photo_url else '无'} | "
        f"ethnicity={body.ethnicity}"
    )

    sb = get_supabase()
    settings = get_settings()

    # ==== 1. 验证consent ====
    try:
        user_resp = (
            sb.table("users")
            .select("consent_ai_scoring, consent_genital_data, gender")
            .eq("id", user.user_id)
            .single()
            .execute()
        )
    except Exception as e:
        logger.error(f"查询用户失败 | user={user.user_id} | error={e}")
        raise HTTPException(status_code=500, detail="查询用户信息失败")

    user_data = user_resp.data
    if not user_data:
        raise HTTPException(status_code=404, detail="用户不存在")

    if not user_data.get("consent_ai_scoring"):
        logger.warning(f"用户未同意AI评分 | user={user.user_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="请先在设置中同意AI评分条款 (consent_ai_scoring=true)",
        )

    gender = user_data.get("gender", "male")
    has_genital_consent = user_data.get("consent_genital_data", False)

    # ==== 2. 提取自测数据 ====
    sm = body.self_measurements
    genital_kwargs: dict = {}
    if sm:
        if not has_genital_consent:
            logger.warning(
                f"用户提交了生殖器官数据但未同意consent | user={user.user_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="提交生殖器官数据需要先同意隐私条款 (consent_genital_data=true)",
            )
        genital_kwargs = {
            "penis_length_cm": sm.penis_length_cm,
            "penis_girth_cm": sm.penis_girth_cm,
            "breast_cup": sm.breast_cup,
            "grooming_level": sm.grooming_level,
            "self_rating": sm.self_rating,
        }

    # ==== 3. AI评分 ====
    engine = get_engine()
    try:
        scores = await engine.calculate(
            face_photo_url=body.face_photo_url,
            height_cm=body.height_cm,
            gender=gender,
            ethnicity=body.ethnicity,
            body_photo_url=body.body_photo_url,
            body_side_photo_url=body.body_side_photo_url,
            weight_kg=body.weight_kg,
            **genital_kwargs,
        )
    except Exception as e:
        logger.error(
            f"AI评分引擎异常 | user={user.user_id} | "
            f"type={type(e).__name__} | error={e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI评分服务暂时不可用，请稍后重试",
        )

    total = scores["total_score"]
    logger.info(
        f"评分完成 | user={user.user_id} | total={total}/100 | "
        f"percentile={scores['percentile']}"
    )

    # ==== 4. 加密生殖器官分数 ====
    encrypted_genital = None
    genital_iv = None
    try:
        crypto = EncryptionService(
            settings.ENCRYPTION_MASTER_KEY, settings.ENCRYPTION_KEY_VERSION
        )
        genital_ct, genital_iv_bytes = crypto.encrypt_field(
            str(scores["genital_score"])
        )
        encrypted_genital = base64.b64encode(genital_ct).decode()
        genital_iv = base64.b64encode(genital_iv_bytes).decode()
    except Exception as e:
        logger.error(f"加密genital_score失败 | user={user.user_id} | error={e}")

    # ==== 5. 写入ratings表 ====
    rating_row = {
        "user_id": user.user_id,
        "face_score": scores["face_score"],
        "height_score": scores["height_score"],
        "body_score": scores["body_score"],
        "genital_score": scores["genital_score"],
        "skin_hair_score": scores["skin_hair_score"],
        "scoring_model_version": scores["model_version"],
        "face_photo_url": body.face_photo_url,
        "body_photo_url": body.body_photo_url,
        "ai_feedback": {
            "face": scores["face_feedback"],
            "height": scores["height_feedback"],
            "body": scores["body_feedback"],
            "skin_hair": scores["skin_hair_feedback"],
            "genital": scores["genital_feedback"],
            "breakdown": scores["breakdown"],
            "improvement_tips": scores["improvement_tips"],
            "east_asian_notes": scores["east_asian_notes"],
            "percentile": scores["percentile"],
        },
    }
    if encrypted_genital:
        rating_row["genital_score_encrypted"] = encrypted_genital
        rating_row["genital_score_iv"] = genital_iv
        rating_row["genital_score_key_version"] = settings.ENCRYPTION_KEY_VERSION

    try:
        insert_resp = sb.table("ratings").insert(rating_row).execute()
        rating_id = insert_resp.data[0]["id"]
    except Exception as e:
        logger.error(f"写入ratings失败 | user={user.user_id} | error={e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="保存评分记录失败",
        )

    # ==== 6. 审计日志 ====
    try:
        sb.table("scoring_audit_log").insert({
            "user_id": user.user_id,
            "rating_id": rating_id,
            "action": "score_created",
            "ip_address": client_ip,
            "user_agent": user_agent,
            "metadata": {
                "total_score": total,
                "percentile": scores["percentile"],
                "model_version": scores["model_version"],
                "has_body_photo": bool(body.body_photo_url),
                "has_side_photo": bool(body.body_side_photo_url),
                "has_genital_data": bool(genital_kwargs),
                "genital_encrypted": bool(encrypted_genital),
                "ethnicity": body.ethnicity,
                "is_east_asian": bool(scores.get("east_asian_notes")),
            },
        }).execute()
    except Exception as e:
        logger.warning(f"审计日志写入失败（非致命） | user={user.user_id} | error={e}")

    # ==== 7. 构建响应 ====
    bd = scores["breakdown"]

    breakdown = ScoreBreakdown(
        face=FaceDetail(**bd["face"]),
        body=BodyDetail(**bd["body"]),
        height=HeightDetail(**bd["height"]),
        skin_hair=SkinHairDetail(**bd["skin_hair"]),
        genital=GenitalDetail(**bd["genital"]),
    )

    score_data = ScoreResponse(
        rating_id=rating_id,
        total_score=total,
        percentile=scores["percentile"],
        score_label=scores["score_label"],
        breakdown=breakdown,
        face_feedback=scores["face_feedback"],
        body_feedback=scores["body_feedback"],
        height_feedback=scores["height_feedback"],
        skin_hair_feedback=scores["skin_hair_feedback"],
        genital_feedback=scores["genital_feedback"],
        improvement_tips=scores["improvement_tips"],
        east_asian_notes=scores["east_asian_notes"],
        model_version=scores["model_version"],
    )

    logger.info(
        f"评分响应 | user={user.user_id} | rating_id={rating_id} | "
        f"total={total}/100 | percentile={scores['percentile']}"
    )

    return await build_response(
        success=True,
        message=(
            f"AI评分完成: {total}/100 "
            f"({scores['score_label']}, {scores['percentile']})"
        ),
        data=score_data.model_dump(),
        user_id=user.user_id,
    )
