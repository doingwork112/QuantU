// ============================================================
// QuantifyU — Consent 管理组件
// 用户可以在设置中随时查看和修改同意状态
// ============================================================

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  Switch,
  Alert,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import Animated, { FadeInUp } from 'react-native-reanimated';
import * as Haptics from 'expo-haptics';

import { getConsentStatus, updateConsent, deleteVaultData } from '../../lib/api';
import { useStore } from '../../store';

interface ConsentItem {
  key: string;
  label: string;
  description: string;
  editable: boolean;
  dangerous?: boolean;
  dangerWarning?: string;
}

const CONSENT_ITEMS: ConsentItem[] = [
  {
    key: 'consent_terms_of_service',
    label: '服务条款',
    description: '必须同意才能使用服务。如需撤回，请删除账号。',
    editable: false,
  },
  {
    key: 'consent_privacy_policy',
    label: '隐私政策',
    description: '必须同意才能使用服务。如需撤回，请删除账号。',
    editable: false,
  },
  {
    key: 'consent_ai_scoring',
    label: 'AI 评分',
    description: '允许AI分析面部和身材照片。关闭后将无法使用评分功能，已有的照片哈希记录将被自动删除。',
    editable: true,
    dangerous: true,
    dangerWarning: '关闭 AI 评分后，所有照片哈希记录将被自动删除，且无法恢复。确定要关闭吗？',
  },
  {
    key: 'consent_genital_data',
    label: '私密数据模块',
    description: '允许加密存储生殖器官自测数值。关闭后所有私密数据将被永久删除。',
    editable: true,
    dangerous: true,
    dangerWarning: '⚠️ 关闭后，您的所有私密数据（private vault）将被永久删除且无法恢复！\n\n确定要关闭吗？',
  },
  {
    key: 'consent_data_sharing',
    label: '数据共享',
    description: '允许将您的评分等级（非具体分数）展示给匹配对象。',
    editable: true,
  },
  {
    key: 'consent_marketing',
    label: '营销通知',
    description: '接收产品更新和个性化推荐通知。',
    editable: true,
  },
];

export default function ConsentManager() {
  const [consents, setConsents] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState<string | null>(null);
  const { setConsent } = useStore();

  useEffect(() => {
    loadConsents();
  }, []);

  const loadConsents = async () => {
    try {
      const resp = await getConsentStatus();
      setConsents(resp.data);
    } catch {
      Alert.alert('加载失败', '无法获取同意状态');
    }
    setLoading(false);
  };

  const handleToggle = async (item: ConsentItem, newValue: boolean) => {
    if (!item.editable) return;

    // 关闭危险选项时需要确认
    if (item.dangerous && !newValue) {
      Alert.alert(
        '确认操作',
        item.dangerWarning || '确定要关闭此选项吗？',
        [
          { text: '取消', style: 'cancel' },
          {
            text: '确认关闭',
            style: 'destructive',
            onPress: () => doUpdate(item.key, newValue),
          },
        ],
      );
      return;
    }

    await doUpdate(item.key, newValue);
  };

  const doUpdate = async (key: string, value: boolean) => {
    setUpdating(key);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

    try {
      await updateConsent({ [key]: value });
      setConsents({ ...consents, [key]: value });

      // 同步到 zustand store
      const storeKey = key.replace('consent_', '') as keyof Parameters<typeof setConsent>[0];
      setConsent({ [storeKey]: value });

      if (!value && key === 'consent_genital_data') {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
        Alert.alert('已撤回', '私密数据已被永久删除');
      }
    } catch (err: any) {
      const msg = err?.response?.data?.detail || '更新失败';
      Alert.alert('错误', msg);
      // 恢复状态
      await loadConsents();
    }
    setUpdating(null);
  };

  if (loading) {
    return (
      <View style={s.loadingWrap}>
        <ActivityIndicator color="#6366F1" size="large" />
      </View>
    );
  }

  return (
    <View style={s.container}>
      <Text style={s.title}>隐私同意管理</Text>
      <Text style={s.subtitle}>
        您可以随时更改以下设置。某些更改是不可逆的。
      </Text>

      {CONSENT_ITEMS.map((item, i) => (
        <Animated.View
          key={item.key}
          entering={FadeInUp.delay(i * 80).duration(400)}
          style={[s.card, item.dangerous && !consents[item.key] && s.cardDanger]}
        >
          <View style={s.cardHeader}>
            <View style={{ flex: 1 }}>
              <Text style={s.cardLabel}>
                {item.label}
                {!item.editable && <Text style={s.requiredTag}> 必须</Text>}
              </Text>
              <Text style={s.cardDesc}>{item.description}</Text>
            </View>
            <View style={s.switchWrap}>
              {updating === item.key ? (
                <ActivityIndicator color="#6366F1" size="small" />
              ) : (
                <Switch
                  value={consents[item.key] ?? false}
                  onValueChange={(v) => handleToggle(item, v)}
                  disabled={!item.editable}
                  trackColor={{ false: '#374151', true: '#6366F1' }}
                  thumbColor={consents[item.key] ? '#E0E7FF' : '#9CA3AF'}
                  ios_backgroundColor="#374151"
                />
              )}
            </View>
          </View>
        </Animated.View>
      ))}
    </View>
  );
}

const s = StyleSheet.create({
  container: { paddingHorizontal: 0 },
  loadingWrap: { paddingVertical: 40, alignItems: 'center' },
  title: { color: '#E0E7FF', fontSize: 18, fontWeight: '800', marginBottom: 6 },
  subtitle: { color: '#64748B', fontSize: 13, marginBottom: 20, lineHeight: 19 },

  card: {
    backgroundColor: 'rgba(30,27,75,0.5)',
    borderRadius: 14,
    padding: 16,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: 'rgba(99,102,241,0.12)',
  },
  cardDanger: {
    borderColor: 'rgba(239,68,68,0.2)',
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  cardLabel: { color: '#E0E7FF', fontSize: 15, fontWeight: '700', marginBottom: 4 },
  requiredTag: { color: '#6366F1', fontSize: 11, fontWeight: '600' },
  cardDesc: { color: '#94A3B8', fontSize: 12, lineHeight: 18 },
  switchWrap: { width: 52, alignItems: 'center' },
});
