// ============================================================
// QuantifyU — 隐私政策弹窗（中英双语）
// ============================================================

import React, { useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  Modal,
  TouchableOpacity,
  StyleSheet,
  Dimensions,
} from 'react-native';
import Animated, { FadeIn, SlideInDown } from 'react-native-reanimated';
import * as Haptics from 'expo-haptics';

const { height: SCREEN_H } = Dimensions.get('window');

interface Props {
  visible: boolean;
  onAccept: () => void;
  onDecline: () => void;
  /** 'zh' 中文 | 'en' 英文 */
  initialLang?: 'zh' | 'en';
}

// ---- 政策文案 ----
const POLICY = {
  zh: {
    title: '隐私政策',
    subtitle: '最后更新：2025年5月',
    sections: [
      {
        heading: '1. 我们收集的数据',
        body: `QuantifyU 收集以下类别的个人信息：

• 基础信息：邮箱、昵称、出生日期、性别
• 身体数据：身高、体重、体脂率（用于AI评分）
• 面部照片：用于AI美学评分，处理后立即从服务器内存中删除，不会永久存储原图
• 身材照片：同上，仅在评分时短暂处理
• 私密数据（可选）：生殖器官自测数值，使用AES-256-GCM端到端加密存储
• 地理位置：用于匹配距离计算
• 使用日志：API访问日志（用于安全审计）`,
      },
      {
        heading: '2. 数据加密与安全',
        body: `我们采用业界最高标准保护您的数据：

🔒 传输加密：所有API通信使用TLS 1.3
🔒 存储加密：私密数据使用AES-256-GCM加密，每个字段独立初始化向量（IV）
🔒 密钥管理：加密密钥通过Supabase Vault管理，支持定期轮换
🔒 照片安全：服务端仅存储照片的SHA-256哈希指纹，绝不持久化原图
🔒 客户端安全：敏感数据（令牌、加密密钥）存储在iOS Keychain / Android Keystore
🔒 行级安全：数据库启用行级安全策略（RLS），私密数据仅限本人访问
🔒 AAD绑定：加密数据绑定用户ID，防止数据替换攻击`,
      },
      {
        heading: '3. AI 评分系统',
        body: `您的照片如何被处理：

1. 照片在您的设备上选取后，通过加密通道发送到服务器
2. 服务器在内存中处理照片（ViT-FBP面部分析、MediaPipe姿态分析）
3. 生成评分结果后，照片立即从服务器内存中清除
4. 仅保存评分结果和照片的SHA-256哈希（用于去重）
5. 原始照片在整个过程中不会被写入任何磁盘或数据库

⚠️ 私密维度评分仅基于您输入的自测数值，不涉及任何照片或AI视觉分析`,
      },
      {
        heading: '4. 私密数据保护（生殖器官数据）',
        body: `如果您选择启用私密数据模块：

• 所有数据使用AES-256-GCM端到端加密，服务器数据库中仅存储密文
• 每个字段使用独立的初始化向量（IV），增强安全性
• 数据仅限您本人查看 — 即使匹配对象也无法看到
• 数据库行级安全策略（RLS）进行双重验证：身份 + 同意状态
• 您可以随时一键永久删除所有私密数据
• 撤回同意后，系统自动级联删除所有相关数据（不可恢复）

⚠️ 我们不接受任何私密照片，仅接受自测数值`,
      },
      {
        heading: '5. 数据共享',
        body: `您的数据不会被出售给第三方。

• 匹配对象可以看到：您的昵称、头像、城市、总体评分等级
• 匹配对象无法看到：具体评分分数（除非您在设置中选择公开）、私密数据、原始照片
• 我们不会与广告商共享个人身体数据
• 审计日志仅用于安全合规，不用于商业目的`,
      },
      {
        heading: '6. 您的权利',
        body: `您享有以下隐私权利：

📋 查看权：随时查看您的所有个人数据
📤 导出权：一键导出所有个人数据（GDPR第20条）
✏️ 修改权：随时修改个人资料和偏好设置
🗑️ 删除权：一键永久删除账号和所有数据（GDPR第17条 — 被遗忘权）
🔄 同意管理：随时更改或撤回您的同意状态
⏸️ 暂停权：停用账号但保留数据

行使权利：设置 → 隐私管理`,
      },
      {
        heading: '7. 数据保留',
        body: `• 照片：AI处理完毕后立即清除，最长保留1小时
• 评分记录：账号存续期间保留
• 私密数据：直到您手动删除或撤回同意
• 审计日志：保留2年（法律合规要求）
• 账号删除后：所有数据在30天内完全清除`,
      },
    ],
    acceptBtn: '我已阅读并同意',
    declineBtn: '不同意',
    langSwitch: 'English',
  },
  en: {
    title: 'Privacy Policy',
    subtitle: 'Last updated: May 2025',
    sections: [
      {
        heading: '1. Data We Collect',
        body: `QuantifyU collects the following categories of personal information:

• Basic info: email, display name, date of birth, gender
• Body data: height, weight, body fat percentage (for AI scoring)
• Facial photos: for AI aesthetic scoring — deleted from server memory immediately after processing, never permanently stored
• Body photos: same as above, only briefly processed during scoring
• Private data (optional): self-measured genital data, stored with AES-256-GCM end-to-end encryption
• Geolocation: for match distance calculation
• Usage logs: API access logs (for security auditing)`,
      },
      {
        heading: '2. Encryption & Security',
        body: `We employ the highest industry standards to protect your data:

🔒 Transit: All API communication uses TLS 1.3
🔒 At-rest: Private data encrypted with AES-256-GCM, independent IVs per field
🔒 Key management: Encryption keys managed via Supabase Vault with rotation support
🔒 Photo safety: Server only stores SHA-256 hash fingerprints — never the original images
🔒 Client security: Sensitive data (tokens, keys) stored in iOS Keychain / Android Keystore
🔒 Row-level security: Database RLS policies ensure private data is accessible only by its owner
🔒 AAD binding: Encrypted data is bound to user ID, preventing data substitution attacks`,
      },
      {
        heading: '3. AI Scoring System',
        body: `How your photos are processed:

1. Photos are selected on your device and sent to the server via encrypted channel
2. The server processes photos in-memory (ViT-FBP face analysis, MediaPipe pose analysis)
3. After generating scores, photos are immediately cleared from server memory
4. Only scores and SHA-256 photo hashes are saved (for deduplication)
5. Original photos are never written to any disk or database during the entire process

⚠️ Private dimension scores are based solely on your self-reported measurements — no photos or AI visual analysis involved`,
      },
      {
        heading: '4. Private Data Protection (Genital Data)',
        body: `If you choose to enable the private data module:

• All data is encrypted with AES-256-GCM end-to-end — only ciphertext is stored in the database
• Each field uses an independent initialization vector (IV) for enhanced security
• Data is visible only to you — even your matches cannot see it
• Database row-level security (RLS) performs double verification: identity + consent status
• You can permanently delete all private data with one click at any time
• Revoking consent automatically cascade-deletes all related data (irreversible)

⚠️ We do not accept any intimate photos — only self-measured numerical values`,
      },
      {
        heading: '5. Data Sharing',
        body: `Your data is never sold to third parties.

• Matches can see: your display name, avatar, city, overall score tier
• Matches cannot see: specific scores (unless you opt-in), private data, original photos
• We do not share personal body data with advertisers
• Audit logs are used solely for security compliance, not commercial purposes`,
      },
      {
        heading: '6. Your Rights',
        body: `You have the following privacy rights:

📋 Access: View all your personal data at any time
📤 Portability: Export all personal data with one click (GDPR Art. 20)
✏️ Rectification: Modify your profile and preferences at any time
🗑️ Erasure: Permanently delete your account and all data (GDPR Art. 17 — Right to be Forgotten)
🔄 Consent management: Change or revoke your consent status at any time
⏸️ Pause: Deactivate your account while retaining data

Exercise your rights: Settings → Privacy Management`,
      },
      {
        heading: '7. Data Retention',
        body: `• Photos: Cleared immediately after AI processing, max retention 1 hour
• Score records: Retained during account lifetime
• Private data: Until you manually delete or revoke consent
• Audit logs: Retained for 2 years (legal compliance)
• After account deletion: All data fully purged within 30 days`,
      },
    ],
    acceptBtn: 'I have read and agree',
    declineBtn: 'Decline',
    langSwitch: '中文',
  },
};

