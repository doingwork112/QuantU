// ============================================================
// QuantifyU — Zustand 全局状态
// ============================================================

import { create } from 'zustand';
import type { AuthResponse, ScoreResponse, Profile, ConsentState } from '../types';

interface AppState {
  // Auth
  user: AuthResponse | null;
  setUser: (u: AuthResponse | null) => void;

  // Score
  latestScore: ScoreResponse | null;
  setLatestScore: (s: ScoreResponse | null) => void;

  // Profile
  profile: Profile | null;
  setProfile: (p: Profile | null) => void;

  // Consent
  consent: ConsentState;
  setConsent: (c: Partial<ConsentState>) => void;

  // UI
  isLoading: boolean;
  setLoading: (v: boolean) => void;
}

export const useStore = create<AppState>((set) => ({
  user: null,
  setUser: (user) => set({ user }),

  latestScore: null,
  setLatestScore: (latestScore) => set({ latestScore }),

  profile: null,
  setProfile: (profile) => set({ profile }),

  consent: {
    terms: false,
    privacy: false,
    ai_scoring: false,
    genital_data: false,
    marketing: false,
  },
  setConsent: (partial) => set((s) => ({ consent: { ...s.consent, ...partial } })),

  isLoading: false,
  setLoading: (isLoading) => set({ isLoading }),
}));
