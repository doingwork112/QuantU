// ============================================================
// Screen 4: MatchesScreen (Discover)
// 卡片式滑动匹配，显示兼容百分比
// ============================================================

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  Image,
  Dimensions,
  RefreshControl,
  FlatList,
  StyleSheet,
} from 'react-native';
import Animated, {
  FadeInUp,
  FadeInDown,
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  withTiming,
  runOnJS,
  Easing,
} from 'react-native-reanimated';
import {
  Gesture,
  GestureDetector,
} from 'react-native-gesture-handler';
import { LinearGradient } from 'expo-linear-gradient';
import * as Haptics from 'expo-haptics';

import Button from '../../components/ui/Button';
import ProgressBar from '../../components/ui/ProgressBar';
import { getMatches } from '../../lib/api';
import type { MatchItem } from '../../types';

const { width: SW, height: SH } = Dimensions.get('window');
const CARD_W = SW - 48;
const CARD_H = SH * 0.55;
const SWIPE_THRESHOLD = SW * 0.3;

// ---- 兼容性环形指示器 ----
function CompatRing({ pct, size = 56 }: { pct: number; size?: number }) {
  const color = pct >= 80 ? '#10B981' : pct >= 60 ? '#6366F1' : pct >= 40 ? '#F59E0B' : '#EF4444';
  return (
    <View style={[ring.container, { width: size, height: size }]}>
      <View style={[ring.track, { width: size, height: size, borderRadius: size / 2 }]}>
        <View style={[ring.fill, {
          width: size, height: size, borderRadius: size / 2,
          borderColor: color,
          borderTopColor: color,
          borderRightColor: pct > 25 ? color : 'transparent',
          borderBottomColor: pct > 50 ? color : 'transparent',
          borderLeftColor: pct > 75 ? color : 'transparent',
        }]} />
      </View>
      <Text style={[ring.text, { color, fontSize: size * 0.28 }]}>{Math.round(pct)}%</Text>
    </View>
  );
}

const ring = StyleSheet.create({
  container: { alignItems: 'center', justifyContent: 'center', position: 'relative' },
  track: {
    borderWidth: 3,
    borderColor: 'rgba(99,102,241,0.12)',
    position: 'absolute',
  },
  fill: { borderWidth: 3, position: 'absolute' },
  text: { fontWeight: '800' },
});

// ---- 兼容性明细条 ----
function CompatBar({ label, value }: { label: string; value: number }) {
  return (
    <View style={s.compatRow}>
      <Text style={s.compatLabel}>{label}</Text>
      <View style={s.compatBarTrack}>
        <ProgressBar progress={value / 100} height={4} />
      </View>
      <Text style={s.compatValue}>{value.toFixed(0)}</Text>
    </View>
  );
}

