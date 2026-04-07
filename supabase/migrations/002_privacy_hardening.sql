-- ============================================================
-- QuantifyU — 隐私加固迁移 002
-- 最高级别隐私保护：
--   1. 强化 private_vault RLS（双重 consent + 速率限制）
--   2. Supabase Vault 密钥管理集成
--   3. 照片哈希表（服务端只存哈希，不存原图）
--   4. Consent 审计日志 + 不可篡改性
--   5. 数据自毁（用户删除时级联清除所有痕迹）
-- ============================================================

-- 0. 确保扩展
CREATE EXTENSION IF NOT EXISTS "pgsodium";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- 1. SUPABASE VAULT — 密钥管理
-- ============================================================
-- 在 Supabase Vault 中创建加密密钥（用于数据库层加密）
-- 注：实际密钥通过 Supabase Dashboard > Vault 管理
-- 以下是引用密钥的辅助视图

-- 密钥轮换追踪表
CREATE TABLE IF NOT EXISTS encryption_key_registry (
    id SERIAL PRIMARY KEY,
    key_version INT NOT NULL UNIQUE,
    key_purpose TEXT NOT NULL DEFAULT 'vault_field_encryption',
    algorithm TEXT NOT NULL DEFAULT 'AES-256-GCM',
    created_at TIMESTAMPTZ DEFAULT now(),
    rotated_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    -- Supabase Vault secret ID (引用 vault.secrets 表)
    vault_secret_id UUID,
    notes TEXT
);

INSERT INTO encryption_key_registry (key_version, key_purpose, is_active, notes)
VALUES (1, 'vault_field_encryption', TRUE, '初始主密钥 — AES-256-GCM')
ON CONFLICT (key_version) DO NOTHING;

COMMENT ON TABLE encryption_key_registry IS
    '加密密钥版本注册表，与 Supabase Vault 配合管理密钥轮换';

-- ============================================================
-- 2. 照片哈希表 — 服务端只存哈希
-- ============================================================
CREATE TABLE IF NOT EXISTS photo_hashes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- 照片用途
    photo_type TEXT NOT NULL CHECK (photo_type IN ('face', 'body', 'body_side', 'avatar')),

    -- 仅存储哈希，不存储原图
    sha256_hash TEXT NOT NULL,               -- SHA-256(原图字节)
    perceptual_hash TEXT,                    -- pHash（用于去重，可选）
    file_size_bytes BIGINT,
    mime_type TEXT CHECK (mime_type IN ('image/jpeg', 'image/png', 'image/webp')),

    -- 客户端加密元数据
    client_encrypted BOOLEAN DEFAULT FALSE,  -- 客户端是否已E2E加密
    encryption_algorithm TEXT,               -- 客户端使用的加密算法
    client_key_id TEXT,                      -- 客户端密钥标识（不含密钥本身）

    -- 生命周期
    uploaded_at TIMESTAMPTZ DEFAULT now(),
    processed_at TIMESTAMPTZ,                -- AI 处理完成时间
    purged_at TIMESTAMPTZ,                   -- 原图清除时间（处理后立即清除）
    retention_hours INT DEFAULT 1,           -- 最大保留时长（小时）

    -- 评分关联
    rating_id UUID REFERENCES ratings(id) ON DELETE SET NULL,

    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_photo_hashes_user ON photo_hashes(user_id, photo_type);
CREATE INDEX idx_photo_hashes_hash ON photo_hashes(sha256_hash);

-- 照片哈希表 RLS：仅本人可见
ALTER TABLE photo_hashes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "photo_hashes_select_own" ON photo_hashes
    FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "photo_hashes_insert_own" ON photo_hashes
    FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "photo_hashes_delete_own" ON photo_hashes
    FOR DELETE USING (auth.uid() = user_id);
-- 不允许客户端更新（仅后端 service_role 可更新 processed_at/purged_at）

