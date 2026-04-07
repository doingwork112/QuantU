"""
QuantifyU — 认证相关Pydantic模型
"""

from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import date


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str
    date_of_birth: date
    gender: str  # male | female | non-binary | other

    # 必须同意的条款
    consent_terms_of_service: bool
    consent_privacy_policy: bool
    consent_ai_scoring: bool = False
    consent_genital_data: bool = False

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("密码至少8位")
        if not any(c.isdigit() for c in v):
            raise ValueError("密码必须包含数字")
        if not any(c.isalpha() for c in v):
            raise ValueError("密码必须包含字母")
        return v

    @field_validator("gender")
    @classmethod
    def valid_gender(cls, v: str) -> str:
        allowed = {"male", "female", "non-binary", "other"}
        if v not in allowed:
            raise ValueError(f"gender必须为: {allowed}")
        return v

    @field_validator("consent_terms_of_service", "consent_privacy_policy")
    @classmethod
    def must_consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("必须同意服务条款和隐私政策")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    user_id: str
    email: str
    access_token: str
    refresh_token: str
    display_name: str
    has_profile: bool = False
    has_scores: bool = False
