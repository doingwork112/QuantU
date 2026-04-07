// ============================================================
// QuantifyU — API 客户端
// ============================================================

import axios from 'axios';
import * as SecureStore from 'expo-secure-store';
import { API_URL } from './constants';
import type {
  ApiResponse,
  AuthResponse,
  CalculateScorePayload,
  MatchItem,
  ScoreResponse,
  SignupPayload,
} from '../types';

const api = axios.create({ baseURL: API_URL });

// 自动附加 JWT
api.interceptors.request.use(async (config) => {
  const token = await SecureStore.getItemAsync('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// ---- Auth ----
export async function signup(payload: SignupPayload) {
  const { data } = await api.post<ApiResponse<AuthResponse>>('/auth/signup', payload);
  if (data.data.access_token) {
    await SecureStore.setItemAsync('access_token', data.data.access_token);
    await SecureStore.setItemAsync('refresh_token', data.data.refresh_token);
  }
  return data;
}

export async function login(email: string, password: string) {
  const { data } = await api.post<ApiResponse<AuthResponse>>('/auth/login', { email, password });
  if (data.data.access_token) {
    await SecureStore.setItemAsync('access_token', data.data.access_token);
    await SecureStore.setItemAsync('refresh_token', data.data.refresh_token);
  }
  return data;
}

// ---- Rating ----
export async function calculateScore(payload: CalculateScorePayload) {
  const { data } = await api.post<ApiResponse<ScoreResponse>>('/rating/calculate', payload);
  return data;
}

// ---- Profile ----
export async function updateProfile(payload: Record<string, any>) {
  const { data } = await api.post<ApiResponse>('/profile/update', payload);
  return data;
}

export async function getProfile() {
  const { data } = await api.get<ApiResponse>('/profile/me');
  return data;
}

// ---- Matches ----
export async function getMatches(status = 'matched', page = 1) {
  const { data } = await api.get<ApiResponse<{ matches: MatchItem[]; total: number }>>(
    `/matches?status_filter=${status}&page=${page}`
  );
  return data;
}

// ---- Vault ----
export async function saveVault(payload: Record<string, any>) {
  const { data } = await api.post<ApiResponse>('/private-vault/save', payload);
  return data;
}

// ---- Privacy ----
export async function updateConsent(payload: {
  consent_ai_scoring?: boolean;
  consent_genital_data?: boolean;
  consent_data_sharing?: boolean;
  consent_marketing?: boolean;
}) {
  const { data } = await api.post<ApiResponse>('/privacy/consent/update', payload);
  return data;
}

export async function getConsentStatus() {
  const { data } = await api.get<ApiResponse>('/privacy/consent/status');
  return data;
}

export async function deleteVaultData() {
  const { data } = await api.delete<ApiResponse>('/privacy/vault');
  return data;
}

export async function uploadPhotoHash(
  photoUri: string,
  photoType: 'face' | 'body' | 'body_side' | 'avatar',
  clientEncrypted: boolean = false,
) {
  const formData = new FormData();
  formData.append('photo', {
    uri: photoUri,
    type: 'image/jpeg',
    name: `${photoType}.jpg`,
  } as any);
  formData.append('photo_type', photoType);
  formData.append('client_encrypted', String(clientEncrypted));

  const { data } = await api.post<ApiResponse>(
    '/privacy/photo/upload',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return data;
}

export async function exportUserData() {
  const { data } = await api.get<ApiResponse>('/privacy/data-export');
  return data;
}

export async function deleteAccount() {
  const { data } = await api.delete<ApiResponse>('/privacy/account');
  return data;
}

export default api;
