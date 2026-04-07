"""
QuantifyU — 用户资料Pydantic模型
"""

from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime


class ProfileUpdateRequest(BaseModel):
    """更新用户资料"""
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    body_fat_pct: Optional[float] = None
    ethnicity: Optional[str] = None
    hair_color: Optional[str] = None
    eye_color: Optional[str] = None
    avatar_url: Optional[str] = None
    photo_urls: Optional[list[str]] = None
    bio: Optional[str] = None
    looking_for: Optional[list[str]] = None
    city: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    @field_validator("bio")
    @classmethod
    def bio_length(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 500:
            raise ValueError("简介不能超过500字")
        return v

    @field_validator("looking_for")
    @classmethod
    def valid_looking_for(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is not None:
            allowed = {"relationship", "casual", "friends"}
            for item in v:
                if item not in allowed:
                    raise ValueError(f"looking_for 选项必须为: {allowed}")
        return v


class ProfileResponse(BaseModel):
    user_id: str
    display_name: str
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    body_fat_pct: Optional[float] = None
    ethnicity: Optional[str] = None
    hair_color: Optional[str] = None
    eye_color: Optional[str] = None
    avatar_url: Optional[str] = None
    photo_urls: list[str] = []
    bio: Optional[str] = None
    looking_for: list[str] = []
    city: Optional[str] = None
    country: Optional[str] = None
    latest_overall_score: Optional[float] = None
    score_updated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
