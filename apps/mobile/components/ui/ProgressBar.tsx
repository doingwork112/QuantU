import React, { useEffect } from 'react';
import { View, StyleSheet } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withTiming,
  Easing,
} from 'react-native-reanimated';
import { LinearGradient } from 'expo-linear-gradient';

interface Props {
  progress: number; // 0-1
  height?: number;
  colors?: [string, string];
}

export default function ProgressBar({
  progress,
  height = 6,
  colors = ['#6366F1', '#EC4899'],
}: Props) {
  const width = useSharedValue(0);

  useEffect(() => {
    width.value = withTiming(Math.min(1, Math.max(0, progress)), {
      duration: 800,
      easing: Easing.out(Easing.cubic),
    });
  }, [progress]);

  const animStyle = useAnimatedStyle(() => ({
    width: `${width.value * 100}%`,
  }));

  return (
    <View style={[s.track, { height }]}>
      <Animated.View style={[s.fill, animStyle, { height }]}>
        <LinearGradient
          colors={colors}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 0 }}
          style={{ flex: 1, borderRadius: height / 2 }}
        />
      </Animated.View>
    </View>
  );
}

const s = StyleSheet.create({
  track: {
    width: '100%',
    backgroundColor: 'rgba(99,102,241,0.15)',
    borderRadius: 999,
    overflow: 'hidden',
  },
  fill: { borderRadius: 999, overflow: 'hidden' },
});
