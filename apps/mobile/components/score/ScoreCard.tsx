import React, { useEffect } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withTiming,
  withDelay,
  Easing,
} from 'react-native-reanimated';
import { LinearGradient } from 'expo-linear-gradient';

interface Props {
  icon: string;
  label: string;
  score: number;
  maxScore: number;
  color: string;
  feedback: string;
  index?: number;
}

export default function ScoreCard({
  icon,
  label,
  score,
  maxScore,
  color,
  feedback,
  index = 0,
}: Props) {
  const barWidth = useSharedValue(0);
  const opacity = useSharedValue(0);
  const translateY = useSharedValue(20);

  useEffect(() => {
    const delay = index * 120;
    opacity.value = withDelay(delay, withTiming(1, { duration: 500 }));
    translateY.value = withDelay(delay, withTiming(0, { duration: 500, easing: Easing.out(Easing.cubic) }));
    barWidth.value = withDelay(
      delay + 200,
      withTiming(maxScore > 0 ? score / maxScore : 0, { duration: 800, easing: Easing.out(Easing.cubic) })
    );
  }, [score]);

  const cardAnim = useAnimatedStyle(() => ({
    opacity: opacity.value,
    transform: [{ translateY: translateY.value }],
  }));

  const barAnim = useAnimatedStyle(() => ({
    width: `${barWidth.value * 100}%`,
  }));

  const pct = maxScore > 0 ? ((score / maxScore) * 100).toFixed(0) : '0';

  return (
    <Animated.View style={[s.card, cardAnim]}>
      <View style={s.header}>
        <Text style={s.icon}>{icon}</Text>
        <View style={{ flex: 1 }}>
          <View style={s.row}>
            <Text style={s.label}>{label}</Text>
            <Text style={[s.score, { color }]}>
              {score.toFixed(1)}
              <Text style={s.max}>/{maxScore}</Text>
            </Text>
          </View>
          {/* 进度条 */}
          <View style={s.barTrack}>
            <Animated.View style={[s.barFill, barAnim]}>
              <LinearGradient
                colors={[color, `${color}99`]}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 0 }}
                style={s.gradient}
              />
            </Animated.View>
          </View>
        </View>
        <Text style={[s.pct, { color }]}>{pct}%</Text>
      </View>
      <Text style={s.feedback} numberOfLines={2}>{feedback}</Text>
    </Animated.View>
  );
}

const s = StyleSheet.create({
  card: {
    backgroundColor: 'rgba(30,27,75,0.6)',
    borderRadius: 16,
    padding: 16,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: 'rgba(99,102,241,0.15)',
  },
  header: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  icon: { fontSize: 24 },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 },
  label: { color: '#C7D2FE', fontSize: 14, fontWeight: '600' },
  score: { fontSize: 18, fontWeight: '800' },
  max: { fontSize: 12, color: '#64748B', fontWeight: '500' },
  barTrack: {
    height: 5,
    backgroundColor: 'rgba(99,102,241,0.12)',
    borderRadius: 999,
    overflow: 'hidden',
  },
  barFill: { height: '100%', borderRadius: 999, overflow: 'hidden' },
  gradient: { flex: 1 },
  pct: { fontSize: 13, fontWeight: '700', minWidth: 38, textAlign: 'right' },
  feedback: { color: '#94A3B8', fontSize: 12, marginTop: 8, lineHeight: 17 },
});