// ---- 可滑动匹配卡片 ----
function SwipeCard({
  item,
  onSwipeLeft,
  onSwipeRight,
}: {
  item: MatchItem;
  onSwipeLeft: () => void;
  onSwipeRight: () => void;
}) {
  const translateX = useSharedValue(0);
  const translateY = useSharedValue(0);
  const rotate = useSharedValue(0);
  const scale = useSharedValue(1);
  const likeOpacity = useSharedValue(0);
  const passOpacity = useSharedValue(0);

  const swipeGesture = Gesture.Pan()
    .onUpdate((e) => {
      translateX.value = e.translationX;
      translateY.value = e.translationY * 0.3;
      rotate.value = e.translationX * 0.05;
      likeOpacity.value = Math.max(0, e.translationX / SWIPE_THRESHOLD);
      passOpacity.value = Math.max(0, -e.translationX / SWIPE_THRESHOLD);
    })
    .onEnd((e) => {
      if (e.translationX > SWIPE_THRESHOLD) {
        // Like
        translateX.value = withTiming(SW * 1.5, { duration: 300 });
        runOnJS(Haptics.impactAsync)(Haptics.ImpactFeedbackStyle.Medium);
        runOnJS(onSwipeRight)();
      } else if (e.translationX < -SWIPE_THRESHOLD) {
        // Pass
        translateX.value = withTiming(-SW * 1.5, { duration: 300 });
        runOnJS(Haptics.impactAsync)(Haptics.ImpactFeedbackStyle.Light);
        runOnJS(onSwipeLeft)();
      } else {
        // 弹回
        translateX.value = withSpring(0);
        translateY.value = withSpring(0);
        rotate.value = withSpring(0);
        likeOpacity.value = withTiming(0);
        passOpacity.value = withTiming(0);
      }
    });

  const cardStyle = useAnimatedStyle(() => ({
    transform: [
      { translateX: translateX.value },
      { translateY: translateY.value },
      { rotate: `${rotate.value}deg` },
      { scale: scale.value },
    ],
  }));
  const likeStyle = useAnimatedStyle(() => ({ opacity: likeOpacity.value }));
  const passStyle = useAnimatedStyle(() => ({ opacity: passOpacity.value }));

  const bd = item.compatibility_breakdown;

  return (
    <GestureDetector gesture={swipeGesture}>
      <Animated.View style={[s.card, cardStyle]}>
        {/* 头像/背景 */}
        <View style={s.cardImageWrap}>
          {item.other_avatar_url ? (
            <Image source={{ uri: item.other_avatar_url }} style={s.cardImage} />
          ) : (
            <LinearGradient colors={['#312E81', '#4338CA']} style={s.cardImage}>
              <Text style={s.cardAvatarFallback}>
                {item.other_display_name[0]?.toUpperCase() || '?'}
              </Text>
            </LinearGradient>
          )}

          {/* LIKE / PASS 覆盖 */}
          <Animated.View style={[s.swipeLabel, s.likeLabel, likeStyle]}>
            <Text style={s.swipeLabelText}>LIKE 💚</Text>
          </Animated.View>
          <Animated.View style={[s.swipeLabel, s.passLabel, passStyle]}>
            <Text style={s.swipeLabelText}>PASS ✋</Text>
          </Animated.View>

          {/* 底部渐变 */}
          <LinearGradient
            colors={['transparent', 'rgba(15,13,46,0.95)']}
            style={s.cardGradient}
          />

          {/* 兼容度环 */}
          <View style={s.compatRingWrap}>
            <CompatRing pct={item.compatibility_pct} />
          </View>
        </View>

        {/* 信息区域 */}
        <View style={s.cardInfo}>
          <View style={s.cardNameRow}>
            <Text style={s.cardName}>{item.other_display_name}</Text>
            {item.other_age && <Text style={s.cardAge}>{item.other_age}岁</Text>}
          </View>

          {/* 兼容性 breakdown */}
          <View style={s.compatSection}>
            <Text style={s.compatTitle}>
              兼容度 {item.compatibility_pct.toFixed(1)}%
            </Text>
            <CompatBar label="评分相似" value={bd.score_similarity} />
            <CompatBar label="偏好匹配" value={bd.preference_match} />
            <CompatBar label="年龄兼容" value={bd.age_compatibility} />
            {bd.distance_km != null && (
              <View style={s.distRow}>
                <Text style={s.distText}>📍 {bd.distance_km.toFixed(1)} km</Text>
              </View>
            )}
          </View>

          {/* 状态 */}
          {item.status === 'matched' && (
            <View style={s.matchedBadge}>
              <Text style={s.matchedText}>💘 已匹配</Text>
            </View>
          )}
        </View>
      </Animated.View>
    </GestureDetector>
  );
}

