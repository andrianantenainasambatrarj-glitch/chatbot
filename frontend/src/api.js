// Client API : gestion du jeton JWT et des appels REST.
// En développement, les chemins relatifs passent par le proxy CRA.

const TOKEN_KEY = 'cv_token';

export const API_BASE = process.env.REACT_APP_API_URL || '';

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export function wsUrl(path) {
  const base = API_BASE || window.location.origin;
  return base.replace(/^http/, 'ws') + path;
}

export async function apiFetch(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (response.status === 204) return null;

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.error || `HTTP ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return data;
}

export const authApi = {
  register: (email, password) =>
    apiFetch('/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    }),
  login: (email, password) =>
    apiFetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    }),
  me: () => apiFetch('/api/auth/me'),
};
