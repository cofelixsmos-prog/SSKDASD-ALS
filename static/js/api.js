import { getToken, logout } from './auth.js';

export async function api(path, options = {}) {
  const token = getToken();
  const isFormData = options.body instanceof FormData;

  const headers = {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...(options.headers || {}),
  };

  const res = await fetch(path, { ...options, headers });

  if (res.status === 401) {
    logout();
    return null;
  }

  return res;
}

export async function apiJSON(path, options = {}) {
  const res = await api(path, options);
  if (!res) return null;
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(err.detail || err.error || 'Request failed');
  }
  return res.json();
}
