import React, { useEffect } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Svg, { Polygon, Circle, Line, Text as SvgText } from 'react-native-svg';
import Animated, {
  useSharedValue,
  useAnimatedProps,
  withTiming,
  Easing,
} from 'react-native-reanimated';
import type { RadarDataPoint } from '../../types';

const AnimatedPolygon = Animated.createAnimatedComponent(Polygon);

interface Props {
  data: RadarDataPoint[];
  size?: number;
}

export default function RadarChart({ data, size = 260 }: Props) {
  const center = size / 2;
  const radius = size / 2 - 40;
  const levels = 5;
  const animProgress = useSharedValue(0);

  useEffect(() => {
    animProgress.value = withTiming(1, {
      duration: 1200,
      easing: Easing.out(Easing.cubic),
    });
  }, [data]);

  const n = data.length;
  const angleStep = (Math.PI * 2) / n;

  // 计算各顶点坐标
  const getPoint = (index: number, value: number) => {
    const angle = angleStep * index - Math.PI / 2;
    const r = radius * value;
    return {
      x: center + r * Math.cos(angle),
      y: center + r * Math.sin(angle),
    };
  };

  // 网格线
  const gridPolygons = Array.from({ length: levels }, (_, level) => {
    const scale = (level + 1) / levels;
    const pts = Array.from({ length: n }, (_, i) => {
      const p = getPoint(i, scale);
      return `${p.x},${p.y}`;
    }).join(' ');
    return pts;
  });

  // 数据多边形
  const dataPoints = data.map((d, i) => getPoint(i, d.value));
  const dataPolygon = dataPoints.map((p) => `${p.x},${p.y}`).join(' ');

  // 轴线 + 标签
  const axes = data.map((d, i) => {
    const end = getPoint(i, 1);
    const labelPos = getPoint(i, 1.22);
    return { end, labelPos, label: d.label, color: d.color, raw: d.rawScore, max: d.maxScore };
  });

  return (
    <View style={[s.container, { width: size, height: size }]}>
      <Svg width={size} height={size}>
        {/* 网格 */}
        {gridPolygons.map((pts, i) => (
          <Polygon
            key={`grid-${i}`}
            points={pts}
            fill="none"
            stroke="rgba(99,102,241,0.12)"
            strokeWidth={1}
          />
        ))}

        {/* 轴线 */}
        {axes.map((a, i) => (
          <Line
            key={`axis-${i}`}
            x1={center}
            y1={center}
            x2={a.end.x}
            y2={a.end.y}
            stroke="rgba(99,102,241,0.15)"
            strokeWidth={1}
          />
        ))}

        {/* 数据区域 */}
        <Polygon
          points={dataPolygon}
          fill="rgba(99,102,241,0.20)"
          stroke="#6366F1"
          strokeWidth={2.5}
        />

        {/* 数据点 */}
        {dataPoints.map((p, i) => (
          <Circle
            key={`dot-${i}`}
            cx={p.x}
            cy={p.y}
            r={5}
            fill={data[i].color}
            stroke="#fff"
            strokeWidth={2}
          />
        ))}

        {/* 标签 */}
        {axes.map((a, i) => (
          <SvgText
            key={`lbl-${i}`}
            x={a.labelPos.x}
            y={a.labelPos.y}
            textAnchor="middle"
            alignmentBaseline="central"
            fill="#94A3B8"
            fontSize={11}
            fontWeight="600"
          >
            {a.label}
          </SvgText>
        ))}
      </Svg>

      {/* 中心分数 */}
      <View style={s.centerScore}>
        <Text style={s.totalLabel}>总分</Text>
        <Text style={s.totalValue}>
          {data.reduce((sum, d) => sum + d.rawScore, 0).toFixed(1)}
        </Text>
        <Text style={s.totalMax}>/100</Text>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  container: { alignSelf: 'center', position: 'relative' },
  centerScore: {
    position: 'absolute',
    top: '50%',
    left: '50%',
    transform: [{ translateX: -30 }, { translateY: -28 }],
    alignItems: 'center',
    width: 60,
  },
  totalLabel: { color: '#94A3B8', fontSize: 11, fontWeight: '500' },
  totalValue: { color: '#E0E7FF', fontSize: 28, fontWeight: '800', marginTop: -2 },
  totalMax: { color: '#64748B', fontSize: 12, marginTop: -4 },
});
