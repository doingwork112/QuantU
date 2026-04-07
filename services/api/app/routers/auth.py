"""
QuantifyU — 认证路由
POST /auth/signup
POST /auth/login
"""

from fastapi import APIRouter, HTTPException, Request, status
from loguru import logger

from app.schemas.auth import SignupRequest, LoginRequest, AuthResponse
from app.schemas.base import BaseResponse
from app.services.supabase_client import get_supabase
from app.services.response_builder import build_response
from app.middleware.auth import get_client_ip

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/signup", response_model=BaseResponse, status_code=201)
async def signup(body: SignupRequest, request: Request):
    """
    用户注册
    1. 通过Supabase Auth创建账号
    2. 在users表写入基础信息和consent flags
    3. 创建空的profiles和user_preferences记录
    """
    client_ip = get_client_ip(request)
    logger.info(f"注册请求 | email={body.email} | ip={client_ip}")

    sb = get_supabase()

    # 1. Supabase Auth注册
    try:
        auth_resp = sb.auth.sign_up({
            "email": body.email,
            "password": body.password,
        })
    except Exception as e:
        logger.error(f"Supabase Auth注册失败 | email={body.email} | error={e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"注册失败: {str(e)}",
        )

    if not auth_resp.user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="注册失败，请检查邮箱是否已被使用",
        )

    user_id = auth_resp.user.id
    logger.info(f"Auth账号创建成功 | user_id={user_id}")

    # 2. 写入users表
    try:
        sb.table("users").insert({
            "id": user_id,
            "email": body.email,
            "display_name": body.display_name,
            "date_of_birth": body.date_of_birth.isoformat(),
            "gender": body.gender,
            "consent_terms_of_service": body.consent_terms_of_service,
            "consent_privacy_policy": body.consent_privacy_policy,
            "consent_ai_scoring": body.consent_ai_scoring,
            "consent_genital_data": body.consent_genital_data,
        }).execute()
    except Exception as e:
        logger.error(f"写入users表失败 | user_id={user_id} | error={e}")
        # 回滚：删除Auth账号
        try:
            sb.auth.admin.delete_user(user_id)
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建用户记录失败",
        )

    # 3. 创建空profile和默认preferences
    try:
        sb.table("profiles").insert({
            "user_id": user_id,
        }).execute()

        sb.table("user_preferences").insert({
            "user_id": user_id,
        }).execute()
    except Exception as e:
        logger.warning(f"创建关联记录失败（非致命） | user_id={user_id} | error={e}")

    # 4. 自动登录获取token
    try:
        login_resp = sb.auth.sign_in_with_password({
            "email": body.email,
            "password": body.password,
        })
        access_token = login_resp.session.access_token
        refresh_token = login_resp.session.refresh_token
    except Exception:
        access_token = ""
        refresh_token = ""

    logger.info(f"注册完成 | user_id={user_id} | email={body.email}")

    auth_data = AuthResponse(
        user_id=user_id,
        email=body.email,
        access_token=access_token,
        refresh_token=refresh_token,
        display_name=body.display_name,
        has_profile=False,
        has_scores=False,
    )

    return await build_response(
        success=True,
        message="注册成功",
        data=auth_data.model_dump(),
        user_id=user_id,
    )


@router.post("/login", response_model=BaseResponse)
async def login(body: LoginRequest, request: Request):
    """
    用户登录
    返回JWT Token + 用户基础信息 + AI参考分 + 匹配兼容度
    """
    client_ip = get_client_ip(request)
    logger.info(f"登录请求 | email={body.email} | ip={client_ip}")

    sb = get_supabase()

    try:
        auth_resp = sb.auth.sign_in_with_password({
            "email": body.email,
            "password": body.password,
        })
    except Exception as e:
        logger.warning(f"登录失败 | email={body.email} | ip={client_ip} | error={e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
        )

    if not auth_resp.user or not auth_resp.session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
        )

    user_id = auth_resp.user.id

    # 查询用户附加信息
    user_resp = (
        sb.table("users")
        .select("display_name")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    display_name = user_resp.data.get("display_name", "") if user_resp.data else ""

    # 检查是否有profile和评分
    profile_resp = (
        sb.table("profiles")
        .select("latest_overall_score")
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    has_profile = bool(profile_resp.data and profile_resp.data.get("height_cm"))
    has_scores = bool(
        profile_resp.data and profile_resp.data.get("latest_overall_score")
    )

    logger.info(f"登录成功 | user_id={user_id} | email={body.email}")

    auth_data = AuthResponse(
        user_id=user_id,
        email=body.email,
        access_token=auth_resp.session.access_token,
        refresh_token=auth_resp.session.refresh_token,
        display_name=display_name,
        has_profile=has_profile,
        has_scores=has_scores,
    )

    return await build_response(
        success=True,
        message="登录成功",
        data=auth_data.model_dump(),
        user_id=user_id,
    )
