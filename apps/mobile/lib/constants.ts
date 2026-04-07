// ============================================================
// QuantifyU — 常量
// ============================================================

export const SCORE_DIMENSIONS = {
  face: { label: '面部', max: 40, color: '#6366F1', icon: '👤' },
  body: { label: '身材', max: 25, color: '#EC4899', icon: '💪' },
  height: { label: '身高', max: 15, color: '#14B8A6', icon: '📏' },
  skin_hair: { label: '皮肤/头发', max: 10, color: '#F59E0B', icon: '✨' },
  genital: { label: '私密', max: 10, color: '#8B5CF6', icon: '🔒' },
} as const;

export const SCORE_LABELS: Record<string, { color: string; bg: string }> = {
  '卓越': { color: '#10B981', bg: '#D1FAE5' },
  '优秀': { color: '#3B82F6', bg: '#DBEAFE' },
  '良好': { color: '#6366F1', bg: '#E0E7FF' },
  '中等': { color: '#F59E0B', bg: '#FEF3C7' },
  '待提升': { color: '#EF4444', bg: '#FEE2E2' },
};

export const API_URL = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000';
export const SUPABASE_URL = process.env.EXPO_PUBLIC_SUPABASE_URL || '';
export const SUPABASE_ANON_KEY = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY || '';
