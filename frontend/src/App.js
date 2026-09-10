import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import './i18n';
import './styles.css';
import { apiFetch, authApi, clearToken, getToken } from './api';
import AuthScreen from './AuthScreen';
import LiveMode from './LiveMode';

const ACCEPTED_AUDIO = '.wav,.mp3,.m4a,.ogg,.oga,.webm,.mp4,.flac,.aac,.opus,audio/*';

function formatTime(totalSeconds) {
  const s = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(s / 3600);
  const minutes = Math.floor((s % 3600) / 60);
  const seconds = s % 60;
  return hours > 0
    ? `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
    : `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

function App() {
  const { t, i18n } = useTranslation();

  // ----- Authentification
  const [user, setUser] = useState(null);
  const [authChecking, setAuthChecking] = useState(!!getToken());

  // ----- Configuration moteur / langue
  const [engines, setEngines] = useState([]);
  const [engine, setEngine] = useState('vosk');
  const [language, setLanguage] = useState('fr');
  const [tab, setTab] = useState('standard'); // standard | live

  // ----- Enregistrement
  const [phase, setPhase] = useState('idle'); // idle | recording | paused | review | processing
  const [elapsed, setElapsed] = useState(0);
  const [previewUrl, setPreviewUrl] = useState('');
  const [job, setJob] = useState(null);

  // ----- Résultats
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [history, setHistory] = useState([]);
  const [current, setCurrent] = useState(null);
  const [editedText, setEditedText] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [darkMode, setDarkMode] = useState(false);

  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerRef = useRef(null);
  const previewUrlRef = useRef('');
  const fileInputRef = useRef(null);
  const pollRef = useRef(null);

  const mediaSupported =
    typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices &&
    typeof window.MediaRecorder !== 'undefined';

  // ------------------------------------------------------------------
  const showError = useCallback((message) => {
    setError(message);
    setStatus('');
  }, []);

  const handle401 = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  const fetchHistory = useCallback(() => {
    apiFetch('/api/transcriptions')
      .then(setHistory)
      .catch((err) => {
        if (err.status === 401) handle401();
        else console.error('Historique impossible :', err);
      });
  }, [handle401]);

  const fetchEngines = useCallback(() => {
    apiFetch('/api/engines')
      .then(setEngines)
      .catch((err) => console.error('Moteurs indisponibles :', err));
  }, []);

  useEffect(() => {
    if (!getToken()) return;
    authApi
      .me()
      .then(setUser)
      .catch(() => clearToken())
      .finally(() => setAuthChecking(false));
  }, []);

  useEffect(() => {
    if (user) {
      fetchEngines();
      fetchHistory();
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [user, fetchEngines, fetchHistory]);

  useEffect(() => () => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    streamRef.current?.getTracks().forEach((tr) => tr.stop());
  }, []);

  const activeEngineMeta = engines.find((e) => e.name === engine);
  const languageOptions = activeEngineMeta?.languages || [{ code: 'fr', available: true }];

  const setPreview = (blob) => {
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    const url = URL.createObjectURL(blob);
    previewUrlRef.current = url;
    setPreviewUrl(url);
  };

  const stopMicrophone = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  };

  const logout = () => {
    clearToken();
    setUser(null);
  };

  // ------------------------------------------------------------------
  // Enregistrement micro
  // ------------------------------------------------------------------
  const startRecording = () => {
    setError('');
    setStatus('');
    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then((stream) => {
        streamRef.current = stream;
        const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'];
        const mimeType = candidates.find((candidate) => MediaRecorder.isTypeSupported(candidate)) || '';
        const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
        mediaRecorderRef.current = recorder;
        audioChunksRef.current = [];

        recorder.ondataavailable = (event) => {
          if (event.data.size > 0) audioChunksRef.current.push(event.data);
        };
        recorder.onstop = () => {
          stopMicrophone();
          if (timerRef.current) clearInterval(timerRef.current);
          setPreview(new Blob(audioChunksRef.current, { type: recorder.mimeType || 'audio/webm' }));
          setPhase('review');
        };

        recorder.start();
        setElapsed(0);
        setPhase('recording');
        timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);
      })
      .catch((err) => {
        stopMicrophone();
        setPhase('idle');
        if (err.name === 'NotAllowedError') showError(t('micDenied'));
        else if (err.name === 'NotFoundError') showError(t('micNotFound'));
        else showError(err.message);
      });
  };

  const pauseRecording = () => {
    mediaRecorderRef.current?.pause();
    if (timerRef.current) clearInterval(timerRef.current);
    setPhase('paused');
  };

  const resumeRecording = () => {
    mediaRecorderRef.current?.resume();
    timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);
    setPhase('recording');
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current?.state !== 'inactive') mediaRecorderRef.current.stop();
  };

  const discardRecording = () => {
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    previewUrlRef.current = '';
    setPreviewUrl('');
    setElapsed(0);
    setPhase('idle');
  };

  const submitRecording = () => {
    const blob = new Blob(audioChunksRef.current, {
      type: mediaRecorderRef.current?.mimeType || 'audio/webm',
    });
    const mime = blob.type || 'audio/webm';
    const ext = mime.includes('ogg') ? 'ogg' : mime.includes('mp4') ? 'mp4' : 'webm';
    // Les petits enregistrements passent en synchrone
    sendAudio(blob, `enregistrement.${ext}`, false);
  };

  // ------------------------------------------------------------------
  // Upload fichier -> systématiquement asynchrone avec progression
  // ------------------------------------------------------------------
  const onFileSelected = (event) => {
    const file = event.target.files?.[0];
    if (file) sendAudio(file, file.name, true);
    event.target.value = '';
  };

  const sendAudio = (blobOrFile, filename, asyncMode) => {
    setError('');
    setStatus(asyncMode ? t('queued') : t('processing'));
    setJob(null);
    setPhase('processing');

    const formData = new FormData();
    formData.append('audio', blobOrFile, filename);
    formData.append('engine', engine);
    formData.append('language', language);
    if (asyncMode) formData.append('async', '1');

    apiFetch('/api/transcribe', { method: 'POST', body: formData })
      .then((data) => {
        if (data.status && ['pending', 'processing'].includes(data.status)) {
          setJob(data);
          pollJob(data.id);
        } else {
          applyNewTranscription(data);
          setPhase('idle');
        }
      })
      .catch((err) => {
        if (err.status === 401) handle401();
        else showError(err.message);
        setPhase('idle');
      })
      .finally(() => {
        if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
        previewUrlRef.current = '';
        setPreviewUrl('');
        setElapsed(0);
      });
  };

  const pollJob = (jobId) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(() => {
      apiFetch(`/api/jobs/${jobId}`)
        .then((jobState) => {
          setJob(jobState);
          if (jobState.status === 'done') {
            clearInterval(pollRef.current);
            applyNewTranscription(jobState.transcription);
            setPhase('idle');
          } else if (jobState.status === 'error') {
            clearInterval(pollRef.current);
            showError(jobState.error || 'Échec de la tâche');
            setPhase('idle');
          }
        })
        .catch(() => {});
    }, 1000);
  };

  const applyNewTranscription = (transcription) => {
    setCurrent(transcription);
    setEditedText(transcription.text);
    setStatus(t('done'));
    fetchHistory();
  };

  // ------------------------------------------------------------------
  const saveEdits = () => {
    if (!current) return;
    setIsSaving(true);
    apiFetch(`/api/transcriptions/${current.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: editedText }),
    })
      .then((data) => {
        setCurrent(data);
        setStatus(t('editsSaved'));
        fetchHistory();
      })
      .catch((err) => showError(err.message))
      .finally(() => setIsSaving(false));
  };

  const deleteItem = (id) => {
    apiFetch(`/api/transcriptions/${id}`, { method: 'DELETE' })
      .then(() => {
        if (current?.id === id) {
          setCurrent(null);
          setEditedText('');
        }
        fetchHistory();
      })
      .catch((err) => showError(err.message));
  };

  const clearHistory = () => {
    if (!window.confirm(t('confirmClear'))) return;
    apiFetch('/api/transcriptions', { method: 'DELETE' })
      .then(() => {
        setHistory([]);
        setCurrent(null);
        setEditedText('');
        setStatus(t('historyCleared'));
      })
      .catch((err) => showError(err.message));
  };

  const exportUrl = (item, fmt) => (item?.exports?.[fmt] ? `${item.exports[fmt]}` : '');

  const exportLabel = (fmt) =>
    ({
      docx: `📄 ${t('exportWord')}`,
      pdf: `📕 ${t('exportPdf')}`,
      txt: `📝 ${t('exportTxt')}`,
      srt: `💬 ${t('exportSrt')}`,
    }[fmt]);

  // Les liens de téléchargement passent par un fetch authentifié (jeton en en-tête)
  const downloadExport = async (item, fmt) => {
    const response = await fetch(exportUrl(item, fmt), {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${item.id}.${fmt}`;
    link.click();
    URL.revokeObjectURL(url);
  };

  // ------------------------------------------------------------------
  if (authChecking) {
    return <div className="app"><div className="centered-loader"><div className="loader"></div></div></div>;
  }
  if (!user) {
    return (
      <div className={`app ${darkMode ? 'dark-mode' : ''}`}>
        <LanguageSwitch i18n={i18n} />
        <AuthScreen onAuthed={(u) => { setUser(u); fetchEngines(); fetchHistory(); }} />
      </div>
    );
  }

  const busy = phase === 'processing';

  return (
    <div className={`app ${darkMode ? 'dark-mode' : ''}`}>
      <a href="#main" className="skip-link">Aller au contenu</a>
      <header className="header">
        <h1 className="title">Chatbot Vocal</h1>
        <div className="header-actions">
          <LanguageSwitch i18n={i18n} />
          <button className="theme-toggle" onClick={() => setDarkMode(!darkMode)} aria-pressed={darkMode}>
            {darkMode ? '☀️' : '🌙'}
          </button>
          <button className="secondary-button small" onClick={logout}>{t('auth.logout')}</button>
        </div>
      </header>

      <main id="main" className="main-content">
        {/* Sélecteurs moteur / langue */}
        <div className="selectors">
          <label className="selector">
            <span>{t('engine')}</span>
            <select
              value={engine}
              onChange={(e) => {
                setEngine(e.target.value);
                if (e.target.value === 'whisper') setTab('standard');
              }}
            >
              {engines.length === 0 && <option value="vosk">{t('vosk')}</option>}
              {engines.map((meta) => (
                <option key={meta.name} value={meta.name}>{meta.label}</option>
              ))}
            </select>
          </label>
          <label className="selector">
            <span>{t('language')}</span>
            <select value={language} onChange={(e) => setLanguage(e.target.value)}>
              {languageOptions.map((lang) => (
                <option key={lang.code} value={lang.code} disabled={!lang.available}>
                  {lang.code.toUpperCase()}
                  {lang.available ? '' : ' (modèle absent)'}
                </option>
              ))}
            </select>
          </label>
        </div>

        {/* Onglets */}
        <div className="tabs" role="tablist">
          <button
            role="tab"
            aria-selected={tab === 'standard'}
            className={`tab ${tab === 'standard' ? 'active' : ''}`}
            onClick={() => setTab('standard')}
          >
            🎙️ {t('modeStandard')}
          </button>
          <button
            role="tab"
            aria-selected={tab === 'live'}
            className={`tab ${tab === 'live' ? 'active' : ''}`}
            onClick={() => setTab('live')}
            disabled={engine === 'whisper'}
            title={engine === 'whisper' ? t('live.unsupported') : ''}
          >
            📡 {t('modeLive')}
          </button>
        </div>

        {error && <div className="error-message" role="alert">⚠️ {error}</div>}

        {tab === 'live' ? (
          <LiveMode
            language={language}
            onError={showError}
            onSaved={(transcription) => {
              applyNewTranscription(transcription);
              setStatus(t('live.saved'));
            }}
          />
        ) : (
          <section className="controls">
            <p className="subtitle">{t('tagline')}</p>

            <div className="instruction-card">
              <h3>{t('instructionsTitle')}</h3>
              <ul>
                <li>{t('instructions.one')}</li>
                <li>{t('instructions.two')}</li>
                <li>{t('instructions.three')}</li>
              </ul>
            </div>

            {(phase === 'recording' || phase === 'paused') && (
              <div className={`recorder-panel ${phase === 'paused' ? 'paused' : ''}`}>
                <span className="recording-dot" aria-hidden="true"></span>
                <span className="timer">{formatTime(elapsed)}</span>
                <span className="recorder-state">{phase === 'paused' ? t('pausedState') : t('recordingState')}</span>
              </div>
            )}

            <div className="button-row">
              {phase === 'idle' && (
                <button className="record-button" onClick={startRecording} disabled={!mediaSupported || busy}>
                  🎙️ {t('record')}
                </button>
              )}
              {phase === 'recording' && (
                <>
                  <button className="secondary-button" onClick={pauseRecording}>⏸ {t('pause')}</button>
                  <button className="record-button stop" onClick={stopRecording}>⏹ {t('stop')}</button>
                </>
              )}
              {phase === 'paused' && (
                <>
                  <button className="record-button" onClick={resumeRecording}>▶️ {t('resume')}</button>
                  <button className="record-button stop" onClick={stopRecording}>⏹ {t('stop')}</button>
                </>
              )}
            </div>

            {phase === 'review' && previewUrl && (
              <div className="review-card">
                <h3>{t('reviewTitle')}</h3>
                <p className="review-hint">{t('reviewHint')}</p>
                <audio src={previewUrl} controls className="audio-player" />
                <div className="button-row">
                  <button className="record-button" onClick={submitRecording} disabled={busy}>
                    ✅ {t('transcribe')}
                  </button>
                  <button className="secondary-button danger-outline" onClick={discardRecording} disabled={busy}>
                    ❌ {t('rerecord')}
                  </button>
                </div>
              </div>
            )}

            {phase === 'processing' && (
              <>
                <div className="loader" role="status" aria-label={t('processing')}></div>
                {job && (
                  <div className="job-progress">
                    <div className="progress-bar">
                      <div className="progress-fill" style={{ width: `${job.progress || 0}%` }}></div>
                    </div>
                    <p>{t('jobProgress', { progress: job.progress || 0 })} — {job.message}</p>
                  </div>
                )}
              </>
            )}

            {phase === 'idle' && (
              <div className="upload-zone">
                <label className="upload-label">
                  📁 {t('orUpload')}
                  <input ref={fileInputRef} type="file" accept={ACCEPTED_AUDIO} onChange={onFileSelected} hidden />
                </label>
              </div>
            )}

            {!mediaSupported && <p className="error-message">{t('micUnsupported')}</p>}
          </section>
        )}

        <div className="result" aria-live="polite">{status}</div>

        {current && (
          <div className="transcription-card">
            <h3>
              {t('transcriptionTitle')}
              {current.duration_seconds
                ? ` · ${t('duration', { time: formatTime(Math.round(current.duration_seconds)) })}`
                : ''}
              {' '}· {current.engine} · {current.language.toUpperCase()}
            </h3>
            <textarea
              className="transcription-editor"
              value={editedText}
              onChange={(e) => setEditedText(e.target.value)}
              rows={Math.min(12, Math.max(4, editedText.split('\n').length))}
              aria-label={t('transcriptionTitle')}
            />
            <div className="button-row wrap">
              <button
                className="secondary-button"
                onClick={saveEdits}
                disabled={isSaving || editedText.trim() === current.text}
              >
                💾 {t('saveEdits')}
              </button>
              {['docx', 'pdf', 'txt', ...(current.has_timestamps ? ['srt'] : [])].map((fmt) => (
                <button
                  key={fmt}
                  className={`export-button ${fmt}`}
                  onClick={() => downloadExport(current, fmt).catch(showError)}
                >
                  {exportLabel(fmt)}
                </button>
              ))}
            </div>
          </div>
        )}

        <button className="clear-history" onClick={clearHistory} disabled={history.length === 0 || busy}>
          🗑️ {t('clearHistory')}
        </button>

        {history.length > 0 && (
          <section className="history-section" aria-label={t('historyTitle', { count: history.length })}>
            <h2>{t('historyTitle', { count: history.length })}</h2>
            <div className="history-grid">
              {history.map((item) => (
                <div key={item.id} className="history-card">
                  <div className="history-card-head">
                    <strong>{new Date(item.created_at).toLocaleString()}</strong>
                    <button className="icon-button" title="✕" onClick={() => deleteItem(item.id)}>✕</button>
                  </div>
                  <p className="history-meta">{item.engine} · {item.language.toUpperCase()}
                    {item.duration_seconds ? ` · ${formatTime(Math.round(item.duration_seconds))}` : ''}</p>
                  <p className="history-text">{item.text}</p>
                  <div className="history-exports">
                    {['docx', 'pdf', 'txt', ...(item.has_timestamps ? ['srt'] : [])].map((fmt) => (
                      <button key={fmt} onClick={() => downloadExport(item, fmt).catch(showError)}>
                        {fmt.toUpperCase()}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

function LanguageSwitch({ i18n }) {
  return (
    <select
      className="language-switch"
      aria-label="Language / Langue"
      value={i18n.language?.startsWith('en') ? 'en' : 'fr'}
      onChange={(e) => {
        i18n.changeLanguage(e.target.value);
        localStorage.setItem('cv_lang', e.target.value);
      }}
    >
      <option value="fr">FR</option>
      <option value="en">EN</option>
    </select>
  );
}

export default App;