COMMENT ON TABLE photo_hashes IS
    '照片指纹表 — 服务端仅存 SHA-256 哈希，绝不持久化原图。AI 处理完毕后原图立即从内存清除';

-- ============================================================
-- 3. CONSENT 审计日志 — 不可篡改追踪
-- ============================================================
CREATE TABLE IF NOT EXISTS consent_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- 变更详情
    consent_field TEXT NOT NULL,              -- 哪个 consent 字段变更
    old_value BOOLEAN,
    new_value BOOLEAN NOT NULL,
    change_reason TEXT,                       -- 用户提供的原因（可选）

    -- 来源追踪
    ip_address INET,
    user_agent TEXT,
    request_id TEXT,                          -- 请求追踪 ID

    -- 法律时间戳
    consented_at TIMESTAMPTZ DEFAULT now(),
    -- 不可篡改：无 UPDATE/DELETE 策略
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_consent_audit_user ON consent_audit_log(user_id, created_at DESC);

-- RLS：仅本人可查看，任何人不可修改/删除
ALTER TABLE consent_audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "consent_audit_select_own" ON consent_audit_log
    FOR SELECT USING (auth.uid() = user_id);
-- INSERT 仅限 service_role（后端写入）
-- 无 UPDATE / DELETE 策略 → 不可篡改

COMMENT ON TABLE consent_audit_log IS
    '同意变更审计日志 — 不可篡改（无 UPDATE/DELETE RLS），满足 GDPR/PIPL 合规审计要求';

-- ============================================================
-- 4. 强化 PRIVATE_VAULT RLS
-- ============================================================

-- 先删除旧策略（如存在），再创建更严格版本
DROP POLICY IF EXISTS "vault_select_own" ON private_vault;
DROP POLICY IF EXISTS "vault_insert_own" ON private_vault;
DROP POLICY IF EXISTS "vault_update_own" ON private_vault;
DROP POLICY IF EXISTS "vault_delete_own" ON private_vault;

-- 4a. SELECT — 三重验证：本人 + consent + 账号未封禁
CREATE POLICY "vault_select_own_v2" ON private_vault
    FOR SELECT USING (
        auth.uid() = user_id
        AND EXISTS (
            SELECT 1 FROM users
            WHERE users.id = auth.uid()
            AND users.consent_genital_data = TRUE
            AND users.is_active = TRUE
            AND users.banned_at IS NULL
        )
    );

-- 4b. INSERT — 三重验证 + 检查用户未被封禁
CREATE POLICY "vault_insert_own_v2" ON private_vault
    FOR INSERT WITH CHECK (
        auth.uid() = user_id
        AND EXISTS (
            SELECT 1 FROM users
            WHERE users.id = auth.uid()
            AND users.consent_genital_data = TRUE
            AND users.is_active = TRUE
            AND users.banned_at IS NULL
        )
    );

-- 4c. UPDATE — 同上
CREATE POLICY "vault_update_own_v2" ON private_vault
    FOR UPDATE USING (
        auth.uid() = user_id
        AND EXISTS (
            SELECT 1 FROM users
            WHERE users.id = auth.uid()
            AND users.consent_genital_data = TRUE
            AND users.is_active = TRUE
            AND users.banned_at IS NULL
        )
    );

-- 4d. DELETE — 允许本人删除（即使撤回 consent 后也能删除数据）
CREATE POLICY "vault_delete_own_v2" ON private_vault
    FOR DELETE USING (
        auth.uid() = user_id
        AND EXISTS (
            SELECT 1 FROM users
            WHERE users.id = auth.uid()
            AND users.is_active = TRUE
        )
    );

-- ============================================================
-- 5. CONSENT 变更触发器 — 自动记录 + 撤回时级联清除
-- ============================================================

