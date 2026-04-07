"""
QuantifyU — Supabase客户端（service_role，绕过RLS）
"""

from supabase import create_client, Client
from app.config import get_settings


def get_supabase() -> Client:
    """获取Supabase admin客户端（使用service_role key）"""
    settings = get_settings()
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
