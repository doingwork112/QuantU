"""
QuantifyU — Private Vault Pydantic模型（加密存储生殖器官数据）
"""

from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime


class VaultSaveRequest(BaseModel):
    """保存生殖器官自测数据（传入明文，后端加密存储）"""
    # 男性字段
    penis_length_cm: Optional[float] = None
    penis_girth_cm: Optional[float] = None
    penis_erect_length_cm: Optional[float] = None
    penis_erect_girth_cm: Optional[float] = None

    # 女性字段
    breast_cup: Optional[str] = None
    breast_band_size: Optional[float] = None
    breast_shape: Optional[str] = None

    # 通用
    grooming_level: Optional[int] = None
    self_rating: Optional[int] = None
    additional_notes: Optional[str] = None

    # 测量时间
    measured_at: Optional[datetime] = None

    @field_validator("penis_length_cm", "penis_erect_length_cm")
    @classmethod
    def validate_length(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (3.0 <= v <= 35.0):
            raise ValueError("长度范围: 3-35 cm")
        return v

    @field_validator("penis_girth_cm", "penis_erect_girth_cm")
    @classmethod
    def validate_girth(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (3.0 <= v <= 30.0):
            raise ValueError("周长范围: 3-30 cm")
        return v

    @field_validator("additional_notes")
    @classmethod
    def notes_length(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 1000:
            raise ValueError("备注不能超过1000字")
        return v


class VaultSaveResponse(BaseModel):
    vault_id: str
    encrypted_fields: list[str]     # 哪些字段被加密存储了
    encryption_algorithm: str       # "AES-256-GCM"
    key_version: int
    saved_at: datetime
