"""
QuantifyU — 应用配置（从环境变量加载）
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # --- Supabase ---
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str  # 后端专用，绕过RLS
    SUPABASE_JWT_SECRET: str

    # --- API ---
    API_ENV: str = "development"
    API_CORS_ORIGINS: str = "http://localhost:8081"

    # --- 加密 ---
    ENCRYPTION_MASTER_KEY: str  # base64编码的32字节密钥
    ENCRYPTION_KEY_VERSION: int = 1

    # --- AI模型 ---
    MODEL_DEVICE: str = "cpu"  # cpu | cuda | mps
    VIT_FBP_MODEL_PATH: str = "./app/ai/models/vit_fbp.pth"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
