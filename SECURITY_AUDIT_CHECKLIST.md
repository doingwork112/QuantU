# QuantifyU — 安全审计 Checklist

> 最高级别隐私保护审计清单
> 覆盖 OWASP Top 10 · GDPR · PIPL（个人信息保护法）

---

## 1. 数据加密 (Encryption)

| # | 检查项 | 状态 | 文件 |
|---|--------|------|------|
| 1.1 | AES-256-GCM 用于 private_vault 所有字段 | ✅ | `utils/encryption.py` |
| 1.2 | 每个字段使用独立 IV（非共享 IV） | ✅ | `encrypt_vault_data()` → `field_ivs` |
| 1.3 | IV 使用 `os.urandom()` 密码学安全随机 | ✅ | `encrypt_field()` |
| 1.4 | AAD 绑定 user_id 防数据替换攻击 | ✅ | `encrypt_field(aad=user_id)` |
| 1.5 | HMAC-SHA256 验证数据完整性 | ✅ | `compute_data_hash()` |
| 1.6 | 主密钥 base64 存储在环境变量（非代码） | ✅ | `config.py` → `ENCRYPTION_MASTER_KEY` |
| 1.7 | 密钥版本追踪支持轮换 | ✅ | `encryption_key_registry` 表 |
| 1.8 | TLS 1.2+ 传输加密 | ⬜ | 需在 Nginx/CDN 层配置 |
| 1.9 | 照片传输使用 HTTPS | ⬜ | 需确认 API_URL 为 https:// |

## 2. 数据库安全 (Database Security)

| # | 检查项 | 状态 | 文件 |
|---|--------|------|------|
| 2.1 | 所有表启用 RLS | ✅ | `quantifyu_schema.sql` 8表全部 ENABLE RLS |
| 2.2 | private_vault 三重验证（身份+consent+未封禁） | ✅ | `002_privacy_hardening.sql` v2 策略 |
| 2.3 | ratings 仅本人可读 | ✅ | `ratings_select_own` 策略 |
| 2.4 | genital_score_encrypted 不在 SELECT * 中暴露 | ⬜ | 需确认前端查询不含此字段 |
| 2.5 | 无索引在加密字段上（防模式泄露） | ✅ | private_vault 仅 user_id 索引 |
| 2.6 | service_role key 仅后端使用 | ✅ | `supabase_client.py` 使用 env var |
| 2.7 | anon key 无写入 private_vault 权限 | ✅ | RLS + INSERT WITH CHECK |
| 2.8 | 用户删除级联清除所有数据 | ✅ | `fn_gdpr_delete_user_data()` |
| 2.9 | consent 撤回自动级联删除 | ✅ | `fn_on_genital_consent_revoked()` 触发器 |
| 2.10 | 审计日志不可篡改（无 UPDATE/DELETE 策略） | ✅ | `consent_audit_log` RLS |

## 3. 照片安全 (Photo Security)

| # | 检查项 | 状态 | 文件 |
|---|--------|------|------|
| 3.1 | 服务端不持久化存储原始照片 | ✅ | 设计原则：仅存 SHA-256 哈希 |
| 3.2 | 照片在内存中处理后立即清除 | ✅ | `PhotoHashService.secure_wipe()` |
| 3.3 | photo_hashes 表仅存哈希不存原图 | ✅ | `photo_hashes` 表结构 |
| 3.4 | 照片最大保留时间 1 小时 | ✅ | `retention_hours=1` + `fn_purge_expired_photo_records()` |
| 3.5 | 客户端 E2E 加密密钥存储在 SecureStore | ✅ | `lib/crypto.ts` → iOS Keychain |
| 3.6 | 照片上传使用 HMAC 签名验证完整性 | ✅ | `preparePhotoForUpload()` |
| 3.7 | 不接受私密照片（仅数值） | ✅ | 前端 UI + 后端 VaultSaveRequest 无图片字段 |
| 3.8 | Storage bucket RLS 限制照片访问 | ⬜ | 需在 Supabase Dashboard 配置 |

## 4. 认证与授权 (Auth)