// ---- 主组件 ----
export default function DiscoverScreen() {
  const [matches, setMatches] = useState<MatchItem[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'discover' | 'matched'>('discover');

  const loadMatches = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await getMatches(tab === 'discover' ? 'pending' : 'matched');
      setMatches(resp.data.matches);
      setCurrentIndex(0);
    } catch {}
    setLoading(false);
  }, [tab]);

  useEffect(() => { loadMatches(); }, [tab]);

  const handleSwipeLeft = () => {
    // TODO: POST action to backend
    setCurrentIndex((i) => i + 1);
  };
  const handleSwipeRight = () => {
    // TODO: POST action to backend
    setCurrentIndex((i) => i + 1);
  };

  const currentMatch = matches[currentIndex];
  const matchedList = matches.filter((m) => m.status === 'matched');

  return (
    <View style={s.screen}>
      {/* Tab切换 */}
      <Animated.View entering={FadeInDown.duration(400)} style={s.tabBar}>
        <TabButton label="发现" active={tab === 'discover'} onPress={() => setTab('discover')} />
        <TabButton label={`已匹配 (${matchedList.length})`} active={tab === 'matched'} onPress={() => setTab('matched')} />
      </Animated.View>

      {tab === 'discover' ? (
        /* ---- 发现: 卡片滑动 ---- */
        <View style={s.cardStack}>
          {currentMatch ? (
            <SwipeCard
              key={currentMatch.match_id}
              item={currentMatch}
              onSwipeLeft={handleSwipeLeft}
              onSwipeRight={handleSwipeRight}
            />
          ) : (
            <View style={s.emptyState}>
              <Text style={s.emptyIcon}>🔍</Text>
              <Text style={s.emptyTitle}>暂无更多推荐</Text>
              <Text style={s.emptySub}>完善资料和评分可获得更多匹配</Text>
              <Button title="刷新" onPress={loadMatches} variant="outline" style={{ marginTop: 20 }} />
            </View>
          )}

          {/* 底部操作按钮 */}
          {currentMatch && (
            <Animated.View entering={FadeInUp.delay(300)} style={s.actionRow}>
              <ActionBtn emoji="✋" label="Pass" color="#EF4444" onPress={handleSwipeLeft} />
              <ActionBtn emoji="⭐" label="Super" color="#F59E0B" onPress={handleSwipeRight} />
              <ActionBtn emoji="💚" label="Like" color="#10B981" onPress={handleSwipeRight} />
            </Animated.View>
          )}
        </View>
      ) : (
        /* ---- 已匹配列表 ---- */
        <FlatList
          data={matchedList}
          keyExtractor={(m) => m.match_id}
          contentContainerStyle={s.listContent}
          refreshControl={<RefreshControl refreshing={loading} onRefresh={loadMatches} tintColor="#6366F1" />}
          renderItem={({ item }) => (
            <View style={s.matchedCard}>
              <View style={s.matchedLeft}>
                {item.other_avatar_url ? (
                  <Image source={{ uri: item.other_avatar_url }} style={s.matchedAvatar} />
                ) : (
                  <LinearGradient colors={['#6366F1', '#8B5CF6']} style={s.matchedAvatar}>
                    <Text style={s.matchedAvatarText}>{item.other_display_name[0]}</Text>
                  </LinearGradient>
                )}
                <View style={{ flex: 1 }}>
                  <Text style={s.matchedName}>{item.other_display_name}</Text>
                  {item.other_age && <Text style={s.matchedAge}>{item.other_age}岁</Text>}
                </View>
              </View>
              <CompatRing pct={item.compatibility_pct} size={44} />
            </View>
          )}
          ListEmptyComponent={
            <View style={s.emptyState}>
              <Text style={s.emptyIcon}>💘</Text>
              <Text style={s.emptyTitle}>还没有匹配</Text>
              <Text style={s.emptySub}>在发现页滑动来开始匹配吧</Text>
            </View>
          }
        />
      )}
    </View>
  );
}

// ---- Tab按钮 ----
function TabButton({ label, active, onPress }: { label: string; active: boolean; onPress: () => void }) {
  return (
    <View style={{ flex: 1 }}>
      <Button
        title={label}
        onPress={onPress}
        variant={active ? 'primary' : 'ghost'}
        size="sm"
      />
    </View>
  );
}

// ---- 底部操作按钮 ----
function ActionBtn({ emoji, label, color, onPress }: { emoji: string; label: string; color: string; onPress: () => void }) {
  return (
    <View style={{ alignItems: 'center' }}>
      <View style={[s.actionBtnCircle, { borderColor: color }]}>
        <Button title={emoji} onPress={onPress} variant="ghost" size="sm" />
      </View>
      <Text style={[s.actionLabel, { color }]}>{label}</Text>
    </View>
  );
}

