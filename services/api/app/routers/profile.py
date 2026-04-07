"""
QuantifyU — 用户资料路由
POST /profile/update
GET  /profile/me
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger

from app.middleware.auth import AuthenticatedUser, get_current_user, get_client_ip
from app.schemas.profile import ProfileUpdateRequest, ProfileResponse
from app.schemas.base import BaseResponse
from app.services.supabase_client import get_supabase
from app.services.response_builder import build_response

router = APIRouter(prefix="/profile", tags=["用户资料"])


@router.post("/update", response_model=BaseResponse)
async def update_profile(
    body: ProfileUpdateRequest,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    更新用户资料
    支持部分更新（仅传入需要修改的字段）
    """
    client_ip = get_client_ip(request)
    logger.info(f"资料更新 | user={user.user_id} | ip={client_ip}")

    sb = get_supabase()

    # 构建更新字段（排除None值）
    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="至少提供一个需要更新的字段",
        )

    # 处理地理坐标
    lat = update_data.pop("latitude", None)
    lng = update_data.pop("longitude", None)
    if lat is not None and lng is not None:
        update_data["location"] = f"POINT({lng} {lat})"

    # 执行更新
    try:
        resp = (
            sb.table("profiles")
            .update(update_data)
            .eq("user_id", user.user_id)
            .execute()
        )
    except Exception as e:
        logger.error(f"更新profile失败 | user={user.user_id} | error={e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新资料失败",
        )

    if not resp.data:
        # profile不存在，创建一条
        update_data["user_id"] = user.user_id
        try:
            sb.table("profiles").insert(update_data).execute()
        except Exception as e:
            logger.error(f"创建profile失败 | user={user.user_id} | error={e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="创建资料失败",
            )

    updated_fields = list(body.model_dump(exclude_none=True).keys())
    logger.info(
        f"资料已更新 | user={user.user_id} | fields={updated_fields}"
    )

    return await build_response(
        success=True,
        message=f"资料已更新: {', '.join(updated_fields)}",
        data={"updated_fields": updated_fields},
        user_id=user.user_id,
    )


@router.get("/me", response_model=BaseResponse)
async def get_my_profile(
    user: AuthenticatedUser = Depends(get_current_user),
):
    """获取当前用户的完整资料"""
    sb = get_supabase()

    # 联合查询users和profiles
    user_resp = (
        sb.table("users")
        .select("display_name")
        .eq("id", user.user_id)
        .single()
        .execute()
    )

    profile_resp = (
        sb.table("profiles")
        .select("*")
        .eq("user_id", user.user_id)
        .maybe_single()
        .execute()
    )

    if not profile_resp.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户资料不存在，请先完善资料",
        )

    p = profile_resp.data
    profile = ProfileResponse(
        user_id=user.user_id,
        display_name=user_resp.data.get("display_name", ""),
        height_cm=p.get("height_cm"),
        weight_kg=p.get("weight_kg"),
        body_fat_pct=p.get("body_fat_pct"),
        ethnicity=p.get("ethnicity"),
        hair_color=p.get("hair_color"),
        eye_color=p.get("eye_color"),
        avatar_url=p.get("avatar_url"),
        photo_urls=p.get("photo_urls") or [],
        bio=p.get("bio"),
        looking_for=p.get("looking_for") or [],
        city=p.get("city"),
        country=p.get("country"),
        latest_overall_score=p.get("latest_overall_score"),
        score_updated_at=p.get("score_updated_at"),
        created_at=p.get("created_at"),
    )

    return await build_response(
        success=True,
        message="获取资料成功",
        data=profile.model_dump(),
        user_id=user.user_id,
    )