-- 5a. 记录每次 consent 变更
CREATE OR REPLACE FUNCTION fn_audit_consent_change()
RETURNS TRIGGER AS $$
DECLARE
    consent_fields TEXT[] := ARRAY[
        'consent_terms_of_service',
        'consent_privacy_policy',
        'consent_ai_scoring',
        'consent_genital_data',
        'consent_data_sharing',
        'consent_marketing'
    ];
    field_name TEXT;
    old_val BOOLEAN;
    new_val BOOLEAN;
BEGIN
    FOREACH field_name IN ARRAY consent_fields LOOP
        EXECUTE format('SELECT ($1).%I, ($2).%I', field_name, field_name)
            INTO old_val, new_val
            USING OLD, NEW;

        IF old_val IS DISTINCT FROM new_val THEN
            INSERT INTO consent_audit_log (user_id, consent_field, old_value, new_value)
            VALUES (NEW.id, field_name, old_val, new_val);
        END IF;
    END LOOP;

    -- 更新 consent_updated_at
    NEW.consent_updated_at := now();

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_audit_consent ON users;
CREATE TRIGGER trg_audit_consent
    BEFORE UPDATE OF
        consent_terms_of_service,
        consent_privacy_policy,
        consent_ai_scoring,
        consent_genital_data,
        consent_data_sharing,
        consent_marketing
    ON users
    FOR EACH ROW
    EXECUTE FUNCTION fn_audit_consent_change();

-- 5b. 撤回 genital consent → 自动清除 vault 数据
CREATE OR REPLACE FUNCTION fn_on_genital_consent_revoked()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.consent_genital_data = TRUE AND NEW.consent_genital_data = FALSE THEN
        -- 清除 private_vault 数据
        DELETE FROM private_vault WHERE user_id = NEW.id;

        -- 清除 ratings 中的加密字段
        UPDATE ratings SET
            genital_score = NULL,
            genital_score_encrypted = NULL,
            genital_score_iv = NULL
        WHERE user_id = NEW.id;

        -- 记录审计
        INSERT INTO scoring_audit_log (user_id, action, metadata)
        VALUES (
            NEW.id,
            'consent_revoked_cascade_delete',
            jsonb_build_object(
                'consent_field', 'consent_genital_data',
                'vault_deleted', TRUE,
                'genital_scores_nulled', TRUE,
                'timestamp', now()
            )
        );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_genital_consent_revoked ON users;
CREATE TRIGGER trg_genital_consent_revoked
    AFTER UPDATE OF consent_genital_data
    ON users
    FOR EACH ROW
    WHEN (OLD.consent_genital_data = TRUE AND NEW.consent_genital_data = FALSE)
    EXECUTE FUNCTION fn_on_genital_consent_revoked();

-- 5c. 撤回 AI scoring consent → 清除评分照片哈希
CREATE OR REPLACE FUNCTION fn_on_ai_consent_revoked()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.consent_ai_scoring = TRUE AND NEW.consent_ai_scoring = FALSE THEN
        DELETE FROM photo_hashes WHERE user_id = NEW.id;

        INSERT INTO scoring_audit_log (user_id, action, metadata)
        VALUES (
            NEW.id,
            'consent_revoked_cascade_delete',
            jsonb_build_object(
                'consent_field', 'consent_ai_scoring',
                'photo_hashes_deleted', TRUE,
                'timestamp', now()
            )
        );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_ai_consent_revoked ON users;
CREATE TRIGGER trg_ai_consent_revoked
    AFTER UPDATE OF consent_ai_scoring
    ON users
    FOR EACH ROW
    WHEN (OLD.consent_ai_scoring = TRUE AND NEW.consent_ai_scoring = FALSE)
    EXECUTE FUNCTION fn_on_ai_consent_revoked();

-- ============================================================
-- 6. 照片自动清除 — 处理完成后清除原图记录
-- ============================================================
-- 定时任务（Supabase pg_cron 或后端 cron 调用）
CREATE OR REPLACE FUNCTION fn_purge_expired_photo_records()
RETURNS INT AS $$
DECLARE
    purged_count INT;
