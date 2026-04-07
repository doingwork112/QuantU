// ============================================================
// Screen 1: OnboardingConsentScreen
// 多步隐私同意引导 (4步)
//   Step 1: 欢迎 + 基本条款
//   Step 2: AI评分说明 + 同意
//   Step 3: 生殖器官数据模块说明 + 可选同意
//   Step 4: 注册表单
// ============================================================

import React, { useState, useRef } from 'react';
import {
  View,
  Text,
  ScrollView,
  TextInput,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  Alert,
  StyleSheet,
  Dimensions,
} from 'react-native';
import Animated, {
  FadeInRight,
  FadeOutLeft,
  FadeInUp,
  useSharedValue,
  useAnimatedStyle,
  withSpring,
} from 'react-native-reanimated';
import { LinearGradient } from 'expo-linear-gradient';
import { router } from 'expo-router';
import * as Haptics from 'expo-haptics';

import Button from '../../components/ui/Button';
import ProgressBar from '../../components/ui/ProgressBar';
import PrivacyPolicyModal from '../../components/privacy/PrivacyPolicyModal';
import { useStore } from '../../store';
import { signup } from '../../lib/api';
import type { ConsentState } from '../../types';

const { width: SCREEN_W } = Dimensions.get('window');
const TOTAL_STEPS = 4;

// ---- 同意开关组件 ----
function ConsentToggle({
  label,
  description,
  value,
  onToggle,
  required = false,
}: {
  label: string;
  description: string;
  value: boolean;
  onToggle: () => void;
  required?: boolean;
}) {
  const scale = useSharedValue(1);
  const animStyle = useAnimatedStyle(() => ({ transform: [{ scale: scale.value }] }));

  const handlePress = () => {
    scale.value = withSpring(0.95, {}, () => { scale.value = withSpring(1); });
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    onToggle();
  };

  return (
    <TouchableOpacity onPress={handlePress} activeOpacity={0.85}>
      <Animated.View style={[s.consentCard, value && s.consentCardActive, animStyle]}>
        <View style={s.consentHeader}>
          <View style={[s.checkbox, value && s.checkboxActive]}>
            {value && <Text style={s.check}>✓</Text>}
          </View>
          <View style={{ flex: 1 }}>
            <Text style={s.consentLabel}>
              {label}
              {required && <Text style={s.required}> *必须</Text>}
            </Text>
          </View>
        </View>
        <Text style={s.consentDesc}>{description}</Text>
      </Animated.View>
    </TouchableOpacity>
  );
}

