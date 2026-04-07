// ============================================================
// Screen 2: RatingFlowScreen
// 分步评分流程 (5步):
//   Step 0: 上传面部照片
//   Step 1: AI评分进行中 (动画)
//   Step 2: 身高 / 体重 / 身材照片
//   Step 3: 私密自测数据 (可选，需consent)
//   Step 4: 总分展示 + breakdown
// ============================================================

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  TextInput,
  TouchableOpacity,
  Image,
  Alert,
  StyleSheet,
  Dimensions,
} from 'react-native';
import Animated, {
  FadeInUp,
  FadeInRight,
  FadeOutLeft,
  useSharedValue,
  useAnimatedStyle,
  withRepeat,
  withTiming,
  withSequence,
  Easing,
} from 'react-native-reanimated';
import { LinearGradient } from 'expo-linear-gradient';
import * as ImagePicker from 'expo-image-picker';
import * as Haptics from 'expo-haptics';

import Button from '../../components/ui/Button';
import ProgressBar from '../../components/ui/ProgressBar';
import ScoreCard from '../../components/score/ScoreCard';
import RadarChart from '../../components/score/RadarChart';
import { useStore } from '../../store';
import { calculateScore } from '../../lib/api';
import { SCORE_DIMENSIONS, SCORE_LABELS } from '../../lib/constants';
import type { ScoreResponse, RadarDataPoint, SelfMeasurements } from '../../types';

const { width: SW } = Dimensions.get('window');
const STEPS = 5;

// ---- 扫描动画组件 ----
function ScanAnimation() {
  const lineY = useSharedValue(0);
  const pulse = useSharedValue(1);

  useEffect(() => {
    lineY.value = withRepeat(
      withTiming(1, { duration: 2000, easing: Easing.inOut(Easing.ease) }),
      -1, true
    );
    pulse.value = withRepeat(
      withSequence(
        withTiming(1.15, { duration: 800 }),
        withTiming(1, { duration: 800 }),
      ),
      -1
    );
  }, []);

  const lineStyle = useAnimatedStyle(() => ({
    top: `${lineY.value * 80 + 10}%`,
  }));
  const pulseStyle = useAnimatedStyle(() => ({
    transform: [{ scale: pulse.value }],
    opacity: 2 - pulse.value,
  }));

  return (
    <View style={scan.container}>
      <Animated.View style={[scan.ring, pulseStyle]} />
      <Text style={scan.icon}>🔬</Text>
      <Animated.View style={[scan.line, lineStyle]} />
      <Text style={scan.text}>AI 正在分析你的照片...</Text>
      <Text style={scan.sub}>ViT-FBP 面部美学 + MediaPipe 身材比例</Text>
    </View>
  );
}

const scan = StyleSheet.create({
  container: { alignItems: 'center', paddingVertical: 60, position: 'relative' },
  ring: {
    width: 140,
    height: 140,
    borderRadius: 70,
    borderWidth: 3,
    borderColor: '#6366F1',
    position: 'absolute',
    top: 40,
  },
  icon: { fontSize: 64, marginBottom: 24 },
  line: {
    position: 'absolute',
    left: '15%',
    width: '70%',
    height: 2,
    backgroundColor: '#6366F1',
    shadowColor: '#6366F1',
    shadowRadius: 8,
    shadowOpacity: 0.8,
  },
  text: { color: '#C7D2FE', fontSize: 18, fontWeight: '700', marginTop: 20 },
  sub: { color: '#64748B', fontSize: 13, marginTop: 6 },
});