export default function PrivacyPolicyModal({
  visible,
  onAccept,
  onDecline,
  initialLang = 'zh',
}: Props) {
  const [lang, setLang] = useState<'zh' | 'en'>(initialLang);
  const t = POLICY[lang];

  const toggleLang = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setLang(lang === 'zh' ? 'en' : 'zh');
  };

  return (
    <Modal visible={visible} animationType="none" transparent statusBarTranslucent>
      <Animated.View entering={FadeIn.duration(200)} style={s.overlay}>
        <Animated.View entering={SlideInDown.duration(400).springify()} style={s.sheet}>
          {/* Header */}
          <View style={s.header}>
            <View>
              <Text style={s.title}>{t.title}</Text>
              <Text style={s.subtitle}>{t.subtitle}</Text>
            </View>
            <TouchableOpacity onPress={toggleLang} style={s.langBtn}>
              <Text style={s.langText}>{t.langSwitch}</Text>
            </TouchableOpacity>
          </View>

          {/* Content */}
          <ScrollView
            style={s.scrollArea}
            contentContainerStyle={s.scrollContent}
            showsVerticalScrollIndicator
          >
            {t.sections.map((section, i) => (
              <View key={i} style={s.section}>
                <Text style={s.sectionHeading}>{section.heading}</Text>
                <Text style={s.sectionBody}>{section.body}</Text>
              </View>
            ))}
          </ScrollView>

          {/* Buttons */}
          <View style={s.footer}>
            <TouchableOpacity onPress={onDecline} style={s.declineBtn}>
              <Text style={s.declineText}>{t.declineBtn}</Text>
            </TouchableOpacity>
            <TouchableOpacity
              onPress={() => {
                Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
                onAccept();
              }}
              style={s.acceptBtn}
            >
              <Text style={s.acceptText}>{t.acceptBtn}</Text>
            </TouchableOpacity>
          </View>
        </Animated.View>
      </Animated.View>
    </Modal>
  );
}

