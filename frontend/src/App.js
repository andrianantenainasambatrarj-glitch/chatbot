import React, { useState, useRef, useEffect, useCallback } from 'react';
import './styles.css';

// En développement, le proxy CRA relaie vers le backend (clé "proxy" du package.json).
// En production : renseigner REACT_APP_API_URL (voir .env.example).
const API_BASE = process.env.REACT_APP_API_URL || '';

const ACCEPTED_AUDIO = '.wav,.mp3,.m4a,.ogg,.oga,.webm,.mp4,.flac,.aac,.opus,audio/*';

function formatTime(totalSeconds) {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const mm = String(minutes).padStart(2, '0');
  const ss = String(seconds).padStart(2, '0');
  return hours > 0 ? `${hours}:${mm}:${ss}` : `${mm}:${ss}`;
}

function App() {
  // 'idle' | 'recording' | 'paused' | 'review' | 'processing'
  const [phase, setPhase] = useState('idle');
  const [elapsed, setElapsed] = useState(0);
  const [previewUrl, setPreviewUrl] = useState('');
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

  const mediaSupported =
    typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices &&
    typeof window.MediaRecorder !== 'undefined';

  const exportUrl = useCallback(
    (item, fmt) => (item?.exports?.[fmt] ? `${API_BASE}${item.exports[fmt]}` : ''),
    []
  );

  const fetchHistory = useCallback(() => {
    fetch(`${API_BASE}/api/transcriptions`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setHistory)
      .catch((err) => console.error('Chargement de l’historique impossible :', err));
  }, []);

  useEffect(() => {
    fetchHistory();
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, [fetchHistory]);

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

  // ------------------------------------------------------------------
  // Enregistrement
  // ------------------------------------------------------------------
  const startRecording = () => {
    setError('');
    setStatus('');
    if (!mediaSupported) {
      setError("Votre navigateur ne supporte pas l'enregistrement audio.");
      return;
    }
    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then((stream) => {
        streamRef.current = stream;
        const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'];
        const mimeType = candidates.find((t) => MediaRecorder.isTypeSupported(t)) || '';
        const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
        mediaRecorderRef.current = recorder;
        audioChunksRef.current = [];

        recorder.ondataavailable = (event) => {
          if (event.data.size > 0) audioChunksRef.current.push(event.data);
        };
        recorder.onstop = () => {
          stopMicrophone();
          if (timerRef.current) clearInterval(timerRef.current);
          const type = recorder.mimeType || 'audio/webm';
          const blob = new Blob(audioChunksRef.current, { type });
          setPreview(blob);
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
        if (err.name === 'NotAllowedError') {
          setError("L'accès au microphone a été refusé. Autorisez-le dans votre navigateur.");
        } else if (err.name === 'NotFoundError') {
          setError('Aucun microphone détecté sur cet appareil.');
        } else {
          setError(`Erreur : ${err.message}`);
        }
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
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
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
    sendAudio(blob, `enregistrement.${ext}`);
  };

  // ------------------------------------------------------------------
  // Upload d'un fichier
  // ------------------------------------------------------------------
  const onFileSelected = (event) => {
    const file = event.target.files?.[0];
    if (file) sendAudio(file, file.name);
    event.target.value = '';
  };

  // ------------------------------------------------------------------
  // Envoi au backend
  // ------------------------------------------------------------------
  const sendAudio = (blobOrFile, filename) => {
    setError('');
    setStatus('Envoi et transcription en cours...');
    setPhase('processing');

    const formData = new FormData();
    formData.append('audio', blobOrFile, filename);

    fetch(`${API_BASE}/api/transcribe`, { method: 'POST', body: formData })
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || `Erreur HTTP ${response.status}`);
        setCurrent(data);
        setEditedText(data.text);
        setStatus('Transcription terminée.');
        fetchHistory();
      })
      .catch((err) => {
        setError(err.message);
        setStatus('');
      })
      .finally(() => {
        if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
        previewUrlRef.current = '';
        setPreviewUrl('');
        setElapsed(0);
        setPhase('idle');
      });
  };

  // ------------------------------------------------------------------
  // Édition
  // ------------------------------------------------------------------
  const saveEdits = () => {
    if (!current) return;
    setIsSaving(true);
    setError('');
    fetch(`${API_BASE}/api/transcriptions/${current.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: editedText }),
    })
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || `Erreur HTTP ${response.status}`);
        setCurrent(data);
        setStatus('Modifications enregistrées, exports régénérés.');
        fetchHistory();
      })
      .catch((err) => setError(err.message))
      .finally(() => setIsSaving(false));
  };

  // ------------------------------------------------------------------
  // Suppression
  // ------------------------------------------------------------------
  const deleteItem = (id) => {
    fetch(`${API_BASE}/api/transcriptions/${id}`, { method: 'DELETE' })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        if (current?.id === id) {
          setCurrent(null);
          setEditedText('');
        }
        fetchHistory();
      })
      .catch((err) => setError(err.message));
  };

  const clearHistory = () => {
    if (!window.confirm('Supprimer définitivement toutes les transcriptions ?')) return;
    fetch(`${API_BASE}/api/transcriptions`, { method: 'DELETE' })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        setHistory([]);
        setCurrent(null);
        setEditedText('');
        setStatus('Historique effacé.');
      })
      .catch((err) => setError(err.message));
  };

  const busy = phase === 'processing';

  return (
    <div className={`app ${darkMode ? 'dark-mode' : ''}`}>
      <header className="header">
        <h1 className="title">Chatbot Vocal</h1>
        <button className="theme-toggle" onClick={() => setDarkMode(!darkMode)}>
          {darkMode ? '☀️ Mode Clair' : '🌙 Mode Sombre'}
        </button>
      </header>

      <main className="main-content">
        <section className="controls">
          <p className="subtitle">Transcrivez votre voix en document Word, PDF, TXT ou sous-titres</p>

          <div className="instruction-card">
            <h3>Instructions</h3>
            <ul>
              <li><strong>Enregistrez</strong> votre voix (pause possible) ou <strong>déposez un fichier audio</strong>.</li>
              <li>Réécoutez l'enregistrement, puis lancez la transcription.</li>
              <li>Corrigez le texte si besoin, puis téléchargez le document.</li>
            </ul>
          </div>

          {/* Chronomètre */}
          {(phase === 'recording' || phase === 'paused') && (
            <div className={`recorder-panel ${phase === 'paused' ? 'paused' : ''}`}>
              <span className="recording-dot" aria-hidden="true"></span>
              <span className="timer">{formatTime(elapsed)}</span>
              <span className="recorder-state">{phase === 'paused' ? 'En pause' : 'Enregistrement...'}</span>
            </div>
          )}

          {/* Boutons d'enregistrement */}
          <div className="button-row">
            {phase === 'idle' && (
              <button className="record-button" onClick={startRecording} disabled={!mediaSupported || busy}>
                🎙️ Enregistrer
              </button>
            )}
            {phase === 'recording' && (
              <>
                <button className="secondary-button" onClick={pauseRecording}>⏸ Pause</button>
                <button className="record-button stop" onClick={stopRecording}>⏹ Arrêter</button>
              </>
            )}
            {phase === 'paused' && (
              <>
                <button className="record-button" onClick={resumeRecording}>▶️ Reprendre</button>
                <button className="record-button stop" onClick={stopRecording}>⏹ Arrêter</button>
              </>
            )}
          </div>

          {/* Réécoute avant envoi */}
          {phase === 'review' && previewUrl && (
            <div className="review-card">
              <h3>Réécoutez votre enregistrement</h3>
              <audio src={previewUrl} controls className="audio-player" />
              <div className="button-row">
                <button className="record-button" onClick={submitRecording} disabled={busy}>
                  ✅ Transcrire
                </button>
                <button className="secondary-button danger-outline" onClick={discardRecording} disabled={busy}>
                  ❌ Réenregistrer
                </button>
              </div>
            </div>
          )}

          {phase === 'processing' && <div className="loader" role="status" aria-label="Traitement en cours"></div>}

          {/* Upload de fichier */}
          {phase === 'idle' && (
            <div className="upload-zone">
              <label className="upload-label">
                📁 Ou choisissez un fichier audio (MP3, WAV, M4A, OGG, WEBM...)
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={ACCEPTED_AUDIO}
                  onChange={onFileSelected}
                  hidden
                />
              </label>
            </div>
          )}

          {!mediaSupported && (
            <p className="error-message">
              L'enregistrement nécessite un navigateur récent (Chrome, Edge, Firefox) en HTTPS.
              L'import de fichier reste disponible.
            </p>
          )}
          {error && <div className="error-message" role="alert">⚠️ {error}</div>}
          {status && <div className="result">{status}</div>}

          {/* Transcription courante éditable */}
          {current && (
            <div className="transcription-card">
              <h3>Transcription {current.duration_seconds ? `· ${formatTime(Math.round(current.duration_seconds))} d'audio` : ''}</h3>
              <textarea
                className="transcription-editor"
                value={editedText}
                onChange={(e) => setEditedText(e.target.value)}
                rows={Math.min(12, Math.max(4, editedText.split('\n').length))}
                aria-label="Texte de la transcription, éditable"
              />
              <div className="button-row wrap">
                <button className="secondary-button" onClick={saveEdits} disabled={isSaving || editedText.trim() === current.text}>
                  💾 Enregistrer les corrections
                </button>
                <a className="export-button word" href={exportUrl(current, 'docx')} download>📄 Word</a>
                <a className="export-button pdf" href={exportUrl(current, 'pdf')} download>📕 PDF</a>
                <a className="export-button txt" href={exportUrl(current, 'txt')} download>📝 TXT</a>
                {current.has_timestamps && (
                  <a className="export-button srt" href={exportUrl(current, 'srt')} download>💬 Sous-titres SRT</a>
                )}
              </div>
            </div>
          )}

          <button className="clear-history" onClick={clearHistory} disabled={history.length === 0 || busy}>
            🗑️ Effacer tout l'historique
          </button>
        </section>

        {/* Historique persistant */}
        {history.length > 0 && (
          <section className="history-section">
            <h2>Historique ({history.length})</h2>
            <div className="history-grid">
              {history.map((item) => (
                <div key={item.id} className="history-card">
                  <div className="history-card-head">
                    <strong>{new Date(item.created_at).toLocaleString()}</strong>
                    <button
                      className="icon-button"
                      title="Supprimer cette transcription"
                      onClick={() => deleteItem(item.id)}
                    >
                      ✕
                    </button>
                  </div>
                  <p className="history-text">{item.text}</p>
                  <div className="history-exports">
                    <a href={`${API_BASE}${item.exports.docx}`} download>Word</a>
                    <a href={`${API_BASE}${item.exports.pdf}`} download>PDF</a>
                    <a href={`${API_BASE}${item.exports.txt}`} download>TXT</a>
                    {item.exports.srt && <a href={`${API_BASE}${item.exports.srt}`} download>SRT</a>}
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

export default App;
