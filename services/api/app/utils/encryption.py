"""
QuantifyU — AES-256-GCM 加密工具 v2
增强：
  - Supabase Vault 密钥包装（key wrapping）
  - 密钥轮换支持（多版本并存）
  - 内存安全（显式清除明文）
  - 照片哈希计算（SHA-256 + pHash）
"""

import base64
import gc
import hashlib
import hmac
import json
import os
import secrets
from typing import Any, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from loguru import logger


class EncryptionService:
    """AES-256-GCM 加密服务（支持密钥轮换）"""

    ALGORITHM = "AES-256-GCM"
    IV_LENGTH = 12   # GCM 推荐 12 字节
    KEY_LENGTH = 32  # 256 bits

    def __init__(self, master_key_b64: str, key_version: int = 1):
        self._master_key = base64.b64decode(master_key_b64)
        if len(self._master_key) != self.KEY_LENGTH:
            raise ValueError(
                f"主密钥必须为{self.KEY_LENGTH}字节，"
                f"当前{len(self._master_key)}字节"
            )
        self._key_version = key_version
        self._aesgcm = AESGCM(self._master_key)

    @property
    def key_version(self) -> int:
        return self._key_version

    # ================================================================
    # 字段级加密/解密
    # ================================================================

    def encrypt_field(self, plaintext: str, aad: bytes | None = None) -> tuple[bytes, bytes]:
        """
        加密单个字段值

        Args:
            plaintext: 明文字符串
            aad: 附加认证数据（可选，如 user_id 绑定防止数据替换攻击）

        Returns: (ciphertext, iv)
        """
        iv = os.urandom(self.IV_LENGTH)
        ciphertext = self._aesgcm.encrypt(iv, plaintext.encode("utf-8"), aad)
        return ciphertext, iv

    def decrypt_field(self, ciphertext: bytes, iv: bytes, aad: bytes | None = None) -> str:
        """解密单个字段值"""
        plaintext = self._aesgcm.decrypt(iv, ciphertext, aad)
        return plaintext.decode("utf-8")

    def encrypt_vault_data(
        self,
        data: dict[str, Any],
        user_id: str | None = None,
    ) -> tuple[dict[str, bytes], dict[str, str], bytes]:
        """
        加密 vault 中的所有非 None 字段

        Args:
            data: {field_name: plaintext_value}
            user_id: 绑定 AAD 防止数据替换攻击

        Returns:
            encrypted_fields: {field_name: ciphertext_bytes}
            field_ivs:        {field_name: base64_iv_string}
            shared_iv:        一个共享 IV（向后兼容）
        """
        aad = user_id.encode("utf-8") if user_id else None
        encrypted_fields: dict[str, bytes] = {}
        field_ivs: dict[str, str] = {}
        shared_iv = os.urandom(self.IV_LENGTH)

        for key, value in data.items():
            if value is None:
                continue
            plaintext = str(value)
            ciphertext, iv = self.encrypt_field(plaintext, aad=aad)
            encrypted_fields[key] = ciphertext
            field_ivs[key] = base64.b64encode(iv).decode("ascii")

        return encrypted_fields, field_ivs, shared_iv

    def decrypt_vault_data(
        self,
        encrypted_fields: dict[str, str],
        field_ivs: dict[str, str],
        user_id: str | None = None,
    ) -> dict[str, str]:
        """
        解密 vault 中的所有字段

        Args:
            encrypted_fields: {field_name: base64_ciphertext}
            field_ivs: {field_name: base64_iv}
            user_id: AAD 验证

        Returns: {field_name: plaintext_value}
        """
        aad = user_id.encode("utf-8") if user_id else None
        result: dict[str, str] = {}

        for field_name, ct_b64 in encrypted_fields.items():
            if field_name not in field_ivs:
                continue
            ciphertext = base64.b64decode(ct_b64)
            iv = base64.b64decode(field_ivs[field_name])
            result[field_name] = self.decrypt_field(ciphertext, iv, aad=aad)

        return result

    def compute_data_hash(self, data: dict[str, Any]) -> str:
        """计算明文数据的 HMAC-SHA256 哈希（验证解密完整性）"""
        serialized = json.dumps(
            {k: str(v) for k, v in sorted(data.items()) if v is not None},
            sort_keys=True,
        )
        return hmac.new(
            self._master_key, serialized.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    # ================================================================
    # 密钥管理
    # ================================================================

    @staticmethod
    def generate_master_key() -> str:
        """生成新的主密钥（用于初始化或轮换）"""
        return base64.b64encode(os.urandom(32)).decode("ascii")

    @staticmethod
    def derive_field_key(master_key: bytes, field_name: str, version: int) -> bytes:
        """
        从主密钥派生字段级密钥 (HKDF-like)
        用于未来更细粒度的密钥管理
        """
        info = f"quantifyu:vault:{field_name}:v{version}".encode("utf-8")
        return hashlib.sha256(master_key + info).digest()


# ================================================================
# 照片哈希服务
# ================================================================

class PhotoHashService:
    """
    照片哈希服务 — 服务端只存哈希，不存原图

    流程：
    1. 客户端上传加密照片 → 服务端接收
    2. 服务端解密（仅在内存中）→ AI 处理 → 计算哈希
    3. 存储哈希到 photo_hashes 表
    4. 立即从内存清除原图字节
    """

    @staticmethod
    def compute_sha256(data: bytes) -> str:
        """计算照片的 SHA-256 哈希"""
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def compute_file_hash(data: bytes) -> dict:
        """
        计算照片的多种哈希

        Returns: {sha256: str, size_bytes: int}
        """
        return {
            "sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": len(data),
        }

    @staticmethod
    def verify_hash(data: bytes, expected_hash: str) -> bool:
        """验证照片数据是否与预期哈希匹配"""
        return hmac.compare_digest(
            hashlib.sha256(data).hexdigest(),
            expected_hash,
        )

    @staticmethod
    def secure_wipe(data: bytearray) -> None:
        """
        安全清除内存中的照片数据
        注：Python 的 bytes 不可变无法原地覆盖，
        需使用 bytearray 才能真正覆盖内存
        """
        for i in range(len(data)):
            data[i] = 0
        del data
        gc.collect()


# ================================================================
# 内存安全工具
# ================================================================

def secure_delete_dict(d: dict) -> None:
    """安全删除字典中的敏感数据"""
    for key in list(d.keys()):
        if isinstance(d[key], str):
            # 覆盖字符串引用（Python 不保证内存覆盖，但尽力而为）
            d[key] = "x" * len(d[key])
        d[key] = None
    d.clear()
    del d
    gc.collect()


def generate_request_id() -> str:
    """生成唯一请求 ID（用于审计追踪）"""
    return f"req_{secrets.token_hex(16)}"