const s = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: '#1A1640',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    maxHeight: SCREEN_H * 0.88,
    paddingBottom: 40,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    paddingHorizontal: 24,
    paddingTop: 24,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(99,102,241,0.15)',
  },
  title: {
    color: '#E0E7FF',
    fontSize: 22,
    fontWeight: '800',
  },
  subtitle: {
    color: '#64748B',
    fontSize: 12,
    marginTop: 4,
  },
  langBtn: {
    backgroundColor: 'rgba(99,102,241,0.12)',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: 'rgba(99,102,241,0.25)',
  },
  langText: {
    color: '#818CF8',
    fontSize: 13,
    fontWeight: '700',
  },

  scrollArea: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 24,
    paddingTop: 16,
    paddingBottom: 24,
  },
  section: {
    marginBottom: 24,
  },
  sectionHeading: {
    color: '#C7D2FE',
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 10,
  },
  sectionBody: {
    color: '#94A3B8',
    fontSize: 13,
    lineHeight: 21,
  },

  footer: {
    flexDirection: 'row',
    gap: 12,
    paddingHorizontal: 24,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: 'rgba(99,102,241,0.15)',
  },
  declineBtn: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 14,
    borderWidth: 1.5,
    borderColor: 'rgba(239,68,68,0.4)',
    alignItems: 'center',
  },
  declineText: {
    color: '#EF4444',
    fontSize: 15,
    fontWeight: '700',
  },
  acceptBtn: {
    flex: 2,
    paddingVertical: 14,
    borderRadius: 14,
    backgroundColor: '#6366F1',
    alignItems: 'center',
  },
  acceptText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '700',
  },
});
