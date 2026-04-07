import React from 'react';
import {
  TouchableOpacity,
  Text,
  ActivityIndicator,
  StyleSheet,
  ViewStyle,
} from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';

interface Props {
  title: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost';
  loading?: boolean;
  disabled?: boolean;
  style?: ViewStyle;
  size?: 'sm' | 'md' | 'lg';
}

export default function Button({
  title,
  onPress,
  variant = 'primary',
  loading = false,
  disabled = false,
  style,
  size = 'md',
}: Props) {
  const isDisabled = disabled || loading;
  const h = size === 'sm' ? 40 : size === 'lg' ? 60 : 50;

  if (variant === 'primary') {
    return (
      <TouchableOpacity
        onPress={onPress}
        disabled={isDisabled}
        activeOpacity={0.85}
        style={[{ borderRadius: 16, overflow: 'hidden', opacity: isDisabled ? 0.5 : 1 }, style]}
      >
        <LinearGradient
          colors={['#6366F1', '#8B5CF6']}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={[s.base, { height: h }]}
        >
          {loading ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={s.primaryText}>{title}</Text>
          )}
        </LinearGradient>
      </TouchableOpacity>
    );
  }

  const variantStyle =
    variant === 'outline'
      ? s.outline
      : variant === 'ghost'
        ? s.ghost
        : s.secondary;
  const textStyle =
    variant === 'outline'
      ? s.outlineText
      : variant === 'ghost'
        ? s.ghostText
        : s.secondaryText;

  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={isDisabled}
      activeOpacity={0.7}
      style={[s.base, variantStyle, { height: h, opacity: isDisabled ? 0.5 : 1 }, style]}
    >
      {loading ? (
        <ActivityIndicator color={variant === 'secondary' ? '#fff' : '#6366F1'} />
      ) : (
        <Text style={textStyle}>{title}</Text>
      )}
    </TouchableOpacity>
  );
}

const s = StyleSheet.create({
  base: {
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 16,
    paddingHorizontal: 24,
  },
  primaryText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  secondary: { backgroundColor: '#1E1B4B' },
  secondaryText: { color: '#C7D2FE', fontSize: 16, fontWeight: '600' },
  outline: { backgroundColor: 'transparent', borderWidth: 1.5, borderColor: '#6366F1' },
  outlineText: { color: '#6366F1', fontSize: 16, fontWeight: '600' },
  ghost: { backgroundColor: 'transparent' },
  ghostText: { color: '#6366F1', fontSize: 16, fontWeight: '600' },
});
