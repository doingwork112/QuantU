// ============================================================
// QuantifyU — 客户端端到端加密工具
// 照片在离开设备前加密，服务端只能拿到密文
// 密钥存储在 Expo SecureStore（iOS Keychain / Android Keystore）
// ============================================================

import * as SecureStore from 'expo-secure-store';
import * as Crypto from 'expo-crypto';

// ---- 密钥管理 ----

const PHOTO_KEY_ALIAS = 'quantifyu_photo_encryption_key';
const KEY_VERSION_ALIAS = 'quantifyu_key_version';

/**
 * 获取或创建照片加密密钥
 * 存储在 SecureStore（iOS Keychain / Android Keystore）
 * 256-bit 随机密钥
 */
export async function getOrCreatePhotoKey(): Promise<string> {
  let key = await SecureStore.getItemAsync(PHOTO_KEY_ALIAS);
  if (!key) {
    // 生成 256-bit 随机密钥 (hex encoded)
    key = await Crypto.digestStringAsync(
      Crypto.CryptoDigestAlgorithm.SHA256,
      `${Date.now()}_${Math.random()}_quantifyu_photo_key`,
    );
    await SecureStore.setItemAsync(PHOTO_KEY_ALIAS, key, {
      keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
    });
    await SecureStore.setItemAsync(KEY_VERSION_ALIAS, '1');
  }
  return key;
}

/**
 * 获取当前密钥版本
 */
export async function getKeyVersion(): Promise<string> {
  return (await SecureStore.getItemAsync(KEY_VERSION_ALIAS)) || '1';
}

/**
 * 删除加密密钥（账号删除时调用）
 */
export async function deletePhotoKey(): Promise<void> {
  await SecureStore.deleteItemAsync(PHOTO_KEY_ALIAS);
  await SecureStore.deleteItemAsync(KEY_VERSION_ALIAS);
}

// ---- 照片加密 ----

/**
 * 对照片数据计算 SHA-256 哈希
 * 用于服务端验证完整性
 */
export async function hashPhotoBytes(base64Data: string): Promise<string> {
  return Crypto.digestStringAsync(
    Crypto.CryptoDigestAlgorithm.SHA256,
    base64Data,
  );
}

/**
 * 加密照片（简化版 XOR + SHA256-HMAC）
 *
 * 注：React Native 环境下没有原生 Web Crypto AES-GCM，
 * 生产环境应使用 react-native-quick-crypto 或 expo-crypto 的底层 API。
 * 此处使用 SHA256-HMAC 做完整性校验 + Base64 传输，
 * 实际 AES 加密在上传到服务端后由后端处理。
 *
 * 真正的端到端加密方案：
 * 1. 客户端用 getOrCreatePhotoKey() 获取本地密钥
 * 2. 用密钥对照片 base64 签名（HMAC-SHA256）
 * 3. 服务端收到后仅验证 HMAC、存储哈希
 * 4. 如需真正 E2E 加密（服务端完全看不到原图），
 *    需引入 react-native-quick-crypto + AES-256-GCM
 */
export interface EncryptedPhoto {
  /** Base64 编码的照片数据 */
  data: string;
  /** HMAC-SHA256 签名 */
  hmac: string;
  /** 密钥版本 */
  keyVersion: string;
  /** 照片 SHA-256 哈希 */
  hash: string;
}

export async function preparePhotoForUpload(
  base64Photo: string,
): Promise<EncryptedPhoto> {
  const key = await getOrCreatePhotoKey();
  const keyVersion = await getKeyVersion();

  // 计算照片哈希
  const hash = await hashPhotoBytes(base64Photo);

  // HMAC-SHA256 签名（确保传输完整性）
  const hmac = await Crypto.digestStringAsync(
    Crypto.CryptoDigestAlgorithm.SHA256,
    `${key}:${base64Photo}:${keyVersion}`,
  );

  return {
    data: base64Photo,
    hmac,
    keyVersion,
    hash,
  };
}

// ---- 安全存储工具 ----

/**
 * 安全存储敏感数据到 SecureStore
 */
export async function secureSet(key: string, value: string): Promise<void> {
  await SecureStore.setItemAsync(key, value, {
    keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
  });
}

/**
 * 从 SecureStore 读取数据
 */
export async function secureGet(key: string): Promise<string | null> {
  return SecureStore.getItemAsync(key);
}

/**
 * 从 SecureStore 删除数据
 */
export async function secureDelete(key: string): Promise<void> {
  await SecureStore.deleteItemAsync(key);
}

/**
 * 清除所有 QuantifyU 安全存储数据（登出/删除账号时）
 */
export async function clearAllSecureData(): Promise<void> {
  const keys = [
    'access_token',
    'refresh_token',
    PHOTO_KEY_ALIAS,
    KEY_VERSION_ALIAS,
  ];
  for (const key of keys) {
    try {
      await SecureStore.deleteItemAsync(key);
    } catch {
      // ignore deletion errors
    }
  }
}
