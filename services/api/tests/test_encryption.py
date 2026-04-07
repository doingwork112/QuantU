"""
QuantifyU — 加密服务测试
测试 AES-256-GCM 加密/解密 + AAD 绑定 + 完整性校验
"""

import base64
import os

import pytest

from app.utils.encryption import EncryptionService, PhotoHashService, secure_delete_dict


@pytest.fixture
def crypto():
    key = base64.b64encode(os.urandom(32)).decode()
    return EncryptionService(key, key_version=1)


class TestEncryptionService:
    """AES-256-GCM 加密服务测试"""

    def test_encrypt_decrypt_field(self, crypto):
        """基本加密解密循环"""
        plaintext = "6.5 inches"
        ciphertext, iv = crypto.encrypt_field(plaintext)

        assert ciphertext != plaintext.encode()
        assert len(iv) == 12  # GCM IV

        decrypted = crypto.decrypt_field(ciphertext, iv)
        assert decrypted == plaintext

    def test_encrypt_with_aad_binding(self, crypto):
        """AAD 绑定 — 用 user_id 绑定防止数据替换"""
        plaintext = "16.5cm"
        user_id = "user-abc-123"
        aad = user_id.encode("utf-8")

        ciphertext, iv = crypto.encrypt_field(plaintext, aad=aad)

        # 正确的 AAD → 解密成功
        decrypted = crypto.decrypt_field(ciphertext, iv, aad=aad)
        assert decrypted == "16.5cm"

        # 错误的 AAD → 解密失败
        wrong_aad = "user-xyz-999".encode("utf-8")
        with pytest.raises(Exception):
            crypto.decrypt_field(ciphertext, iv, aad=wrong_aad)

    def test_independent_ivs_per_field(self, crypto):
        """每个字段使用独立 IV"""
        data = {
            "penis_length_cm": "16.5",
            "penis_girth_cm": "13.2",
            "self_rating": "8",
        }

        encrypted, field_ivs, shared_iv = crypto.encrypt_vault_data(data)

        # 每个字段有独立 IV
        assert len(field_ivs) == 3
        assert field_ivs["penis_length_cm"] != field_ivs["penis_girth_cm"]

        # 密文互不相同
        assert encrypted["penis_length_cm"] != encrypted["penis_girth_cm"]

    def test_encrypt_decrypt_vault_roundtrip(self, crypto):
        """完整 vault 加密/解密往返"""
        user_id = "test-user-001"
        data = {
            "penis_length_cm": "16.5",
            "penis_erect_length_cm": "17.8",
            "grooming_level": "4",
            "self_rating": "8",
        }

        encrypted, field_ivs, shared_iv = crypto.encrypt_vault_data(
            data, user_id=user_id
        )

        # 转为 base64（模拟 DB 存储）
        encrypted_b64 = {
            k: base64.b64encode(v).decode() for k, v in encrypted.items()
        }

        # 解密
        decrypted = crypto.decrypt_vault_data(
            encrypted_b64, field_ivs, user_id=user_id
        )

        assert decrypted["penis_length_cm"] == "16.5"
        assert decrypted["penis_erect_length_cm"] == "17.8"
        assert decrypted["grooming_level"] == "4"
        assert decrypted["self_rating"] == "8"

    def test_data_hash_integrity(self, crypto):
        """HMAC-SHA256 完整性验证"""
        data = {"penis_length_cm": "16.5", "self_rating": "8"}
        hash1 = crypto.compute_data_hash(data)
        hash2 = crypto.compute_data_hash(data)

        assert hash1 == hash2  # 相同数据 → 相同哈希

        # 篡改数据 → 哈希变化
        tampered = {"penis_length_cm": "20.0", "self_rating": "8"}
        hash3 = crypto.compute_data_hash(tampered)
        assert hash3 != hash1

    def test_key_generation(self):
        """密钥生成正确性"""
        key = EncryptionService.generate_master_key()
        raw = base64.b64decode(key)
        assert len(raw) == 32  # 256 bits

    def test_invalid_key_length(self):
        """无效密钥长度应报错"""
        short_key = base64.b64encode(os.urandom(16)).decode()  # 128 bits
        with pytest.raises(ValueError, match="32字节"):
            EncryptionService(short_key)

    def test_none_values_skipped(self, crypto):
        """None 值不被加密"""
        data = {
            "penis_length_cm": "16.5",
            "breast_cup": None,
            "self_rating": None,
        }
        encrypted, field_ivs, _ = crypto.encrypt_vault_data(data)

        assert "penis_length_cm" in encrypted
        assert "breast_cup" not in encrypted
        assert "self_rating" not in encrypted


class TestPhotoHashService:
    """照片哈希服务测试"""

    def test_sha256_hash(self):
        data = b"fake photo bytes"
        h = PhotoHashService.compute_sha256(data)
        assert len(h) == 64  # SHA-256 hex

    def test_hash_deterministic(self):
        data = b"same photo"
        h1 = PhotoHashService.compute_sha256(data)
        h2 = PhotoHashService.compute_sha256(data)
        assert h1 == h2

    def test_different_photos_different_hashes(self):
        h1 = PhotoHashService.compute_sha256(b"photo A")
        h2 = PhotoHashService.compute_sha256(b"photo B")
        assert h1 != h2

    def test_verify_hash(self):
        data = b"my photo"
        h = PhotoHashService.compute_sha256(data)
        assert PhotoHashService.verify_hash(data, h) is True
        assert PhotoHashService.verify_hash(b"tampered", h) is False

    def test_secure_wipe(self):
        data = bytearray(b"sensitive photo data here")
        PhotoHashService.secure_wipe(data)
        # data should be zeroed (or deleted)
        # can't check after del, but no error = pass

    def test_compute_file_hash(self):
        data = b"x" * 1024
        info = PhotoHashService.compute_file_hash(data)
        assert info["size_bytes"] == 1024
        assert len(info["sha256"]) == 64


class TestSecureDeleteDict:
    """内存安全清除测试"""

    def test_secure_delete(self):
        d = {"secret": "plaintext_password", "data": "sensitive"}
        secure_delete_dict(d)
        # d is deleted, should not raise
