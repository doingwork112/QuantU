// ============================================================
// Screen 3: ProfileScreen
// 100分雷达图 + 各模块 breakdown + 用户资料
// ============================================================

import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  Image,
  RefreshControl,
  StyleSheet,
} from 'react-native';
import Animated, { FadeInUp } from 'react-native-reanimated';
import { LinearGradient } from 'expo-linear-gradient';

import RadarChart from '../../components/score/RadarChart';
import ScoreCard from '../../components/score/ScoreCard';
import Button from '../../components/ui/Button';
import ProgressBar from '../../components/ui/ProgressBar';
import { useStore } from '../../store';
import { getProfile } from '../../lib/api';
import { SCORE_DIMENSIONS, SCORE_LABELS } from '../../lib/constants';
import type { RadarDataPoint, ScoreResponse } from '../../types';

// ---- 统计卡片 ----
function StatChip({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <View style={s.statChip}>
      <Text style={[s.statValue, { color }]}>{value}</Text>
      <Text style={s.statLabel}>{label}</Text>
    </View>
  );
}

// ---- 详细指标行 ----
function MetricRow({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <View style={s.metricRow}>
      <Text style={s.metricLabel}>{label}</Text>
      <Text style={s.metricValue}>
        {value}
        {unit && <Text style={s.metricUnit}> {unit}</Text>}
      </Text>
    </View>
  );
}

