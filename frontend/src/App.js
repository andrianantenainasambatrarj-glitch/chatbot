import React, { useState, useRef, useEffect, useCallback } from 'react';
import './styles.css';
import wavEncoder from 'wav-encoder';

// En développement, le proxy CRA (voir package.json) relaie vers le backend.
// En production, renseignez REACT_APP_API_URL (voir frontend/.env.example).
const API_BASE = process.env.REACT_APP_API_URL || '';

function App() {
  const [recording, setRecording] = useState(false);
  const [status, setStatus] = useState('');
  const [transcription, setTranscription] = useState('');
  const [downloadUrl, setDownloadUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const [darkMode, setDarkMode] = useState(false);

  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const audioChunksRef = useRef([]);

  const mediaSupported =
    typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices &&
    typeof window.MediaRecorder !== 'undefined';

  // Chargement de l'historique persistant côté serveur
  const fetchHistory = useCallback(() => {
    fetch(`${API_BASE}/api/transcriptions`)
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((items) =>
        setHistory(
          items.map((item) => ({
            id: item.id,
            text: item.text,
            url: `${API_BASE}${item.download_url}`,
            timestamp: new Date(item.created_at).toLocaleString(),
          }))
        )
      )
      .catch((err) => console.error("Chargement de l'historique impossible :", err));
  }, []);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const stopMicrophone = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  };

  const startRecording = () => {
    if (!mediaSupported) {
      setStatus("Erreur : votre navigateur ne supporte pas l'enregistrement audio.");
      return;
    }
    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then((stream) => {
        streamRef.current = stream;
        const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : '';
        const mediaRecorder = mimeType
          ? new MediaRecorder(stream, { mimeType })
          : new MediaRecorder(stream);
        mediaRecorderRef.current = mediaRecorder;
        audioChunksRef.current = [];

        mediaRecorder.ondataavailable = (event) => {
          if (event.data.size > 0) audioChunksRef.current.push(event.data);
        };
        mediaRecorder.onstop = () => {
          stopMicrophone();
          convertAndSendAudio();
        };

        mediaRecorder.start();
        setRecording(true);
        setStatus('Enregistrement en cours...');
      })
      .catch((err) => {
        stopMicrophone();
        if (err.name === 'NotAllowedError') {
          setStatus("Erreur : l'accès au microphone a été refusé. Autorisez-le dans votre navigateur.");
        } else if (err.name === 'NotFoundError') {
          setStatus('Erreur : aucun microphone détecté sur cet appareil.');
        } else {
          setStatus(`Erreur : ${err.message}`);
        }
      });
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      setRecording(false);
      setIsLoading(true);
      setStatus('Traitement en cours...');
    }
  };

  const convertAndSendAudio = () => {
    const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
    const formData = new FormData();

    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const reader = new FileReader();
    reader.onload = () => {
      audioContext.decodeAudioData(reader.result, (decodedData) => {
        const audioData = decodedData.getChannelData(0);
        wavEncoder
          .encode({ sampleRate: decodedData.sampleRate, channelData: [audioData] })
          .then((buffer) => {
            const wavBlob = new Blob([new Uint8Array(buffer)], { type: 'audio/wav' });
            formData.append('audio', wavBlob, 'recording.wav');
            return fetch(`${API_BASE}/api/transcribe`, { method: 'POST', body: formData });
          })
          .then(async (response) => {
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
              throw new Error(data.error || `Erreur HTTP ${response.status}`);
            }
            setStatus('Transcription terminée.');
            setTranscription(data.text || 'Aucune transcription');
            setDownloadUrl(`${API_BASE}${data.download_url}`);
            fetchHistory();
          })
          .catch((err) => {
            console.error('Erreur de transcription :', err);
            setStatus(`Erreur : ${err.message}`);
          })
          .finally(() => setIsLoading(false));
      }, (err) => {
        setStatus(`Erreur de décodage audio : ${err.message}`);
        setIsLoading(false);
      });
    };
    reader.onerror = () => {
      setStatus("Erreur : impossible de lire l'enregistrement.");
      setIsLoading(false);
    };
    reader.readAsArrayBuffer(audioBlob);
  };

  const clearHistory = () => {
    fetch(`${API_BASE}/api/transcriptions`, { method: 'DELETE' })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        setHistory([]);
        setTranscription('');
        setDownloadUrl('');
        setStatus('Historique effacé.');
      })
      .catch((err) => setStatus(`Erreur lors de la suppression : ${err.message}`));
  };

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
          <p className="subtitle">Transcrivez votre voix en document Word</p>
          <div className="instruction-card">
            <h3>Instructions</h3>
            <ul>
              <li>Cliquez sur <strong>Enregistrer</strong> et parlez distinctement.</li>
              <li>Cliquez sur <strong>Arrêter</strong> pour terminer.</li>
              <li>Patientez pour la transcription, puis téléchargez.</li>
            </ul>
          </div>
          <button
            className={`record-button ${recording ? 'stop' : ''}`}
            onClick={recording ? stopRecording : startRecording}
            disabled={!mediaSupported || isLoading}
          >
            {recording ? '⏹ Arrêter' : '🎙️ Enregistrer'}
          </button>
          {!mediaSupported && (
            <p className="error-message">
              L'enregistrement audio nécessite un navigateur récent (Chrome, Edge, Firefox) en HTTPS.
            </p>
          )}
          {isLoading && <div className="loader" role="status" aria-label="Traitement en cours"></div>}
          <div className="result">{status}</div>
          {transcription && (
            <div className="transcription-card">
              <h3>Transcription</h3>
              <p>{transcription}</p>
            </div>
          )}
          {downloadUrl && (
            <a className="download-button" href={downloadUrl} download>
              📄 Télécharger le document Word
            </a>
          )}
          <button
            className="clear-history"
            onClick={clearHistory}
            disabled={history.length === 0 || isLoading}
          >
            🗑️ Effacer l'historique
          </button>
        </section>
        {history.length > 0 && (
          <section className="history-section">
            <h2>Historique</h2>
            <div className="history-grid">
              {history.map((item) => (
                <div key={item.id} className="history-card">
                  <p><strong>{item.timestamp}</strong></p>
                  <p>{item.text}</p>
                  <a href={item.url} download className="download-link">
                    Télécharger
                  </a>
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