// ---- 主组件 ----
export default function RatingFlowScreen() {
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const { consent, latestScore, setLatestScore } = useStore();

  // 数据
  const [faceUri, setFaceUri] = useState('');
  const [bodyUri, setBodyUri] = useState('');
  const [height, setHeight] = useState('');
  const [weight, setWeight] = useState('');
  const [ethnicity, setEthnicity] = useState('');
  const [selfData, setSelfData] = useState<SelfMeasurements>({});
  const [result, setResult] = useState<ScoreResponse | null>(null);

  const pickImage = useCallback(async (setter: (uri: string) => void) => {
    const res = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 0.8,
      allowsEditing: true,
      aspect: [3, 4],
    });
    if (!res.canceled && res.assets[0]) {
      setter(res.assets[0].uri);
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    }
  }, []);

  const startScoring = async () => {
    if (!faceUri) { Alert.alert('提示', '请先上传面部照片'); return; }
    if (!height || parseFloat(height) < 100) { Alert.alert('提示', '请输入有效身高'); return; }

    setStep(1); // 进入扫描动画
    setLoading(true);

    try {
      // 实际场景: 先上传图片到Supabase Storage获得URL
      // 这里用本地URI占位
      const payload = {
        face_photo_url: faceUri,
        body_photo_url: bodyUri || undefined,
        height_cm: parseFloat(height),
        weight_kg: weight ? parseFloat(weight) : undefined,
        ethnicity: ethnicity || undefined,
        self_measurements: consent.genital_data && Object.keys(selfData).length > 0
          ? selfData
          : undefined,
      };

      const resp = await calculateScore(payload);
      setResult(resp.data);
      setLatestScore(resp.data);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      setStep(4); // 跳到结果
    } catch (err: any) {
      Alert.alert('评分失败', err?.response?.data?.detail || '请稍后重试');
      setStep(0); // 回到第一步
    } finally {
      setLoading(false);
    }
  };

  const handleNext = () => {
    if (step === 0) {
      setStep(2); // 跳过动画步骤, 进入body data
    } else if (step === 2) {
      if (consent.genital_data) {
        setStep(3); // 进入私密数据
      } else {
        startScoring(); // 直接评分
      }
    } else if (step === 3) {
      startScoring();
    }
  };

  const resetFlow = () => {
    setStep(0);
    setFaceUri('');
    setBodyUri('');
    setResult(null);
  };

  // ---- 构建雷达图数据 ----
  const buildRadarData = (r: ScoreResponse): RadarDataPoint[] => {
    const dims = SCORE_DIMENSIONS;
    return [
      { label: dims.face.label, value: r.breakdown.face.weighted_score / dims.face.max, rawScore: r.breakdown.face.weighted_score, maxScore: dims.face.max, color: dims.face.color },
      { label: dims.body.label, value: r.breakdown.body.weighted_score / dims.body.max, rawScore: r.breakdown.body.weighted_score, maxScore: dims.body.max, color: dims.body.color },
      { label: dims.height.label, value: r.breakdown.height.weighted_score / dims.height.max, rawScore: r.breakdown.height.weighted_score, maxScore: dims.height.max, color: dims.height.color },
      { label: dims.skin_hair.label, value: r.breakdown.skin_hair.weighted_score / dims.skin_hair.max, rawScore: r.breakdown.skin_hair.weighted_score, maxScore: dims.skin_hair.max, color: dims.skin_hair.color },
      { label: dims.genital.label, value: r.breakdown.genital.weighted_score / dims.genital.max, rawScore: r.breakdown.genital.weighted_score, maxScore: dims.genital.max, color: dims.genital.color },
    ];
  };

  // ---- Step 渲染 ----
  const renderStep = () => {
    switch (step) {
      // ---- Step 0: 上传面部照片 ----
      case 0:
        return (
          <Animated.View entering={FadeInRight.duration(400)} exiting={FadeOutLeft} key="s0">
            <Text style={s.stepTitle}>上传正面照片</Text>
            <Text style={s.stepSub}>请上传一张光线充足的正面免冠照</Text>

            <TouchableOpacity onPress={() => pickImage(setFaceUri)} activeOpacity={0.8}>
              <View style={[s.uploadBox, faceUri ? s.uploadBoxFilled : null]}>
                {faceUri ? (
                  <Image source={{ uri: faceUri }} style={s.previewImg} />
                ) : (
                  <>
                    <Text style={s.uploadIcon}>📸</Text>
                    <Text style={s.uploadText}>点击上传面部照片</Text>
                    <Text style={s.uploadHint}>建议: 自然光 + 正面 + 无墨镜</Text>
                  </>
                )}
              </View>
            </TouchableOpacity>

            {faceUri && (
              <TouchableOpacity onPress={() => setFaceUri('')}>
                <Text style={s.reupload}>重新选择</Text>
              </TouchableOpacity>
            )}
          </Animated.View>
        );

      // ---- Step 1: AI扫描动画 ----
      case 1:
        return (
          <Animated.View entering={FadeInUp.duration(600)} key="s1">
            <ScanAnimation />
          </Animated.View>
        );

      // ---- Step 2: 身体数据 ----
      case 2:
        return (
          <Animated.View entering={FadeInRight.duration(400)} exiting={FadeOutLeft} key="s2">
            <Text style={s.stepTitle}>身体数据</Text>
            <Text style={s.stepSub}>用于身高评分和身材比例分析</Text>

            <View style={s.inputRow}>
              <View style={s.inputHalf}>
                <Text style={s.label}>身高 (cm) *</Text>
                <TextInput
                  style={s.input}
                  placeholder="178"
                  placeholderTextColor="#4B5563"
                  keyboardType="numeric"
                  value={height}
                  onChangeText={setHeight}
                />
              </View>
              <View style={s.inputHalf}>
                <Text style={s.label}>体重 (kg)</Text>
                <TextInput
                  style={s.input}
                  placeholder="70"
                  placeholderTextColor="#4B5563"
                  keyboardType="numeric"
                  value={weight}
                  onChangeText={setWeight}
                />
              </View>
            </View>

            <View style={s.formGroup}>
              <Text style={s.label}>族裔（用于东亚脸优化）</Text>
              <View style={s.chipRow}>
                {['chinese', 'japanese', 'korean', 'other'].map((e) => (
                  <TouchableOpacity
                    key={e}
                    onPress={() => setEthnicity(e)}
                    style={[s.chip, ethnicity === e && s.chipActive]}
                  >
                    <Text style={[s.chipText, ethnicity === e && s.chipTextActive]}>
                      {e === 'chinese' ? '华人' : e === 'japanese' ? '日本' : e === 'korean' ? '韩国' : '其他'}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            {/* 身材照片 (可选) */}
            <Text style={s.label}>身材照片（可选, 获取完整WHR/SHR分析）</Text>
            <TouchableOpacity onPress={() => pickImage(setBodyUri)} activeOpacity={0.8}>
              <View style={[s.uploadBoxSmall, bodyUri ? s.uploadBoxFilled : null]}>
                {bodyUri ? (
                  <Image source={{ uri: bodyUri }} style={s.previewSmall} />
                ) : (
                  <Text style={s.uploadText}>📷 上传全身站立照</Text>
                )}
              </View>
            </TouchableOpacity>
          </Animated.View>
        );

      // ---- Step 3: 私密自测 ----
      case 3:
        return (
          <Animated.View entering={FadeInRight.duration(400)} exiting={FadeOutLeft} key="s3">
            <Text style={s.stepTitle}>🔒 私密自测数据</Text>
            <Text style={s.stepSub}>所有数据 AES-256-GCM 加密存储，仅限本人查看</Text>

            <View style={s.privacyBadge}>
              <Text style={s.privacyBadgeText}>🔐 端到端加密 · 不接受照片 · 可随时删除</Text>
            </View>

            <View style={s.inputRow}>
              <View style={s.inputHalf}>
                <Text style={s.label}>长度 (cm)</Text>
                <TextInput
                  style={s.input}
                  placeholder="—"
                  placeholderTextColor="#4B5563"
                  keyboardType="numeric"
                  onChangeText={(v) => setSelfData({ ...selfData, penis_length_cm: parseFloat(v) || undefined })}
                />
              </View>
              <View style={s.inputHalf}>
                <Text style={s.label}>周长 (cm)</Text>
                <TextInput
                  style={s.input}
                  placeholder="—"
                  placeholderTextColor="#4B5563"
                  keyboardType="numeric"
                  onChangeText={(v) => setSelfData({ ...selfData, penis_girth_cm: parseFloat(v) || undefined })}
                />
              </View>
            </View>

            <View style={s.inputRow}>
              <View style={s.inputHalf}>
                <Text style={s.label}>修饰程度 (1-5)</Text>
                <TextInput
                  style={s.input}
                  placeholder="3"
                  placeholderTextColor="#4B5563"
                  keyboardType="numeric"
                  onChangeText={(v) => setSelfData({ ...selfData, grooming_level: parseInt(v) || undefined })}
                />
              </View>
              <View style={s.inputHalf}>
                <Text style={s.label}>自评 (1-10)</Text>
                <TextInput
                  style={s.input}
                  placeholder="7"
                  placeholderTextColor="#4B5563"
                  keyboardType="numeric"
                  onChangeText={(v) => setSelfData({ ...selfData, self_rating: parseInt(v) || undefined })}
                />
              </View>
            </View>

            <Text style={s.skipHint}>所有字段均可选，留空不影响评分</Text>
          </Animated.View>
        );

      // ---- Step 4: 结果 ----
      case 4:
        if (!result) return null;
        const labelStyle = SCORE_LABELS[result.score_label] || SCORE_LABELS['良好'];
        return (
          <Animated.View entering={FadeInUp.duration(600)} key="s4">
            {/* 总分头部 */}
            <View style={s.resultHeader}>
              <Animated.Text entering={FadeInUp.delay(200).duration(600)} style={s.totalScore}>
                {result.total_score.toFixed(1)}
              </Animated.Text>
              <Text style={s.totalMax}>/100</Text>
              <View style={[s.labelBadge, { backgroundColor: labelStyle.bg }]}>
                <Text style={[s.labelText, { color: labelStyle.color }]}>
                  {result.score_label}
                </Text>
              </View>
              <Text style={s.percentile}>{result.percentile}</Text>
            </View>

            {/* 雷达图 */}
            <RadarChart data={buildRadarData(result)} size={280} />

            {/* 各维度详情 */}
            <Text style={s.sectionTitle}>评分详情</Text>
            <ScoreCard
              icon={SCORE_DIMENSIONS.face.icon}
              label={SCORE_DIMENSIONS.face.label}
              score={result.breakdown.face.weighted_score}
              maxScore={SCORE_DIMENSIONS.face.max}
              color={SCORE_DIMENSIONS.face.color}
              feedback={result.face_feedback}
              index={0}
            />
            <ScoreCard
              icon={SCORE_DIMENSIONS.body.icon}
              label={SCORE_DIMENSIONS.body.label}
              score={result.breakdown.body.weighted_score}
              maxScore={SCORE_DIMENSIONS.body.max}
              color={SCORE_DIMENSIONS.body.color}
              feedback={result.body_feedback}
              index={1}
            />
            <ScoreCard
              icon={SCORE_DIMENSIONS.height.icon}
              label={SCORE_DIMENSIONS.height.label}
              score={result.breakdown.height.weighted_score}
              maxScore={SCORE_DIMENSIONS.height.max}
              color={SCORE_DIMENSIONS.height.color}
              feedback={result.height_feedback}
              index={2}
            />
            <ScoreCard
              icon={SCORE_DIMENSIONS.skin_hair.icon}
              label={SCORE_DIMENSIONS.skin_hair.label}
              score={result.breakdown.skin_hair.weighted_score}
              maxScore={SCORE_DIMENSIONS.skin_hair.max}
              color={SCORE_DIMENSIONS.skin_hair.color}
              feedback={result.skin_hair_feedback}
              index={3}
            />
            <ScoreCard
              icon={SCORE_DIMENSIONS.genital.icon}
              label={SCORE_DIMENSIONS.genital.label}
              score={result.breakdown.genital.weighted_score}
              maxScore={SCORE_DIMENSIONS.genital.max}
              color={SCORE_DIMENSIONS.genital.color}
              feedback={result.genital_feedback}
              index={4}
            />

            {/* 改善建议 */}
            {result.improvement_tips.length > 0 && (
              <Animated.View entering={FadeInUp.delay(600)} style={s.tipsBox}>
                <Text style={s.tipsTitle}>💡 改善建议</Text>
                {result.improvement_tips.map((tip, i) => (
                  <Text key={i} style={s.tipItem}>• {tip}</Text>
                ))}
              </Animated.View>
            )}

            {/* 东亚脸专项 */}
            {result.east_asian_notes.length > 0 && (
              <Animated.View entering={FadeInUp.delay(800)} style={s.eastAsianBox}>
                <Text style={s.tipsTitle}>🌏 东亚面孔专项建议</Text>
                {result.east_asian_notes.map((note, i) => (
                  <Text key={i} style={s.tipItem}>• {note}</Text>
                ))}
              </Animated.View>
            )}

            <Button title="重新评分" onPress={resetFlow} variant="outline" style={{ marginTop: 20 }} />
          </Animated.View>
        );
    }
  };

  return (
    <View style={s.screen}>
      {/* 进度条 (结果页不显示) */}
      {step < 4 && (
        <View style={s.progressWrap}>
          <ProgressBar
            progress={
              step === 0 ? 0.2 : step === 1 ? 0.5 : step === 2 ? 0.7 : 0.9
            }
          />
        </View>
      )}

      <ScrollView
        contentContainerStyle={s.scroll}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        {renderStep()}
      </ScrollView>

      {/* 底部按钮 (动画步和结果页不显示) */}
      {step !== 1 && step !== 4 && (
        <View style={s.footer}>
          {step > 0 && step !== 2 && (
            <Button title="返回" onPress={() => setStep(step - 1)} variant="ghost" style={{ flex: 1 }} />
          )}
          <Button
            title={
              step === 2
                ? consent.genital_data ? '下一步' : '开始AI评分'
                : step === 3
                  ? '开始AI评分'
                  : '下一步'
            }
            onPress={handleNext}
            disabled={step === 0 && !faceUri}
            loading={loading}
            style={{ flex: 2 }}
            size="lg"
          />
        </View>
      )}
    </View>
  );
}

// ============================================================
const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#0F0D2E' },
  progressWrap: { paddingHorizontal: 24, paddingTop: 60 },
  scroll: { paddingHorizontal: 24, paddingTop: 24, paddingBottom: 60 },
  stepTitle: { color: '#E0E7FF', fontSize: 24, fontWeight: '800', textAlign: 'center', marginBottom: 6 },
  stepSub: { color: '#94A3B8', fontSize: 14, textAlign: 'center', marginBottom: 24 },

  // Upload
  uploadBox: {
    height: 320,
    borderRadius: 20,
    borderWidth: 2,
    borderStyle: 'dashed',
    borderColor: 'rgba(99,102,241,0.3)',
    backgroundColor: 'rgba(30,27,75,0.4)',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  uploadBoxFilled: { borderStyle: 'solid', borderColor: '#6366F1' },
  uploadBoxSmall: {
    height: 120,
    borderRadius: 16,
    borderWidth: 1.5,
    borderStyle: 'dashed',
    borderColor: 'rgba(99,102,241,0.25)',
    backgroundColor: 'rgba(30,27,75,0.3)',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
    marginTop: 8,
  },
  previewImg: { width: '100%', height: '100%', borderRadius: 18 },
  previewSmall: { width: '100%', height: '100%', borderRadius: 14 },
  uploadIcon: { fontSize: 48, marginBottom: 12 },
  uploadText: { color: '#94A3B8', fontSize: 15, fontWeight: '600' },
  uploadHint: { color: '#64748B', fontSize: 12, marginTop: 6 },
  reupload: { color: '#6366F1', fontSize: 14, textAlign: 'center', marginTop: 12, fontWeight: '600' },

  // Form
  inputRow: { flexDirection: 'row', gap: 12, marginBottom: 16 },
  inputHalf: { flex: 1 },
  formGroup: { marginBottom: 16 },
  label: { color: '#C7D2FE', fontSize: 13, fontWeight: '600', marginBottom: 6 },
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
  chipRow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  chip: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: 'rgba(99,102,241,0.2)',
  },
  chipActive: { backgroundColor: 'rgba(99,102,241,0.15)', borderColor: '#6366F1' },
  chipText: { color: '#94A3B8', fontSize: 13, fontWeight: '600' },
  chipTextActive: { color: '#C7D2FE' },

  // Privacy
  privacyBadge: {
    backgroundColor: 'rgba(139,92,246,0.1)',
    borderRadius: 10,
    padding: 12,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: 'rgba(139,92,246,0.2)',
  },
  privacyBadgeText: { color: '#C4B5FD', fontSize: 12, textAlign: 'center', fontWeight: '600' },
  skipHint: { color: '#64748B', fontSize: 12, textAlign: 'center', marginTop: 12, fontStyle: 'italic' },

  // Results
  resultHeader: { alignItems: 'center', paddingVertical: 20 },
  totalScore: { color: '#E0E7FF', fontSize: 72, fontWeight: '900' },
  totalMax: { color: '#64748B', fontSize: 20, marginTop: -10, marginBottom: 10 },
  labelBadge: { paddingHorizontal: 16, paddingVertical: 6, borderRadius: 20 },
  labelText: { fontSize: 14, fontWeight: '700' },
  percentile: { color: '#6366F1', fontSize: 16, fontWeight: '700', marginTop: 8 },
  sectionTitle: { color: '#C7D2FE', fontSize: 18, fontWeight: '700', marginTop: 24, marginBottom: 14 },

  // Tips
  tipsBox: {
    backgroundColor: 'rgba(30,27,75,0.5)',
    borderRadius: 16,
    padding: 16,
    marginTop: 16,
    borderWidth: 1,
    borderColor: 'rgba(99,102,241,0.12)',
  },
  eastAsianBox: {
    backgroundColor: 'rgba(20,184,166,0.08)',
    borderRadius: 16,
    padding: 16,
    marginTop: 12,
    borderWidth: 1,
    borderColor: 'rgba(20,184,166,0.15)',
  },
  tipsTitle: { color: '#C7D2FE', fontSize: 15, fontWeight: '700', marginBottom: 10 },
  tipItem: { color: '#94A3B8', fontSize: 13, lineHeight: 20, marginBottom: 6 },

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
