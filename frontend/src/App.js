import React, { useState, useRef } from 'react';
import './App.css';
import wavEncoder from 'wav-encoder';

function App() {
  const [recording, setRecording] = useState(false);
  const [result, setResult] = useState('');
  const [transcription, setTranscription] = useState('');
  const [downloadUrl, setDownloadUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const [darkMode, setDarkMode] = useState(false);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  const startRecording = () => {
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(stream => {
        const mediaRecorder = new MediaRecorder(stream);
        mediaRecorderRef.current = mediaRecorder;
        audioChunksRef.current = [];

        mediaRecorder.ondataavailable = event => {
          audioChunksRef.current.push(event.data);
        };

        mediaRecorder.onstop = convertAndSendAudio;
        mediaRecorder.start();
        setRecording(true);
        setResult('Enregistrement en cours...');
      })
      .catch(err => setResult(`Erreur : ${err.message}`));
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
      setRecording(false);
      setIsLoading(true);
      setResult('Traitement en cours...');
    }
  };

  const convertAndSendAudio = () => {
    const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
    const formData = new FormData();

    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const reader = new FileReader();
    reader.onload = () => {
      audioContext.decodeAudioData(reader.result, decodedData => {
        const audioData = decodedData.getChannelData(0);
        wavEncoder.encode({
          sampleRate: decodedData.sampleRate,
          channelData: [audioData]
        }).then(buffer => {
          const wavBlob = new Blob([new Uint8Array(buffer)], { type: 'audio/wav' });
          formData.append('audio', wavBlob, 'recording.wav');

          fetch('http://localhost:5001/speak', {
            method: 'POST',
            body: formData
          })
          .then(response => {
            if (!response.ok) {
              throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
          })
          .then(data => {
            const newTranscription = data.text || 'Aucune transcription';
            setResult(data.status);
            setTranscription(newTranscription);
            if (data.status.includes('généré')) {
              setDownloadUrl('http://localhost:5001/static/transcription.docx');
              setHistory(prev => [...prev, { text: newTranscription, url: 'http://localhost:5001/static/transcription.docx', timestamp: new Date().toLocaleString() }]);
            }
            setIsLoading(false);
          })
          .catch(err => {
            console.error('Fetch error:', err);
            setResult(`Erreur : ${err.message}`);
            setIsLoading(false);
          });
        });
      }, err => {
        setResult(`Erreur de décodage audio : ${err.message}`);
        setIsLoading(false);
      });
    };
    reader.readAsArrayBuffer(audioBlob);
  };

  const clearHistory = () => {
    setHistory([]);
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
            disabled={!navigator.mediaDevices || isLoading}
          >
            {recording ? 'Arrêter' : 'Enregistrer'}
          </button>
          {isLoading && <div className="loader"></div>}
          <div className="result">{result}</div>
          {transcription && (
            <div className="transcription-card">
              <h3>Transcription</h3>
              <p>{transcription}</p>
            </div>
          )}
          {downloadUrl && (
            <a className="download-button" href={downloadUrl} download="transcription.docx">
              Télécharger Document
            </a>
          )}
          <button
            className="clear-history"
            onClick={clearHistory}
            disabled={history.length === 0}
          >
            Effacer l'historique
          </button>
        </section>
        {history.length > 0 && (
          <section className="history-section">
            <h2>Historique</h2>
            <div className="history-grid">
              {history.map((item, index) => (
                <div key={index} className="history-card">
                  <p><strong>{item.timestamp}</strong></p>
                  <p>{item.text}</p>
                  <a href={item.url} download="transcription.docx" className="download-link">
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