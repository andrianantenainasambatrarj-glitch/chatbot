import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import {
  authApi, getToken, clearToken,
  transcribeFileApi, getJob, historyApi, deleteTranscriptionApi,
  updateTranscriptionApi, exportWord, exportPdf, exportTxt, exportSrt,
  sharedApi, sharedExportUrl, clearHistoryApi,
} from './api';
import { createStreamAnalyser } from './audioStream';
import AuthScreen from './AuthScreen';
import LiveMode from './LiveMode';
import CommandMic from './CommandMic';
import DashboardView from './DashboardView';
import TranscriptionActions from './TranscriptionActions';
import Icon from './components/Icon';
import Waveform from './components/Waveform';
import './i18n';

const MIC_TYPES = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/ogg;codecs=opus'];

function preferredMime() {
  if (typeof MediaRecorder === 'undefined') return '';
  return MIC_TYPES.find((type) => MediaRecorder.isTypeSupported?.(type)) || '';
}

function mimeExtension(mime) {
  if (mime.includes('mp4')) return 'mp4';
  if (mime.includes('ogg')) return 'ogg';
  if (mime.includes('webm')) return 'webm';
  return 'webm';
}

function formatTime(seconds) {
  const m = Math.floor(seconds / 60).toString().padStart(2, '0');
  const s = Math.floor(seconds % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

function ExportChips({ item, t }) {
  return (
    <div className="export-row" style={{ marginTop: 14 }}>
      <button className="export-chip" onClick={() => exportWord(item.id)}>
        <Icon name="fileText" size={16} /> {t('exportWord')}
      </button>
      <button className="export-chip" onClick={() => exportPdf(item.id)}>
        <Icon name="fileText" size={16} /> {t('exportPdf')}
      </button>
      <button className="export-chip" onClick={() => exportTxt(item.id)}>
        <Icon name="fileText" size={16} /> {t('exportTxt')}
      </button>
      {item.has_timestamps && (
        <button className="export-chip" onClick={() => exportSrt(item.id)}>
          <Icon name="fileText" size={16} /> {t('exportSrt')}
        </button>
      )}
    </div>
  );
}

function SpeakerTurns({ item, t }) {
  return (
    <div className="speakers">
      {item.speakers.map((sp, i) => (
        <p key={i} className={`speaker-turn speaker-${((sp.speaker - 1) % 2) + 1}`}>
          <strong>{t('speaker', { n: sp.speaker })}</strong>
          {sp.text}
        </p>
      ))}
    </div>
  );
}

function ResultCard({
  item, insights, setInsights, chats, setChats,
  openPanel, setOpenPanel, notify, onError, onRemove, t,
}) {
  const [edited, setEdited] = useState(item.text || '');
  const [saving, setSaving] = useState(false);

  useEffect(() => setEdited(item.text || ''), [item.text]);

  const saveEdits = async () => {
    setSaving(true);
    try {
      const updated = await updateTranscriptionApi(item.id, edited);
      setEdited(updated.text || edited);
      notify(t('editsSaved'));
    } catch (err) {
      onError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <div className="transcription-head">
        <div>
          <h3>{t('transcriptionTitle')}</h3>
          <div className="transcription-meta">
            <span className="meta-chip engine">{t(item.engine === 'whisper' ? 'whisper' : 'vosk')}</span>
            {item.duration_seconds
              ? <span className="meta-chip">{t('duration', { time: Math.round(item.duration_seconds) })}</span>
              : null}
            {item.diarized && <span className="meta-chip">{t('diarizedChip')}</span>}
            {item.created_at && (
              <span className="meta-chip">{new Date(item.created_at).toLocaleString()}</span>
            )}
          </div>
        </div>
        {onRemove && (
          <button
            className="icon-btn danger"
            title={t('history.deleteOne')}
            aria-label={t('history.deleteOne')}
            onClick={() => onRemove(item.id)}
          >
            <Icon name="trash" size={17} />
          </button>
        )}
      </div>

      {item.speakers?.length ? (
        <SpeakerTurns item={item} t={t} />
      ) : (
        <textarea
          className="editor"
          rows={10}
          value={edited}
          onChange={(e) => setEdited(e.target.value)}
        />
      )}

      {edited !== item.text && !item.speakers?.length && (
        <button className="btn btn-secondary btn-sm" onClick={saveEdits} disabled={saving}>
          {saving ? <span className="loader sm" /> : <Icon name="check" size={15} />}
          {t('saveEdits')}
        </button>
      )}

      <ExportChips item={item} t={t} />

      <div className="actions-bar" style={{ borderTop: 'none', paddingTop: 4 }}>
        <TranscriptionActions
          item={item}
          insights={insights}
          setInsights={(data) => setInsights(data)}
          chatMessages={chats}
          setChatMessages={setChats}
          openPanel={openPanel}
          setOpenPanel={setOpenPanel}
          notify={notify}
          onError={onError}
        />
      </div>
    </div>
  );
}

function HistoryList({ items, expandedId, setExpandedId, cardProps, t, onRemove }) {
  if (!items?.length) {
    return (
      <div className="empty-state">
        <Icon name="fileText" size={34} />
        <p>{t('history.empty')}</p>
      </div>
    );
  }
  return (
    <div className="history-grid">
      {items.map((item) => (
        <article className="history-card" key={item.id}>
          {expandedId === item.id ? (
            <ResultCard item={item} {...cardProps(item)} onRemove={onRemove} t={t} />
          ) : (
            <>
              <div className="history-card-head">
                <span className="history-date">{new Date(item.created_at).toLocaleString()}</span>
                <button
                  className="icon-btn danger"
                  style={{ width: 28, height: 28 }}
                  aria-label={t('history.deleteOne')}
                  onClick={() => onRemove(item.id)}
                >
                  <Icon name="trash" size={15} />
                </button>
              </div>
              <span className="meta-chip engine" style={{ alignSelf: 'flex-start' }}>
                {t(item.engine === 'whisper' ? 'whisper' : 'vosk')}
              </span>
              <p className="history-text">{item.text}</p>
              <div className="history-meta">
                {item.duration_seconds
                  ? <span className="meta-chip">{t('duration', { time: Math.round(item.duration_seconds) })}</span>
                  : null}
              </div>
              <div className="history-exports">
                <button onClick={() => exportWord(item.id)}>W</button>
                <button onClick={() => exportPdf(item.id)}>PDF</button>
                <button onClick={() => exportTxt(item.id)}>TXT</button>
                {item.has_timestamps && <button onClick={() => exportSrt(item.id)}>SRT</button>}
                <button
                  style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 3 }}
                  onClick={() => setExpandedId(item.id)}
                >
                  {t('history.more')} <Icon name="chevronDown" size={13} />
                </button>
              </div>
            </>
          )}
        </article>
      ))}
    </div>
  );
}

export default function App() {
  const { t, i18n } = useTranslation();

  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const [view, setView] = useState(() =>
    window.location.pathname.startsWith('/shared/') ? 'shared' : 'studio'
  );
  const [sharedToken] = useState(() =>
    window.location.pathname.startsWith('/shared/')
      ? window.location.pathname.split('/shared/')[1]?.split('/')[0]
      : null
  );
  const [shared, setShared] = useState(null);

  const [engine, setEngine] = useState(() => localStorage.getItem('cv_engine') || 'vosk');
  const [language, setLanguage] = useState(() => localStorage.getItem('cv_lang') || 'fr');
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem('cv_theme') === 'dark');
  const [diarize, setDiarize] = useState(false);

  const [recorderState, setRecorderState] = useState('idle');
  const [elapsed, setElapsed] = useState(0);
  const [recordAnalyser, setRecordAnalyser] = useState(null);
  const [draft, setDraft] = useState(null); // { blobUrl, blob, fileName }

  const [uploadKey, setUploadKey] = useState(0);
  const [job, setJob] = useState(null);
  const [lastResult, setLastResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [expandedId, setExpandedId] = useState(null);

  const [insightsById, setInsightsById] = useState({});
  const [chatsById, setChatsById] = useState({});
  const [openPanel, setOpenPanel] = useState(null);

  const [error, setError] = useState('');
  const [toast, setToast] = useState('');

  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const analyserHandleRef = useRef(null);
  const startStampRef = useRef(0);
  const elapsedBeforeRef = useRef(0);

  const notify = useCallback((message) => {
    setToast(message);
    setTimeout(() => setToast(''), 3000);
  }, []);

  /* ---------- session ---------- */
  useEffect(() => {
    if (view === 'shared') {
      setLoading(false);
      sharedApi(sharedToken)
        .then(setShared)
        .catch(() => setShared({ error: 'notFound' }));
      return undefined;
    }
    if (!getToken()) {
      setLoading(false);
      return undefined;
    }
    let cancelled = false;
    authApi.me()
      // /me renvoie l'utilisateur à plat ; login/register renvoient { token, user }
      .then((data) => { if (!cancelled) setUser(data.user ?? data); })
      .catch((err) => {
        // Un jeton invalide/expiré déconnecte ; un souci réseau passager ne touche pas la session
        if (!cancelled && err.status === 401) clearToken();
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // Vérification de session une seule fois au montage, PAS à chaque changement d'onglet
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    document.body.classList.toggle('dark-mode', darkMode);
    localStorage.setItem('cv_theme', darkMode ? 'dark' : 'light');
  }, [darkMode]);

  useEffect(() => {
    i18n.changeLanguage(language);
    localStorage.setItem('cv_lang', language);
  }, [language, i18n]);

  useEffect(() => {
    localStorage.setItem('cv_engine', engine);
  }, [engine]);

  const loadHistory = useCallback(async () => {
    try {
      setHistory(await historyApi());
    } catch { /* vue dédiée affiche l'état vide */ }
  }, []);

  useEffect(() => {
    if (user) loadHistory();
  }, [user, loadHistory]);

  /* ---------- minuteur ---------- */
  useEffect(() => {
    if (recorderState !== 'recording') return undefined;
    const id = setInterval(() => {
      setElapsed(elapsedBeforeRef.current + (Date.now() - startStampRef.current) / 1000);
    }, 250);
    return () => clearInterval(id);
  }, [recorderState]);

  /* ---------- polling tâche ---------- */
  useEffect(() => {
    if (!job || job.status === 'done' || job.status === 'error') return undefined;
    let cancelled = false;
    const poll = async () => {
      try {
        const fresh = await getJob(job.id);
        if (cancelled) return;
        setJob(fresh);
        if (fresh.status === 'done' && fresh.transcription) {
          setLastResult(fresh.transcription);
          setInsightsById((prev) => ({ ...prev, [fresh.transcription.id]: null }));
          setChatsById((prev) => ({ ...prev, [fresh.transcription.id]: [] }));
          setOpenPanel(null);
          notify(t('done'));
          loadHistory();
        }
      } catch (err) {
        if (!cancelled) setJob((prev) => ({ ...prev, status: 'error', error: err.message }));
      }
    };
    const id = setInterval(poll, 900);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [job, t, notify, loadHistory]);

  useEffect(() => {
    const onEsc = (e) => { if (e.key === 'Escape') setError(''); };
    window.addEventListener('keydown', onEsc);
    return () => window.removeEventListener('keydown', onEsc);
  }, []);

  /* ---------- enregistrement ---------- */
  const teardownMic = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    analyserHandleRef.current?.stop();
    analyserHandleRef.current = null;
    setRecordAnalyser(null);
  };

  const startRecording = async () => {
    setError('');
    setLastResult(null);
    setJob(null);
    setDraft(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setError(t('micUnsupported'));
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
      streamRef.current = stream;
      const analyserHandle = createStreamAnalyser(stream);
      analyserHandleRef.current = analyserHandle;
      setRecordAnalyser(analyserHandle?.analyser || null);

      const chunks = [];
      const mime = preferredMime();
      const recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
      recorder.onstop = () => {
        const type = recorder.mimeType || mime || 'audio/webm';
        const blob = new Blob(chunks, { type });
        const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
        const fileName = `enregistrement-${stamp}.${mimeExtension(type)}`;
        setDraft({ blob, blobUrl: URL.createObjectURL(blob), fileName });
        teardownMic();
        setRecorderState('idle');
      };
      recorder.start(300);
      recorderRef.current = recorder;
      elapsedBeforeRef.current = 0;
      startStampRef.current = Date.now();
      setElapsed(0);
      setRecorderState('recording');
    } catch (err) {
      teardownMic();
      if (err.name === 'NotAllowedError') setError(t('micDenied'));
      else if (err.name === 'NotFoundError') setError(t('micNotFound'));
      else setError(err.message);
    }
  };

  const pauseRecording = () => {
    recorderRef.current?.pause();
    elapsedBeforeRef.current += (Date.now() - startStampRef.current) / 1000;
    setRecorderState('paused');
  };

  const resumeRecording = () => {
    recorderRef.current?.resume();
    startStampRef.current = Date.now();
    setRecorderState('recording');
  };

  const stopRecording = () => {
    if (recorderRef.current?.state !== 'inactive') recorderRef.current?.stop();
  };

  const discardDraft = () => {
    if (draft?.blobUrl) URL.revokeObjectURL(draft.blobUrl);
    setDraft(null);
    setUploadKey((k) => k + 1);
  };

  const onFileSelected = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setError('');
    setLastResult(null);
    setJob(null);
    setDraft({ blob: file, blobUrl: URL.createObjectURL(file), fileName: file.name });
  };

  const transcribeDraft = async () => {
    if (!draft) return;
    try {
      const data = await transcribeFileApi(draft.blob, draft.fileName, {
        engine,
        language,
        diarize,
      });
      setJob({ id: data.id, status: data.status || 'pending', progress: 0 });
      if (draft.blobUrl) URL.revokeObjectURL(draft.blobUrl);
      setDraft(null);
      setUploadKey((k) => k + 1);
    } catch (err) {
      setError(err.message);
    }
  };

  /* ---------- historique ---------- */
  const removeItem = async (id) => {
    try {
      await deleteTranscriptionApi(id);
      setHistory((items) => items.filter((it) => it.id !== id));
      if (lastResult?.id === id) setLastResult(null);
      notify(t('history.deleted'));
    } catch (err) {
      setError(err.message);
    }
  };

  const clearHistory = async () => {
    if (!window.confirm(t('confirmClear'))) return;
    try {
      await clearHistoryApi();
      setHistory([]);
      setLastResult(null);
      setExpandedId(null);
      notify(t('historyCleared'));
    } catch (err) {
      setError(err.message);
    }
  };

  /* ---------- commandes vocales ---------- */
  const readAloud = (text) => {
    if (!('speechSynthesis' in window) || !text) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = language === 'fr' ? 'fr-FR' : 'en-US';
    window.speechSynthesis.speak(utterance);
  };

  const handleVoiceCommand = (command) => {
    if (!command) return;
    switch (command) {
      case 'new_recording':
      case 'standard_mode':
        setView('studio');
        discardDraft();
        break;
      case 'live_mode':
        setView('direct');
        break;
      case 'dashboard':
        setView('dashboard');
        break;
      case 'history':
        setView('history');
        break;
      case 'dark_mode':
        setDarkMode(true);
        break;
      case 'light_mode':
        setDarkMode(false);
        break;
      case 'logout':
        handleLogout();
        break;
      case 'clear_history':
        clearHistory();
        break;
      case 'download_word':
        if (lastResult) exportWord(lastResult.id);
        break;
      case 'download_pdf':
        if (lastResult) exportPdf(lastResult.id);
        break;
      case 'insights':
        setView('studio');
        if (lastResult) setOpenPanel('insights');
        break;
      case 'listen':
        readAloud(lastResult?.text);
        break;
      case 'language_english':
        setLanguage('en');
        break;
      case 'language_french':
        setLanguage('fr');
        break;
      default:
        break;
    }
  };

  const handleAuthed = (dataUser) => {
    setUser(dataUser);
    loadHistory();
  };

  const handleLogout = () => {
    clearToken();
    setUser(null);
    setHistory([]);
    setLastResult(null);
  };

  /* ---------- page publique de partage ---------- */
  if (view === 'shared') {
    return (
      <div className={`app ${darkMode ? 'dark-mode' : ''}`}>
        <main className="page" style={{ maxWidth: 760 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 22 }}>
            <span className="brand" style={{ padding: 0 }}>
              <span className="brand-mark"><Icon name="waveform" size={20} /></span>
              <span className="brand-name">Chatbot Vocal</span>
            </span>
          </div>
          {!shared ? (
            <div className="loader" />
          ) : shared.error ? (
            <div className="empty-state">
              <Icon name="link" size={34} />
              <p>{t('shared.notFound')}</p>
            </div>
          ) : (
            <div className="card fade-in">
              <h2 style={{ marginBottom: 10 }}>{t('transcriptionTitle')}</h2>
              <div className="transcription-meta" style={{ marginBottom: 14 }}>
                {shared.duration_seconds
                  ? <span className="meta-chip">{t('duration', { time: Math.round(shared.duration_seconds) })}</span>
                  : null}
                <span className="meta-chip engine">{t(shared.engine === 'whisper' ? 'whisper' : 'vosk')}</span>
                {shared.created_at && (
                  <span className="meta-chip">{new Date(shared.created_at).toLocaleString()}</span>
                )}
              </div>
              {shared.speakers?.length ? (
                <SpeakerTurns item={shared} t={t} />
              ) : (
                <p style={{ whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>{shared.text}</p>
              )}
              <div className="export-row" style={{ marginTop: 16 }}>
                <a className="export-chip" href={sharedExportUrl(sharedToken, 'docx')}>
                  <Icon name="fileText" size={16} /> {t('exportWord')}
                </a>
                <a className="export-chip" href={sharedExportUrl(sharedToken, 'pdf')}>
                  <Icon name="fileText" size={16} /> {t('exportPdf')}
                </a>
              </div>
            </div>
          )}
        </main>
      </div>
    );
  }

  if (loading) {
    return (
      <div className={`app ${darkMode ? 'dark-mode' : ''}`}>
        <div className="centered-loader"><span className="loader" /></div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className={`app ${darkMode ? 'dark-mode' : ''}`}>
        <div className="auth-top-controls">
          <select
            className="language-select"
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            aria-label={t('language')}
          >
            <option value="fr">FR</option>
            <option value="en">EN</option>
          </select>
          <button
            className="theme-toggle"
            onClick={() => setDarkMode(!darkMode)}
            aria-label="Thème"
          >
            <Icon name={darkMode ? 'sun' : 'moon'} size={17} />
          </button>
        </div>
        <AuthScreen onAuthed={handleAuthed} />
      </div>
    );
  }

  const navItems = [
    { id: 'studio', icon: 'mic', label: t('nav.studio') },
    { id: 'direct', icon: 'live', label: t('nav.direct') },
    { id: 'commands', icon: 'command', label: t('nav.commands') },
    { id: 'history', icon: 'folder', label: t('nav.history') },
    { id: 'dashboard', icon: 'dashboard', label: t('nav.dashboard') },
  ];

  const cardProps = {
    notify,
    onError: setError,
    insights: lastResult ? insightsById[lastResult.id] : null,
    setInsights: (data) =>
      setInsightsById((prev) => ({ ...prev, [lastResult.id]: data })),
    chats: lastResult ? chatsById[lastResult.id] || [] : [],
    setChats: (updater) =>
      setChatsById((prev) => {
        const current = prev[lastResult.id] || [];
        return { ...prev, [lastResult.id]: typeof updater === 'function' ? updater(current) : updater };
      }),
    openPanel,
    setOpenPanel,
  };

  const historyCardProps = (item) => ({
    notify,
    onError: setError,
    insights: insightsById[item.id] || null,
    setInsights: (data) => setInsightsById((prev) => ({ ...prev, [item.id]: data })),
    chats: chatsById[item.id] || [],
    setChats: (next) =>
      setChatsById((prev) => ({
        ...prev,
        [item.id]: typeof next === 'function' ? next(prev[item.id] || []) : next,
      })),
    openPanel: expandedId === item.id ? openPanel : null,
    setOpenPanel,
  });

  const initials = (user.email || '?').slice(0, 2);

  return (
    <div className={`app ${darkMode ? 'dark-mode' : ''}`}>
      <div className="shell">
        <aside className="sidebar">
          <span className="brand">
            <span className="brand-mark"><Icon name="waveform" size={21} /></span>
            <span>
              <span className="brand-name">Chatbot Vocal</span>
              <span className="brand-tag">{t('brandTag')}</span>
            </span>
          </span>

          <nav className="nav" aria-label="Navigation principale">
            {navItems.map((item) => (
              <button
                key={item.id}
                className={`nav-item ${view === item.id ? 'active' : ''}`}
                onClick={() => setView(item.id)}
              >
                <Icon name={item.icon} size={19} />
                {item.label}
              </button>
            ))}
          </nav>

          <div className="sidebar-spacer" />

          <div className="sidebar-user">
            <div className="user-line">
              <span className="avatar">{initials}</span>
              <div className="user-meta">
                <span className="user-email">{user.email}</span>
                {user.role === 'admin' && <span className="user-role">{t('adminBadge')}</span>}
              </div>
            </div>
            <button className="btn btn-ghost btn-sm" onClick={handleLogout}>
              <Icon name="logout" size={15} /> {t('auth.logout')}
            </button>
          </div>
        </aside>

        <div className="content">
          <header className="topbar">
            <span className="mobile-brand">
              <span className="brand-mark"><Icon name="waveform" size={18} /></span>
              <span className="brand-name">Chatbot Vocal</span>
            </span>
            <div className="view-title">
              <h1>{navItems.find((n) => n.id === view)?.label}</h1>
            </div>
            <div className="topbar-actions">
              <select
                className="language-select"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                aria-label={t('language')}
              >
                <option value="fr">FR</option>
                <option value="en">EN</option>
              </select>
              <button
                className="theme-toggle"
                onClick={() => setDarkMode(!darkMode)}
                aria-label="Thème"
                title={darkMode ? t('theme.light') : t('theme.dark')}
              >
                <Icon name={darkMode ? 'sun' : 'moon'} size={17} />
              </button>
              <button className="icon-btn" onClick={handleLogout} title={t('auth.logout')}>
                <Icon name="logout" size={17} />
              </button>
            </div>
          </header>

          <main className="page">
            {error && (
              <div className="alert" role="alert" style={{ marginBottom: 16 }}>
                <Icon name="x" size={16} />
                <span style={{ flex: 1 }}>{error}</span>
                <button className="icon-btn" onClick={() => setError('')} aria-label="Fermer">
                  <Icon name="x" size={15} />
                </button>
              </div>
            )}
            {toast && (
              <div className="toast"><Icon name="check" size={15} /> {toast}</div>
            )}

            {view === 'studio' && (
              <div className="studio fade-in">
                <div className="page-head" style={{ marginBottom: 4 }}>
                  <h2>{t('studio.title')}</h2>
                  <p>{t('studio.subtitle')}</p>
                </div>

                <div className="toolbar">
                  <label className="field">
                    <span>{t('engine')}</span>
                    <select value={engine} onChange={(e) => setEngine(e.target.value)}>
                      <option value="vosk">{t('vosk')}</option>
                      <option value="whisper">{t('whisper')}</option>
                    </select>
                  </label>
                  <label className="field checkbox-field">
                    <input type="checkbox" checked={diarize} onChange={(e) => setDiarize(e.target.checked)} />
                    {t('diarize')}
                  </label>
                </div>

                <div className="card">
                  <div className="waveform-frame" style={{ marginBottom: 16 }}>
                    <Waveform analyser={recordAnalyser} active={recorderState === 'recording'} height={78} />
                  </div>

                  {draft ? (
                    <div>
                      <div className="record-stage">
                        <span className="timer-chip">
                          <Icon name="fileText" size={16} />
                          {draft.fileName}
                        </span>
                        <audio className="audio-player" controls src={draft.blobUrl} />
                        <div className="review-actions">
                          <button className="btn btn-secondary" onClick={discardDraft}>
                            <Icon name="trash" size={16} /> {t('discard')}
                          </button>
                          <button className="btn btn-primary" onClick={transcribeDraft}>
                            <Icon name="sparkles" size={16} /> {t('transcribe')}
                          </button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="record-stage">
                        {recorderState !== 'idle' && (
                          <span className="timer-chip">
                            <span className={`live-dot ${recorderState === 'paused' ? 'paused' : ''}`} />
                            {formatTime(elapsed)}
                          </span>
                        )}

                        <div className="record-controls">
                          {(recorderState === 'recording' || recorderState === 'paused') && (
                            <button
                              className="btn btn-secondary"
                              onClick={recorderState === 'paused' ? resumeRecording : pauseRecording}
                            >
                              <Icon name={recorderState === 'paused' ? 'play' : 'pause'} size={17} />
                              {recorderState === 'paused' ? t('resume') : t('pause')}
                            </button>
                          )}

                          {recorderState === 'idle' ? (
                            <button className="record-circle" onClick={startRecording} aria-label={t('record')}>
                              <Icon name="mic" size={31} />
                            </button>
                          ) : (
                            <button
                              className={`record-circle ${recorderState === 'recording' ? 'recording' : ''}`}
                              onClick={stopRecording}
                              aria-label={t('stop')}
                            >
                              <Icon name="stop" size={27} />
                            </button>
                          )}
                        </div>

                        <span className="record-caption">
                          {recorderState === 'recording' && t('recordingState')}
                          {recorderState === 'paused' && t('pausedState')}
                          {recorderState === 'idle' && t('record')}
                        </span>
                      </div>

                      {recorderState === 'idle' && (
                        <div className="upload-zone">
                          <label className="upload-label">
                            <Icon name="upload" size={25} />
                            <span>{t('orUpload')}</span>
                            <input
                              key={uploadKey}
                              type="file"
                              accept="audio/*,video/*"
                              hidden
                              onChange={onFileSelected}
                            />
                          </label>
                        </div>
                      )}
                    </>
                  )}

                  {job && job.status !== 'done' && (
                    <div className="job-panel">
                      <div className="progress-track">
                        <div
                          className={`progress-fill ${job.status === 'error' ? 'danger' : ''}`}
                          style={{ width: `${job.status === 'error' ? 100 : Math.max(4, Math.min(99, job.progress || 4))}%` }}
                        />
                      </div>
                      <p>
                        {job.status === 'error'
                          ? job.error
                          : job.status === 'pending'
                            ? t('queued')
                            : job.message || t('jobProgress', { progress: Math.max(4, Math.min(99, job.progress || 4)) })}
                      </p>
                      {job.status === 'error' && (
                        <button className="btn btn-ghost btn-sm" onClick={() => setJob(null)}>
                          <Icon name="x" size={14} /> {t('jobDismiss')}
                        </button>
                      )}
                    </div>
                  )}
                </div>

                {lastResult && (
                  <div className="card fade-in">
                    <ResultCard
                      item={lastResult}
                      {...cardProps}
                      onRemove={removeItem}
                      t={t}
                    />
                  </div>
                )}

                <div className="history-head">
                  <h2>{t('history.recent')}</h2>
                  <button className="btn btn-danger btn-sm" onClick={clearHistory}>
                    <Icon name="trash" size={14} /> {t('clearHistory')}
                  </button>
                </div>
                <HistoryList
                  items={history}
                  expandedId={expandedId}
                  setExpandedId={setExpandedId}
                  cardProps={historyCardProps}
                  onRemove={removeItem}
                  t={t}
                />
              </div>
            )}

            {view === 'direct' && (
              <div className="fade-in">
                <div className="page-head">
                  <h2>{t('nav.direct')}</h2>
                  <p>{t('live.hint')}</p>
                </div>
                <LiveMode
                  language={language}
                  onError={setError}
                  onSaved={(item) => {
                    loadHistory();
                    notify(t('live.saved'));
                  }}
                />
              </div>
            )}

            {view === 'commands' && (
              <div className="fade-in">
                <div className="page-head">
                  <h2>{t('nav.commands')}</h2>
                  <p>{t('commands.hint')}</p>
                </div>
                <CommandMic
                  language={language}
                  onCommand={handleVoiceCommand}
                  onError={setError}
                  disabled={false}
                />
              </div>
            )}

            {view === 'history' && (
              <div className="fade-in">
                <div className="page-head">
                  <h2>{t('nav.history')}</h2>
                  <p>{t('historyTitle', { count: history.length })}</p>
                </div>
                <div style={{ marginBottom: 16 }}>
                  <button className="btn btn-danger btn-sm" onClick={clearHistory}>
                    <Icon name="trash" size={14} /> {t('clearHistory')}
                  </button>
                </div>
                <HistoryList
                  items={history}
                  expandedId={expandedId}
                  setExpandedId={setExpandedId}
                  cardProps={historyCardProps}
                  onRemove={removeItem}
                  t={t}
                />
              </div>
            )}

            {view === 'dashboard' && <DashboardView user={user} onError={setError} />}
          </main>
        </div>
      </div>
    </div>
  );
}