export default function ProfileScreen() {
  const { latestScore, user, profile, setProfile } = useStore();
  const [refreshing, setRefreshing] = useState(false);

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      const resp = await getProfile();
      setProfile(resp.data);
    } catch {}
    setRefreshing(false);
  };

  useEffect(() => { onRefresh(); }, []);

  const score = latestScore;
  const dims = SCORE_DIMENSIONS;

  const radarData: RadarDataPoint[] = score
    ? [
        { label: dims.face.label, value: score.breakdown.face.weighted_score / dims.face.max, rawScore: score.breakdown.face.weighted_score, maxScore: dims.face.max, color: dims.face.color },
        { label: dims.body.label, value: score.breakdown.body.weighted_score / dims.body.max, rawScore: score.breakdown.body.weighted_score, maxScore: dims.body.max, color: dims.body.color },
        { label: dims.height.label, value: score.breakdown.height.weighted_score / dims.height.max, rawScore: score.breakdown.height.weighted_score, maxScore: dims.height.max, color: dims.height.color },
        { label: dims.skin_hair.label, value: score.breakdown.skin_hair.weighted_score / dims.skin_hair.max, rawScore: score.breakdown.skin_hair.weighted_score, maxScore: dims.skin_hair.max, color: dims.skin_hair.color },
        { label: dims.genital.label, value: score.breakdown.genital.weighted_score / dims.genital.max, rawScore: score.breakdown.genital.weighted_score, maxScore: dims.genital.max, color: dims.genital.color },
      ]
    : [];

  const labelStyle = score
    ? SCORE_LABELS[score.score_label] || SCORE_LABELS['良好']
    : { color: '#94A3B8', bg: '#1E293B' };

  return (
    <ScrollView
      style={s.screen}
      contentContainerStyle={s.scroll}
      showsVerticalScrollIndicator={false}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#6366F1" />}
    >
      {/* ---- 头部 ---- */}
      <Animated.View entering={FadeInUp.duration(500)} style={s.header}>
        <View style={s.avatarWrap}>
          {profile?.avatar_url ? (
            <Image source={{ uri: profile.avatar_url }} style={s.avatar} />
          ) : (
            <LinearGradient colors={['#6366F1', '#8B5CF6']} style={s.avatar}>
              <Text style={s.avatarText}>
                {(user?.display_name || '?')[0].toUpperCase()}
              </Text>
            </LinearGradient>
          )}
        </View>
        <Text style={s.name}>{user?.display_name || '用户'}</Text>
        {profile?.city && <Text style={s.location}>📍 {profile.city}</Text>}
      </Animated.View>

      {/* ---- 评分概览 ---- */}
      {score ? (
        <>
          <Animated.View entering={FadeInUp.delay(150).duration(500)} style={s.scoreOverview}>
            <View style={s.scoreHeader}>
              <View>
                <Text style={s.overviewTotal}>{score.total_score.toFixed(1)}</Text>
                <Text style={s.overviewMax}>/100</Text>
              </View>
              <View style={{ alignItems: 'flex-end' }}>
                <View style={[s.badge, { backgroundColor: labelStyle.bg }]}>
                  <Text style={[s.badgeText, { color: labelStyle.color }]}>{score.score_label}</Text>
                </View>
                <Text style={s.percentileText}>{score.percentile}</Text>
              </View>
            </View>

            <View style={s.statsRow}>
              <StatChip
                label="美学"
                value={`${score.breakdown.face.aesthetic.toFixed(1)}`}
                color={dims.face.color}
              />
              <StatChip
                label="对称性"
                value={`${score.breakdown.face.symmetry.toFixed(1)}`}
                color="#14B8A6"
              />
              <StatChip
                label="黄金比例"
                value={`${score.breakdown.face.golden_ratio.toFixed(1)}`}
                color="#F59E0B"
              />
              <StatChip
                label="体态"
                value={`${score.breakdown.body.posture.toFixed(1)}`}
                color={dims.body.color}
              />
            </View>
          </Animated.View>

          {/* ---- 雷达图 ---- */}
          <Animated.View entering={FadeInUp.delay(300).duration(500)}>
            <Text style={s.sectionTitle}>五维评分</Text>
            <RadarChart data={radarData} size={280} />
          </Animated.View>

          {/* ---- 各维度卡片 ---- */}
          <Animated.View entering={FadeInUp.delay(500).duration(500)}>
            <Text style={s.sectionTitle}>评分详情</Text>
            <ScoreCard icon={dims.face.icon} label={dims.face.label} score={score.breakdown.face.weighted_score} maxScore={dims.face.max} color={dims.face.color} feedback={score.face_feedback} index={0} />
            <ScoreCard icon={dims.body.icon} label={dims.body.label} score={score.breakdown.body.weighted_score} maxScore={dims.body.max} color={dims.body.color} feedback={score.body_feedback} index={1} />
            <ScoreCard icon={dims.height.icon} label={dims.height.label} score={score.breakdown.height.weighted_score} maxScore={dims.height.max} color={dims.height.color} feedback={score.height_feedback} index={2} />
            <ScoreCard icon={dims.skin_hair.icon} label={dims.skin_hair.label} score={score.breakdown.skin_hair.weighted_score} maxScore={dims.skin_hair.max} color={dims.skin_hair.color} feedback={score.skin_hair_feedback} index={3} />
            <ScoreCard icon={dims.genital.icon} label={dims.genital.label} score={score.breakdown.genital.weighted_score} maxScore={dims.genital.max} color={dims.genital.color} feedback={score.genital_feedback} index={4} />
          </Animated.View>

          {/* ---- 身体指标 ---- */}
          {score.breakdown.body.metrics && (
            <Animated.View entering={FadeInUp.delay(700).duration(500)} style={s.metricsCard}>
              <Text style={s.cardTitle}>📐 身体指标</Text>
              {score.breakdown.body.metrics.bmi != null && (
                <MetricRow label="BMI" value={score.breakdown.body.metrics.bmi.toFixed(1)} />
              )}
              {score.breakdown.body.metrics.shr != null && (
                <MetricRow label="肩臀比 (SHR)" value={score.breakdown.body.metrics.shr.toFixed(2)} />
              )}
              {score.breakdown.body.metrics.whr != null && (
                <MetricRow label="腰臀比 (WHR)" value={score.breakdown.body.metrics.whr.toFixed(2)} />
              )}
              {score.breakdown.body.metrics.leg_body_ratio != null && (
                <MetricRow label="腿身比" value={score.breakdown.body.metrics.leg_body_ratio.toFixed(3)} />
              )}
              <MetricRow label="身高" value={`${score.breakdown.height.height_cm}`} unit="cm" />
            </Animated.View>
          )}

          {/* ---- 模型版本 ---- */}
          <Text style={s.modelVersion}>
            评分模型: {score.model_version} · {new Date(score.scored_at).toLocaleDateString()}
          </Text>
        </>
      ) : (
        /* 无评分 */
        <Animated.View entering={FadeInUp.delay(200)} style={s.emptyState}>
          <Text style={s.emptyIcon}>📊</Text>
          <Text style={s.emptyTitle}>尚无评分</Text>
          <Text style={s.emptySub}>完成AI评分后，这里会显示你的五维雷达图</Text>
        </Animated.View>
      )}
    </ScrollView>
  );
}

