// Client API : gestion du jeton JWT et des appels REST / WebSocket.
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

/* ------------------------------------------------------------------ */
/* Transcriptions                                                      */
/* ------------------------------------------------------------------ */

// Toujours en mode asynchrone : l'API renvoie un objet job (202).
export function transcribeFileApi(file, fileName, { engine, language, diarize = false }) {
  const form = new FormData();
  form.append('audio', file, fileName);
  form.append('engine', engine);
  form.append('language', language);
  if (diarize) form.append('diarize', '1');
  form.append('async', '1');
  return apiFetch('/api/transcribe', { method: 'POST', body: form });
}

export const getJob = (jobId) => apiFetch(`/api/jobs/${jobId}`);

export const historyApi = () => apiFetch('/api/transcriptions');

export const transcriptionApi = (id) => apiFetch(`/api/transcriptions/${id}`);

export const updateTranscriptionApi = (id, text) =>
  apiFetch(`/api/transcriptions/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });

export const deleteTranscriptionApi = (id) =>
  apiFetch(`/api/transcriptions/${id}`, { method: 'DELETE' });

export const clearHistoryApi = () =>
  apiFetch('/api/transcriptions', { method: 'DELETE' });

/* ------------------------------------------------------------------ */
/* Exports (DOCX / PDF / TXT / SRT)                                    */
/* ------------------------------------------------------------------ */

async function downloadAuthed(path) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { Authorization: `Bearer ${getToken() || ''}` },
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  const blob = await response.blob();
  const disposition = response.headers.get('Content-Disposition') || '';
  const match = /filename="?([^"]+)"?/.exec(disposition);
  const fileName = match ? match[1] : path.split('/').pop();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

const exportPath = (id, fmt) => `/api/transcriptions/${id}/export/${fmt}`;
export const exportWord = (id) => downloadAuthed(exportPath(id, 'docx'));
export const exportPdf = (id) => downloadAuthed(exportPath(id, 'pdf'));
export const exportTxt = (id) => downloadAuthed(exportPath(id, 'txt'));
export const exportSrt = (id) => downloadAuthed(exportPath(id, 'srt'));

export const sharedExportUrl = (token, fmt) =>
  `${API_BASE}/api/shared/${token}/export/${fmt}`;

/* ------------------------------------------------------------------ */
/* Analyse, chat, partage, intégrations                                */
/* ------------------------------------------------------------------ */

export const insightsApi = (id) =>
  apiFetch(`/api/transcriptions/${id}/insights`, { method: 'POST' });

export const chatApi = (id, message, history = []) =>
  apiFetch(`/api/transcriptions/${id}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history }),
  }).then((data) => data.reply);

export const shareApi = (id) =>
  apiFetch(`/api/transcriptions/${id}/share`, { method: 'POST' });

export const emailApi = (id, email) =>
  apiFetch(`/api/transcriptions/${id}/email`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });

export const webhookApi = (id, url) =>
  apiFetch(`/api/transcriptions/${id}/webhook`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });

export const sharedApi = (token) => apiFetch(`/api/shared/${token}`);

/* ------------------------------------------------------------------ */
/* Statistiques et administration                                      */
/* ------------------------------------------------------------------ */

export const statsApi = () => apiFetch('/api/stats');

export const adminStatsApi = () => apiFetch('/api/admin/stats');

export const adminUsersApi = () => apiFetch('/api/admin/users');

export const adminUpdateUserApi = (id, patch) =>
  apiFetch(`/api/admin/users/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