// ============================================================
const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#0F0D2E' },

  // Tabs
  tabBar: {
    flexDirection: 'row',
    gap: 8,
    paddingHorizontal: 24,
    paddingTop: 60,
    paddingBottom: 12,
  },

  // Card stack
  cardStack: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 24 },
  card: {
    width: CARD_W,
    backgroundColor: 'rgba(30,27,75,0.7)',
    borderRadius: 24,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(99,102,241,0.15)',
  },
  cardImageWrap: { height: CARD_H * 0.45, position: 'relative' },
  cardImage: { width: '100%', height: '100%', alignItems: 'center', justifyContent: 'center' },
  cardAvatarFallback: { color: '#C7D2FE', fontSize: 48, fontWeight: '800' },
  cardGradient: { position: 'absolute', bottom: 0, left: 0, right: 0, height: '50%' },
  compatRingWrap: { position: 'absolute', top: 16, right: 16 },

  // Swipe labels
  swipeLabel: {
    position: 'absolute',
    top: 24,
    paddingHorizontal: 20,
    paddingVertical: 8,
    borderRadius: 12,
    borderWidth: 3,
  },
  likeLabel: { left: 16, borderColor: '#10B981', backgroundColor: 'rgba(16,185,129,0.15)' },
  passLabel: { right: 16, borderColor: '#EF4444', backgroundColor: 'rgba(239,68,68,0.15)' },
  swipeLabelText: { fontSize: 22, fontWeight: '800' },

  // Card info
  cardInfo: { padding: 20 },
  cardNameRow: { flexDirection: 'row', alignItems: 'baseline', gap: 8, marginBottom: 12 },
  cardName: { color: '#E0E7FF', fontSize: 24, fontWeight: '800' },
  cardAge: { color: '#94A3B8', fontSize: 16 },

  // Compat section
  compatSection: { marginTop: 4 },
  compatTitle: { color: '#C7D2FE', fontSize: 14, fontWeight: '700', marginBottom: 10 },
  compatRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 },
  compatLabel: { color: '#94A3B8', fontSize: 12, width: 60 },
  compatBarTrack: { flex: 1 },
  compatValue: { color: '#C7D2FE', fontSize: 12, fontWeight: '700', width: 28, textAlign: 'right' },
  distRow: { marginTop: 4 },
  distText: { color: '#64748B', fontSize: 12 },

  matchedBadge: {
    marginTop: 12,
    backgroundColor: 'rgba(16,185,129,0.1)',
    borderRadius: 10,
    paddingVertical: 8,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: 'rgba(16,185,129,0.2)',
  },
  matchedText: { color: '#10B981', fontSize: 14, fontWeight: '700' },

  // Action buttons
  actionRow: { flexDirection: 'row', gap: 32, marginTop: 20, marginBottom: 20 },
  actionBtnCircle: {
    width: 60,
    height: 60,
    borderRadius: 30,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  actionLabel: { fontSize: 11, fontWeight: '600', marginTop: 4 },

  // Matched list
  listContent: { paddingHorizontal: 24, paddingBottom: 40 },
  matchedCard: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: 'rgba(30,27,75,0.5)',
    borderRadius: 16,
    padding: 16,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: 'rgba(99,102,241,0.12)',
  },
  matchedLeft: { flexDirection: 'row', alignItems: 'center', gap: 12, flex: 1 },
  matchedAvatar: { width: 48, height: 48, borderRadius: 24, alignItems: 'center', justifyContent: 'center' },
  matchedAvatarText: { color: '#fff', fontSize: 20, fontWeight: '700' },
  matchedName: { color: '#E0E7FF', fontSize: 16, fontWeight: '700' },
  matchedAge: { color: '#94A3B8', fontSize: 13 },

  // Empty
  emptyState: { alignItems: 'center', paddingVertical: 60 },
  emptyIcon: { fontSize: 48, marginBottom: 16 },
  emptyTitle: { color: '#C7D2FE', fontSize: 20, fontWeight: '700', marginBottom: 8 },
  emptySub: { color: '#64748B', fontSize: 14, textAlign: 'center', lineHeight: 21 },
});
