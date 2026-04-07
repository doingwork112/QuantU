"""
QuantifyU — 测试配置
"""

import os
import base64
import pytest

# 设置测试环境变量（在导入 app 之前）
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-at-least-32-chars-long")
os.environ.setdefault("ENCRYPTION_MASTER_KEY", base64.b64encode(os.urandom(32)).decode())
os.environ.setdefault("ENCRYPTION_KEY_VERSION", "1")
os.environ.setdefault("API_ENV", "test")
os.environ.setdefault("MODEL_DEVICE", "cpu")
os.environ.setdefault("VIT_FBP_MODEL_PATH", "./app/ai/models/vit_fbp.pth")


@pytest.fixture
def encryption_key():
    """生成一个测试用加密密钥"""
    return base64.b64encode(os.urandom(32)).decode()