| # | 检查项 | 状态 | 文件 |
|---|--------|------|------|
| 4.1 | JWT 使用 HS256 + Supabase JWT Secret 验证 | ✅ | `middleware/auth.py` |
| 4.2 | 密码要求：8位+字母+数字 | ✅ | `schemas/auth.py` validator |
| 4.3 | Token 存储在 SecureStore（非 AsyncStorage） | ✅ | `lib/api.ts` |
| 4.4 | SecureStore 使用 WHEN_UNLOCKED_THIS_DEVICE_ONLY | ✅ | `lib/crypto.ts` |
| 4.5 | 封禁用户无法访问 vault | ✅ | RLS 检查 `banned_at IS NULL` |
| 4.6 | 停用用户无法访问 vault | ✅ | RLS 检查 `is_active = TRUE` |
| 4.7 | 每个 API 端点都需要认证 | ✅ | `Depends(get_current_user)` |
| 4.8 | Consent 检查在业务逻辑层强制执行 | ✅ | `middleware/consent.py` |

## 5. Consent 流程 (Consent)

| # | 检查项 | 状态 | 文件 |
|---|--------|------|------|
| 5.1 | 服务条款 + 隐私政策必须同意才能注册 | ✅ | onboarding Step 0 + auth validator |
| 5.2 | AI 评分 consent 可选但解锁评分功能 | ✅ | onboarding Step 1 |
| 5.3 | 生殖器官 consent 可选但解锁私密模块 | ✅ | onboarding Step 2 |
| 5.4 | Consent 变更自动记录审计日志 | ✅ | `fn_audit_consent_change()` 触发器 |
| 5.5 | 用户可随时查看/修改 consent 状态 | ✅ | `ConsentManager.tsx` + `/privacy/consent/*` |
| 5.6 | 撤回 consent 前显示不可逆警告 | ✅ | ConsentManager Alert.alert() |
| 5.7 | 隐私政策弹窗支持中英双语 | ✅ | `PrivacyPolicyModal.tsx` |
| 5.8 | Consent 时间戳有法律效力 | ✅ | `consent_audit_log.consented_at` |
| 5.9 | 不可通过 API 绕过 consent 检查 | ✅ | 后端 + RLS 双重验证 |

## 6. GDPR / PIPL 合规

| # | 检查项 | 状态 | 条文 |
|---|--------|------|------|
| 6.1 | 数据最小化（仅收集必要数据） | ✅ | GDPR Art.5(1)(c) |
| 6.2 | 用途限制（明确告知每类数据用途） | ✅ | 隐私政策 §1 |
| 6.3 | 数据可携带权（一键导出） | ✅ | `/privacy/data-export` · GDPR Art.20 |
| 6.4 | 被遗忘权（一键删除账号+所有数据） | ✅ | `/privacy/account` · GDPR Art.17 |
| 6.5 | 同意可撤回 | ✅ | `/privacy/consent/update` · GDPR Art.7(3) |
| 6.6 | 审计日志满足合规检查 | ✅ | `consent_audit_log` + `scoring_audit_log` |
| 6.7 | 明确的同意获取界面（非默认勾选） | ✅ | onboarding 所有 consent 默认 false |
| 6.8 | 年龄限制 18+ | ✅ | DB CHECK + 前端 date_of_birth 验证 |
| 6.9 | 数据保留政策明确 | ✅ | 隐私政策 §7 |
| 6.10 | 跨境数据传输告知 | ⬜ | 需根据部署地区补充 |

## 7. OWASP Top 10 防护

| # | 威胁 | 防护措施 | 状态 |
|---|------|----------|------|
| 7.1 | 注入攻击 (A03) | Supabase SDK 参数化查询 + Pydantic 验证 | ✅ |
| 7.2 | 失效的身份验证 (A07) | JWT + SecureStore + 密码强度验证 | ✅ |
| 7.3 | 敏感数据暴露 (A02) | AES-256-GCM + TLS + 不存储原图 | ✅ |
| 7.4 | XML外部实体 (A05) | 不使用 XML 解析 | N/A |
| 7.5 | 失效的访问控制 (A01) | RLS + consent middleware + 每端点验证 | ✅ |
| 7.6 | 安全配置错误 (A05) | 环境变量 + 无硬编码密钥 | ✅ |
| 7.7 | XSS (A03) | React Native 自动转义 + 无 dangerouslySetInnerHTML | ✅ |
| 7.8 | 不安全的反序列化 (A08) | Pydantic 严格类型验证 | ✅ |
| 7.9 | 使用含已知漏洞的组件 (A06) | ⬜ | 需定期 `pip audit` / `npm audit` |
| 7.10 | 日志不足 (A09) | 全链路审计日志 + Loguru | ✅ |