// ============================================================
const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#0F0D2E' },
  scroll: { paddingHorizontal: 24, paddingTop: 60, paddingBottom: 60 },

  // Header
  header: { alignItems: 'center', marginBottom: 24 },
  avatarWrap: { marginBottom: 12 },
  avatar: { width: 80, height: 80, borderRadius: 40, alignItems: 'center', justifyContent: 'center' },
  avatarText: { color: '#fff', fontSize: 32, fontWeight: '800' },
  name: { color: '#E0E7FF', fontSize: 22, fontWeight: '800' },
  location: { color: '#94A3B8', fontSize: 13, marginTop: 4 },

  // Score overview
  scoreOverview: {
    backgroundColor: 'rgba(30,27,75,0.6)',
    borderRadius: 20,
    padding: 20,
    marginBottom: 24,
    borderWidth: 1,
    borderColor: 'rgba(99,102,241,0.15)',
  },
  scoreHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 },
  overviewTotal: { color: '#E0E7FF', fontSize: 48, fontWeight: '900' },
  overviewMax: { color: '#64748B', fontSize: 16, marginTop: -6 },
  badge: { paddingHorizontal: 12, paddingVertical: 4, borderRadius: 12 },
  badgeText: { fontSize: 13, fontWeight: '700' },
  percentileText: { color: '#6366F1', fontSize: 14, fontWeight: '700', marginTop: 6 },

  statsRow: { flexDirection: 'row', gap: 8 },
  statChip: {
    flex: 1,
    backgroundColor: 'rgba(99,102,241,0.08)',
    borderRadius: 12,
    paddingVertical: 10,
    alignItems: 'center',
  },
  statValue: { fontSize: 18, fontWeight: '800' },
  statLabel: { color: '#64748B', fontSize: 10, fontWeight: '600', marginTop: 2 },

  sectionTitle: { color: '#C7D2FE', fontSize: 18, fontWeight: '700', marginTop: 20, marginBottom: 14 },

  // Metrics
  metricsCard: {
    backgroundColor: 'rgba(30,27,75,0.5)',
    borderRadius: 16,
    padding: 16,
    marginTop: 8,
    borderWidth: 1,
    borderColor: 'rgba(99,102,241,0.12)',
  },
  cardTitle: { color: '#C7D2FE', fontSize: 15, fontWeight: '700', marginBottom: 12 },
  metricRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: 'rgba(99,102,241,0.08)' },
  metricLabel: { color: '#94A3B8', fontSize: 14 },
  metricValue: { color: '#E0E7FF', fontSize: 14, fontWeight: '700' },
  metricUnit: { color: '#64748B', fontWeight: '500' },

  modelVersion: { color: '#4B5563', fontSize: 11, textAlign: 'center', marginTop: 24 },

  // Empty
  emptyState: { alignItems: 'center', paddingVertical: 60 },
  emptyIcon: { fontSize: 48, marginBottom: 16 },
  emptyTitle: { color: '#C7D2FE', fontSize: 20, fontWeight: '700', marginBottom: 8 },
  emptySub: { color: '#64748B', fontSize: 14, textAlign: 'center', lineHeight: 21 },
});
