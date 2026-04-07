// ============================================================
// QuantifyU — TypeScript 类型定义
// 与后端 Pydantic schema 1:1 对应
// ============================================================

// ---- Auth ----
export interface SignupPayload {
  email: string;
  password: string;
  display_name: string;
  date_of_birth: string; // ISO date
  gender: 'male' | 'female' | 'non-binary' | 'other';
  consent_terms_of_service: boolean;
  consent_privacy_policy: boolean;
  consent_ai_scoring: boolean;
  consent_genital_data: boolean;
}

export interface AuthResponse {
  user_id: string;
  email: string;
  access_token: string;
  refresh_token: string;
  display_name: string;
  has_profile: boolean;
  has_scores: boolean;
}

// ---- Scoring ----
export interface SelfMeasurements {
  penis_length_cm?: number;
  penis_girth_cm?: number;
  penis_erect_length_cm?: number;
  penis_erect_girth_cm?: number;
  breast_cup?: string;
  breast_band_size?: number;
  breast_shape?: string;
  grooming_level?: number; // 1-5
  self_rating?: number; // 1-10
}

export interface CalculateScorePayload {
  face_photo_url: string;
  body_photo_url?: string;
  body_side_photo_url?: string;
  height_cm: number;
  weight_kg?: number;
  ethnicity?: string;
  self_measurements?: SelfMeasurements;
}

export interface FaceDetail {
  weighted_score: number;
  max: number;
  raw_0_10: number;
  aesthetic: number;
  symmetry: number;
  golden_ratio: number;
  detail: Record<string, any>;
}

export interface BodyDetail {
  weighted_score: number;
  max: number;
  raw_0_10: number;
  proportions: number;
  bmi: number;
  posture: number;
  metrics: {
    shr: number | null;
    whr: number | null;
    leg_body_ratio: number | null;
    bmi: number | null;
  };
  detail: Record<string, any>;
}

export interface ScoreBreakdown {
  face: FaceDetail;
  body: BodyDetail;
  height: { weighted_score: number; max: number; height_cm: number };
  skin_hair: { weighted_score: number; max: number; raw_0_10: number };
  genital: { weighted_score: number; max: number; note: string };
}

export interface ScoreResponse {
  rating_id: string;
  total_score: number;
  percentile: string;
  score_label: string;
  breakdown: ScoreBreakdown;
  face_feedback: string;
  body_feedback: string;
  height_feedback: string;
  skin_hair_feedback: string;
  genital_feedback: string;
  improvement_tips: string[];
  east_asian_notes: string[];
  model_version: string;
  scored_at: string;
}

// ---- Profile ----
export interface Profile {
  user_id: string;
  display_name: string;
  height_cm?: number;
  weight_kg?: number;
  avatar_url?: string;
  photo_urls: string[];
  bio?: string;
  looking_for: string[];
  city?: string;
  country?: string;
  latest_overall_score?: number;
  score_updated_at?: string;
}

// ---- Matching ----
export interface CompatibilityBreakdown {
  score_similarity: number;
  preference_match: number;
  distance_km: number | null;
  age_compatibility: number;
}

export interface MatchItem {
  match_id: string;
  other_user_id: string;
  other_display_name: string;
  other_avatar_url?: string;
  other_age?: number;
  other_overall_score?: number;
  status: 'pending' | 'matched' | 'rejected';
  compatibility_pct: number;
  compatibility_breakdown: CompatibilityBreakdown;
  my_action?: string;
  their_action?: string;
  matched_at?: string;
  created_at: string;
}

// ---- API ----
export interface AIScoreRef {
  overall_score: number | null;
  score_label: string | null;
  last_scored_at: string | null;
}

export interface MatchCompatRef {
  active_matches: number;
  avg_compatibility_pct: number | null;
  top_compatibility_pct: number | null;
}

export interface ApiResponse<T = any> {
  success: boolean;
  message: string;
  data: T;
  ai_score_ref?: AIScoreRef;
  match_compatibility_ref?: MatchCompatRef;
  timestamp: string;
}

// ---- Consent state ----
export interface ConsentState {
  terms: boolean;
  privacy: boolean;
  ai_scoring: boolean;
  genital_data: boolean;
  marketing: boolean;
}

// ---- UI ----
export type ScoreDimension = 'face' | 'body' | 'height' | 'skin_hair' | 'genital';

export interface RadarDataPoint {
  label: string;
  value: number; // 0-1 normalized
  rawScore: number;
  maxScore: number;
  color: string;
}