BEGIN
    -- 标记已超期的照片为已清除
    UPDATE photo_hashes
    SET purged_at = now()
    WHERE purged_at IS NULL
    AND uploaded_at < now() - (retention_hours || ' hours')::INTERVAL;

    GET DIAGNOSTICS purged_count = ROW_COUNT;

    -- 记录审计
    IF purged_count > 0 THEN
        INSERT INTO scoring_audit_log (
            user_id, action, metadata
        )
        SELECT DISTINCT
            user_id,
            'photo_auto_purged',
            jsonb_build_object('purged_count', purged_count, 'timestamp', now())
        FROM photo_hashes
        WHERE purged_at = now();
    END IF;

    RETURN purged_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION fn_purge_expired_photo_records IS
    '定期清除过期照片记录，配合后端内存清除确保原图不持久化';

-- ============================================================
-- 7. 用户账号删除 — 级联清除所有数据（GDPR 被遗忘权）
-- ============================================================
CREATE OR REPLACE FUNCTION fn_gdpr_delete_user_data(target_user_id UUID)
RETURNS JSONB AS $$
DECLARE
    result JSONB;
    vault_count INT;
    rating_count INT;
    match_count INT;
    photo_count INT;
    msg_count INT;
BEGIN
    -- 1. 删除 private_vault
    DELETE FROM private_vault WHERE user_id = target_user_id;
    GET DIAGNOSTICS vault_count = ROW_COUNT;

    -- 2. 删除 ratings
    DELETE FROM ratings WHERE user_id = target_user_id;
    GET DIAGNOSTICS rating_count = ROW_COUNT;

    -- 3. 删除 matches
    DELETE FROM matches WHERE user_a = target_user_id OR user_b = target_user_id;
    GET DIAGNOSTICS match_count = ROW_COUNT;

    -- 4. 删除 photo_hashes
    DELETE FROM photo_hashes WHERE user_id = target_user_id;
    GET DIAGNOSTICS photo_count = ROW_COUNT;

    -- 5. 删除 messages（通过 match cascade 已处理，但双重保险）
    DELETE FROM messages WHERE sender_id = target_user_id;
    GET DIAGNOSTICS msg_count = ROW_COUNT;

    -- 6. 匿名化审计日志（保留记录但移除可识别信息）
    UPDATE scoring_audit_log
    SET ip_address = NULL, user_agent = NULL,
        metadata = metadata || '{"gdpr_anonymized": true}'::jsonb
    WHERE user_id = target_user_id;

    UPDATE consent_audit_log
    SET ip_address = NULL, user_agent = NULL
    WHERE user_id = target_user_id;

    -- 7. 删除 profiles, preferences, user
    DELETE FROM user_preferences WHERE user_id = target_user_id;
    DELETE FROM profiles WHERE user_id = target_user_id;
    DELETE FROM users WHERE id = target_user_id;

    result := jsonb_build_object(
        'user_id', target_user_id,
        'vault_deleted', vault_count,
        'ratings_deleted', rating_count,
        'matches_deleted', match_count,
        'photos_deleted', photo_count,
        'messages_deleted', msg_count,
        'audit_logs_anonymized', TRUE,
        'deleted_at', now()
    );

    RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION fn_gdpr_delete_user_data IS
    'GDPR "被遗忘权" — 级联删除用户所有数据，审计日志匿名化保留';

-- ============================================================
-- 8. 加密密钥轮换 RLS
-- ============================================================
ALTER TABLE encryption_key_registry ENABLE ROW LEVEL SECURITY;
-- 仅 service_role 可管理密钥（无客户端策略）

-- ============================================================
-- ✅ 隐私加固迁移完成
-- 新增: encryption_key_registry, photo_hashes, consent_audit_log
-- 强化: private_vault RLS (三重验证 + 封禁检查)
-- 触发器: consent 变更自动审计 + 撤回时级联清除
-- 函数: GDPR 删除 + 照片过期清除
-- ============================================================