// ---- 主组件 ----
export default function OnboardingConsentScreen() {
  const [step, setStep] = useState(0);
  const { consent, setConsent, setUser } = useStore();
  const [loading, setLoading] = useState(false);
  const [showPrivacyPolicy, setShowPrivacyPolicy] = useState(false);

  // 注册表单
  const [form, setForm] = useState({
    email: '',
    password: '',
    display_name: '',
    date_of_birth: '2000-01-01',
    gender: 'male' as 'male' | 'female' | 'non-binary' | 'other',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const canNext = () => {
    if (step === 0) return consent.terms && consent.privacy;
    if (step === 1) return true; // AI scoring is optional here
    if (step === 2) return true; // Genital consent is optional
    if (step === 3) {
      return form.email.includes('@') && form.password.length >= 8 && form.display_name.length >= 2;
    }
    return true;
  };

  const validateForm = (): boolean => {
    const e: Record<string, string> = {};
    if (!form.email.includes('@')) e.email = '请输入有效邮箱';
    if (form.password.length < 8) e.password = '密码至少8位';
    if (!/\d/.test(form.password)) e.password = '密码必须包含数字';
    if (form.display_name.length < 2) e.display_name = '昵称至少2个字符';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleNext = async () => {
    if (step < TOTAL_STEPS - 1) {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      setStep(step + 1);
      return;
    }

    // 最后一步: 注册
    if (!validateForm()) return;
    setLoading(true);
    try {
      const resp = await signup({
        ...form,
        consent_terms_of_service: consent.terms,
        consent_privacy_policy: consent.privacy,
        consent_ai_scoring: consent.ai_scoring,
        consent_genital_data: consent.genital_data,
      });
      setUser(resp.data);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      router.replace('/(tabs)/score');
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || '注册失败';
      Alert.alert('注册失败', msg);
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    if (step > 0) setStep(step - 1);
  };

  // ---- Step 渲染 ----
  const renderStep = () => {
    switch (step) {
      case 0:
        return (
          <Animated.View entering={FadeInRight.duration(400)} exiting={FadeOutLeft.duration(300)} key="s0">
            <Text style={s.emoji}>🔬</Text>
            <Text style={s.title}>欢迎来到 QuantifyU</Text>
            <Text style={s.subtitle}>AI量化你的魅力，科学匹配你的缘分</Text>

            <View style={s.consentList}>
              <ConsentToggle
                label="服务条款"
                description="我已阅读并同意QuantifyU的服务条款，包括用户行为规范和争议解决机制"
                value={consent.terms}
                onToggle={() => setConsent({ terms: !consent.terms })}
                required
              />
              <ConsentToggle
                label="隐私政策"
                description="我同意QuantifyU收集和处理我的个人信息，包括面部照片和身体数据，用于AI评分服务"
                value={consent.privacy}
                onToggle={() => setConsent({ privacy: !consent.privacy })}
                required
              />
              <TouchableOpacity onPress={() => setShowPrivacyPolicy(true)} style={{ marginTop: -4, marginBottom: 8 }}>
                <Text style={{ color: '#818CF8', fontSize: 13, textAlign: 'center', fontWeight: '600', textDecorationLine: 'underline' }}>
                  查看完整隐私政策 / View Full Privacy Policy
                </Text>
              </TouchableOpacity>
              <ConsentToggle
                label="营销通知"
                description="接收产品更新、匹配通知和个性化推荐（可随时关闭）"
                value={consent.marketing}
                onToggle={() => setConsent({ marketing: !consent.marketing })}
              />
            </View>
          </Animated.View>
        );

      case 1:
        return (
          <Animated.View entering={FadeInRight.duration(400)} exiting={FadeOutLeft.duration(300)} key="s1">
            <Text style={s.emoji}>🤖</Text>
            <Text style={s.title}>AI 评分系统</Text>
            <Text style={s.subtitle}>基于ViT视觉模型的五维量化评分</Text>

            <View style={s.infoBox}>
              <Text style={s.infoTitle}>评分维度</Text>
              {[
                ['👤 面部美学', '40分', 'ViT-FBP模型 + 对称性 + 黄金比例'],
                ['💪 身材比例', '25分', 'MediaPipe姿态分析 (WHR/SHR/BMI)'],
                ['📏 身高', '15分', '统计分布评分'],
                ['✨ 皮肤/头发', '10分', 'CV图像质量分析'],
                ['🔒 私密评分', '10分', '仅基于自测数值，非AI视觉'],
              ].map(([name, score, desc], i) => (
                <View key={i} style={s.dimRow}>
                  <Text style={s.dimName}>{name}</Text>
                  <Text style={s.dimScore}>{score}</Text>
                  <Text style={s.dimDesc}>{desc}</Text>
                </View>
              ))}
            </View>

            <ConsentToggle
              label="同意AI评分"
              description="允许AI分析我的面部照片和身材照片进行美学评分。照片仅在评分时处理，不永久存储原图"
              value={consent.ai_scoring}
              onToggle={() => setConsent({ ai_scoring: !consent.ai_scoring })}
            />
          </Animated.View>
        );

      case 2:
        return (
          <Animated.View entering={FadeInRight.duration(400)} exiting={FadeOutLeft.duration(300)} key="s2">
            <Text style={s.emoji}>🔐</Text>
            <Text style={s.title}>私密数据保护</Text>
            <Text style={s.subtitle}>生殖器官数据模块（完全可选）</Text>

            <View style={s.infoBox}>
              <Text style={s.infoTitle}>安全保障</Text>
              {[
                ['🔒', '所有数据 AES-256-GCM 端到端加密'],
                ['🚫', '不接受私密照片，仅接受自测数值'],
                ['👤', '仅限本人查看，即使匹配对象也无法看到'],
                ['🗑️', '可随时一键永久删除所有私密数据'],
                ['📋', '数据库行级安全 (RLS) + consent检查双重保护'],
              ].map(([icon, text], i) => (
                <View key={i} style={s.safetyRow}>
                  <Text style={s.safetyIcon}>{icon}</Text>
                  <Text style={s.safetyText}>{text}</Text>
                </View>
              ))}
            </View>

            <ConsentToggle
              label="启用私密数据模块"
              description="允许加密存储我的生殖器官自测数值（如尺寸、罩杯等），用于私密维度评分。此数据永远不会被他人看到"
              value={consent.genital_data}
              onToggle={() => setConsent({ genital_data: !consent.genital_data })}
            />

            <Text style={s.skipHint}>
              跳过此项不影响其他功能，私密维度将使用默认中位分
            </Text>
          </Animated.View>
        );

      case 3:
        return (
          <Animated.View entering={FadeInRight.duration(400)} exiting={FadeOutLeft.duration(300)} key="s3">
            <Text style={s.emoji}>✍️</Text>
            <Text style={s.title}>创建账号</Text>
            <Text style={s.subtitle}>最后一步，马上开始你的量化之旅</Text>

            <View style={s.formGroup}>
              <Text style={s.inputLabel}>昵称</Text>
              <TextInput
                style={[s.input, errors.display_name ? s.inputError : null]}
                placeholder="你的昵称"
                placeholderTextColor="#4B5563"
                value={form.display_name}
                onChangeText={(v) => { setForm({ ...form, display_name: v }); setErrors({ ...errors, display_name: '' }); }}
              />
              {errors.display_name ? <Text style={s.errText}>{errors.display_name}</Text> : null}
            </View>

            <View style={s.formGroup}>
              <Text style={s.inputLabel}>邮箱</Text>
              <TextInput
                style={[s.input, errors.email ? s.inputError : null]}
                placeholder="email@example.com"
                placeholderTextColor="#4B5563"
                keyboardType="email-address"
                autoCapitalize="none"
                value={form.email}
                onChangeText={(v) => { setForm({ ...form, email: v }); setErrors({ ...errors, email: '' }); }}
              />
              {errors.email ? <Text style={s.errText}>{errors.email}</Text> : null}
            </View>

            <View style={s.formGroup}>
              <Text style={s.inputLabel}>密码</Text>
              <TextInput
                style={[s.input, errors.password ? s.inputError : null]}
                placeholder="至少8位，包含字母和数字"
                placeholderTextColor="#4B5563"
                secureTextEntry
                value={form.password}
                onChangeText={(v) => { setForm({ ...form, password: v }); setErrors({ ...errors, password: '' }); }}
              />
              {errors.password ? <Text style={s.errText}>{errors.password}</Text> : null}
            </View>

            {/* 性别选择 */}
            <View style={s.formGroup}>
              <Text style={s.inputLabel}>性别</Text>
              <View style={s.genderRow}>
                {(['male', 'female', 'non-binary'] as const).map((g) => (
                  <TouchableOpacity
                    key={g}
                    onPress={() => setForm({ ...form, gender: g })}
                    style={[s.genderChip, form.gender === g && s.genderChipActive]}
                  >
                    <Text style={[s.genderText, form.gender === g && s.genderTextActive]}>
                      {g === 'male' ? '♂ 男' : g === 'female' ? '♀ 女' : '⚧ 非二元'}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          </Animated.View>
        );
    }
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      style={s.screen}
    >
      {/* 顶部进度 */}
      <View style={s.progressWrap}>
        <ProgressBar progress={(step + 1) / TOTAL_STEPS} />
        <Text style={s.stepText}>
          {step + 1} / {TOTAL_STEPS}
        </Text>
      </View>

      <ScrollView
        contentContainerStyle={s.scroll}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        {renderStep()}
      </ScrollView>

      {/* 底部按钮 */}
      <View style={s.footer}>
        {step > 0 && (
          <Button title="返回" onPress={handleBack} variant="ghost" style={{ flex: 1 }} />
        )}
        <Button
          title={step === TOTAL_STEPS - 1 ? '创建账号' : '下一步'}
          onPress={handleNext}
          disabled={!canNext()}
          loading={loading}
          style={{ flex: step > 0 ? 2 : 1 }}
          size="lg"
        />
      </View>
      {/* 隐私政策弹窗 */}
      <PrivacyPolicyModal
        visible={showPrivacyPolicy}
        onAccept={() => {
          setConsent({ privacy: true });
          setShowPrivacyPolicy(false);
        }}
        onDecline={() => setShowPrivacyPolicy(false)}
      />
    </KeyboardAvoidingView>
  );
}

// ============================================================
const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#0F0D2E' },
  progressWrap: { paddingHorizontal: 24, paddingTop: 60, gap: 6 },
  stepText: { color: '#64748B', fontSize: 12, textAlign: 'right' },
  scroll: { paddingHorizontal: 24, paddingTop: 20, paddingBottom: 40 },
  emoji: { fontSize: 48, textAlign: 'center', marginBottom: 12 },
  title: { color: '#E0E7FF', fontSize: 28, fontWeight: '800', textAlign: 'center', marginBottom: 8 },
  subtitle: { color: '#94A3B8', fontSize: 15, textAlign: 'center', lineHeight: 22, marginBottom: 28 },

  // Consent cards
  consentList: { gap: 12 },
  consentCard: {
    backgroundColor: 'rgba(30,27,75,0.5)',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1.5,
    borderColor: 'rgba(99,102,241,0.15)',
    marginBottom: 12,
  },
  consentCardActive: { borderColor: '#6366F1', backgroundColor: 'rgba(99,102,241,0.08)' },
  consentHeader: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 8 },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: 8,
    borderWidth: 2,
    borderColor: '#4B5563',
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkboxActive: { backgroundColor: '#6366F1', borderColor: '#6366F1' },
  check: { color: '#fff', fontSize: 14, fontWeight: '700' },
  consentLabel: { color: '#E0E7FF', fontSize: 15, fontWeight: '700' },
  required: { color: '#EF4444', fontSize: 11 },
  consentDesc: { color: '#94A3B8', fontSize: 13, lineHeight: 19, paddingLeft: 36 },

  // Info box
  infoBox: {
    backgroundColor: 'rgba(30,27,75,0.5)',
    borderRadius: 16,
    padding: 16,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: 'rgba(99,102,241,0.12)',
  },
  infoTitle: { color: '#C7D2FE', fontSize: 14, fontWeight: '700', marginBottom: 12 },
  dimRow: { marginBottom: 10 },
  dimName: { color: '#E0E7FF', fontSize: 14, fontWeight: '600' },
  dimScore: { color: '#6366F1', fontSize: 12, fontWeight: '700', marginTop: 1 },
  dimDesc: { color: '#64748B', fontSize: 11, marginTop: 2 },

  // Safety
  safetyRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, marginBottom: 10 },
  safetyIcon: { fontSize: 16, marginTop: 1 },
  safetyText: { color: '#C7D2FE', fontSize: 13, flex: 1, lineHeight: 19 },
  skipHint: { color: '#64748B', fontSize: 12, textAlign: 'center', marginTop: 16, fontStyle: 'italic' },

  // Form
  formGroup: { marginBottom: 18 },
  inputLabel: { color: '#C7D2FE', fontSize: 13, fontWeight: '600', marginBottom: 6 },
  input: {
    backgroundColor: 'rgba(30,27,75,0.6)',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 14,
    color: '#E0E7FF',
    fontSize: 15,
    borderWidth: 1,
    borderColor: 'rgba(99,102,241,0.15)',
  },
  inputError: { borderColor: '#EF4444' },
  errText: { color: '#EF4444', fontSize: 12, marginTop: 4 },
  genderRow: { flexDirection: 'row', gap: 10 },
  genderChip: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: 'rgba(99,102,241,0.2)',
    alignItems: 'center',
  },
  genderChipActive: { backgroundColor: 'rgba(99,102,241,0.15)', borderColor: '#6366F1' },
  genderText: { color: '#94A3B8', fontSize: 14, fontWeight: '600' },
  genderTextActive: { color: '#C7D2FE' },

  // Footer
  footer: {
    flexDirection: 'row',
    gap: 12,
    paddingHorizontal: 24,
    paddingTop: 12,
    paddingBottom: 40,
    borderTopWidth: 1,
    borderTopColor: 'rgba(99,102,241,0.1)',
  },
});