## 8. 内存安全 (Memory Safety)

| # | 检查项 | 状态 | 文件 |
|---|--------|------|------|
| 8.1 | 明文数据处理后立即 `del` | ✅ | `vault.py` L169-171 |
| 8.2 | 照片字节用 `bytearray` 后 `secure_wipe()` | ✅ | `privacy.py` photo upload |
| 8.3 | `gc.collect()` 强制回收 | ✅ | `secure_wipe()`, `secure_delete_dict()` |
| 8.4 | 错误消息不泄露内部状态 | ✅ | 通用错误消息 + dev-only detail |
| 8.5 | 审计日志不记录明文值 | ✅ | 仅记录字段名和操作类型 |

## 9. 待完善项 (Action Items)

| 优先级 | 项目 | 说明 |
|--------|------|------|
| P0 | TLS 证书配置 | 确保 API 域名使用 TLS 1.2+ |
| P0 | 环境变量安全 | 确认生产 .env 不在版本控制中 |
| P1 | Storage bucket RLS | 在 Supabase Dashboard 配置存储桶访问策略 |
| P1 | 速率限制 | 添加 API 速率限制防暴力攻击 |
| P1 | react-native-quick-crypto | 替换客户端简化加密为真正 AES-256-GCM |
| P2 | 依赖漏洞扫描 | 配置 CI/CD 自动 `pip audit` + `npm audit` |
| P2 | 渗透测试 | 上线前进行第三方安全审计 |
| P2 | pg_cron 照片清除 | 配置定时任务调用 `fn_purge_expired_photo_records()` |
| P3 | 跨境数据传输声明 | 根据部署地区补充隐私政策 |
| P3 | WAF 配置 | 部署 Web 应用防火墙 |

---

## 架构安全图

```
┌─────────────────────────────────────────────────────┐
│                     客户端 (Expo)                      │
│  ┌──────────┐  ┌──────────┐  ┌────────────────┐    │
│  │SecureStore│  │ HMAC签名  │  │ 照片Base64+Hash│    │
│  │(Keychain) │  │(SHA-256)  │  │ (不存磁盘)      │    │
│  └────┬─────┘  └─────┬────┘  └───────┬────────┘    │
│       │              │               │              │
└───────┼──────────────┼───────────────┼──────────────┘
        │   TLS 1.3    │              │
        ▼              ▼              ▼
┌─────────────────────────────────────────────────────┐
│                  FastAPI 后端                         │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │JWT 验证   │  │Consent 中间件│  │AES-256-GCM   │  │
│  │(auth.py)  │  │(consent.py)  │  │(encryption.py│  │
│  └────┬─────┘  └──────┬───────┘  └──────┬───────┘  │
│       │               │                 │           │
│  ┌────┴───────────────┴─────────────────┴───┐      │
│  │         照片: 内存处理 → 立即清除           │      │
│  │         Vault: 加密 → 存密文 → del 明文     │      │
│  └──────────────────────────────────────────┘      │
└────────────────────┬────────────────────────────────┘
                     │ service_role
                     ▼
┌─────────────────────────────────────────────────────┐
│              Supabase (Postgres + Vault)              │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │RLS 三重   │  │Vault 密钥 │  │consent_audit_log │  │
│  │验证策略   │  │管理       │  │(不可篡改)         │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
│                                                      │
│  private_vault: 全字段 AES-256-GCM 密文              │
│  photo_hashes:  仅 SHA-256 哈希（无原图）             │
│  ratings:       genital_score 可选加密存储            │
└─────────────────────────────────────────────────────┘
```
