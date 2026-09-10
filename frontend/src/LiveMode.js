import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { getToken, wsUrl } from './api';

const TARGET_SAMPLE_RATE = 16000;

// Rééchantillonnage linéaire (généralement 44,1/48 kHz -> 16 kHz)
function downsample(buffer, fromRate) {
  if (fromRate === TARGET_SAMPLE_RATE) return buffer;
  const ratio = fromRate / TARGET_SAMPLE_RATE;
  const newLength = Math.round(buffer.length / ratio);
  const result = new Float32Array(newLength);
  let offset = 0;
  let pos = 0;
  while (pos < newLength) {
    const nextOffset = Math.round((pos + 1) * ratio);
    let sum = 0;
    let count = 0;
    for (let i = offset; i < nextOffset && i < buffer.length; i += 1) {
      sum += buffer[i];
      count += 1;
    }
    result[pos] = count ? sum / count : 0;
    offset = nextOffset;
    pos += 1;
  }
  return result;
}

function floatTo16BitPCM(float32Array) {
  const view = new DataView(new ArrayBuffer(float32Array.length * 2));
  float32Array.forEach((value, i) => {
    const clamped = Math.max(-1, Math.min(1, value));
    view.setInt16(i * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
  });
  return view.buffer;
}

export default function LiveMode({ language, onSaved, onError }) {
  const { t } = useTranslation();
  const [state, setState] = useState('idle'); // idle | connecting | live | stopped
  const [committed, setCommitted] = useState('');
  const [partial, setPartial] = useState('');
  const [info, setInfo] = useState('');

  const wsRef = useRef(null);
  const streamRef = useRef(null);
  const audioContextRef = useRef(null);
  const processorRef = useRef(null);
  const sourceRef = useRef(null);

  const cleanupMic = () => {
    processorRef.current?.disconnect();
    sourceRef.current?.disconnect();
    audioContextRef.current?.close().catch(() => {});
    streamRef.current?.getTracks().forEach((track) => track.stop());
    processorRef.current = null;
    sourceRef.current = null;
    audioContextRef.current = null;
    streamRef.current = null;
  };

  useEffect(() => () => {
    wsRef.current?.close();
    cleanupMic();
  }, []);

  const stop = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'stop' }));
    }
    cleanupMic();
    setState('stopped');
    setInfo(t('live.stopped'));
  };

  const start = async () => {
    setCommitted('');
    setPartial('');
    setInfo(t('live.starting'));
    setState('connecting');

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
    } catch (err) {
      setState('idle');
      if (err.name === 'NotAllowedError') onError(t('micDenied'));
      else if (err.name === 'NotFoundError') onError(t('micNotFound'));
      else onError(err.message);
      return;
    }
    streamRef.current = stream;

    const ws = new WebSocket(
      wsUrl(`/ws/transcribe?token=${encodeURIComponent(getToken() || '')}&language=${language}`)
    );
    ws.binaryType = 'arraybuffer';
    wsRef.current = ws;

    ws.onmessage = (event) => {
      let message;
      try {
        message = JSON.parse(event.data);
      } catch {
        return;
      }
      if (message.type === 'ready') {
        setState('live');
        setInfo(t('live.ready'));
      } else if (message.type === 'partial') {
        setPartial(message.text || '');
      } else if (message.type === 'final') {
        if (message.transcription) {
          setCommitted(message.transcription.text);
          setPartial('');
          onSaved?.(message.transcription);
        }
        setInfo(t('live.saved'));
        setState('stopped');
      } else if (message.type === 'error') {
        onError(message.error);
        setState('idle');
        cleanupMic();
      }
    };

    ws.onclose = () => {
      cleanupMic();
      if (state === 'connecting') setState('idle');
    };

    ws.onopen = () => {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      const context = new AudioContextClass();
      audioContextRef.current = context;
      const source = context.createMediaStreamSource(stream);
      sourceRef.current = source;
      const processor = context.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (event) => {
        if (ws.readyState !== WebSocket.OPEN) return;
        const input = event.inputBuffer.getChannelData(0);
        const resampled = downsample(input, context.sampleRate);
        ws.send(floatTo16BitPCM(resampled));
      };

      // Noeud à gain nul pour éviter tout écho vers les haut-parleurs
      const silentGain = context.createGain();
      silentGain.gain.value = 0;
      source.connect(processor);
      processor.connect(silentGain);
      silentGain.connect(context.destination);
    };
  };

  const busy = state === 'connecting' || state === 'live';

  return (
    <div className="live-panel">
      <p className="live-hint">{t('live.hint')}</p>
      <div className="button-row">
        {state === 'idle' || state === 'stopped' ? (
          <button className="record-button" onClick={start}>
            🔴 {t('live.start')}
          </button>
        ) : (
          <button className="record-button stop" onClick={stop} disabled={state === 'connecting'}>
            ⏹ {t('live.stop')}
          </button>
        )}
      </div>

      {busy && (
        <div className={`recorder-panel ${state === 'connecting' ? 'paused' : ''}`}>
          {state === 'live' && <span className="recording-dot" aria-hidden="true"></span>}
          <span className="recorder-state">{info}</span>
        </div>
      )}
      {state === 'stopped' && <div className="result" aria-live="polite">{info}</div>}

      <div className="live-transcript" aria-live="polite">
        {committed && <p className="live-committed">{committed}</p>}
        {partial && <p className="live-partial">{partial}</p>}
        {!committed && !partial && state === 'idle' && (
          <p className="live-placeholder">—</p>
        )}
      </div>
    </div>
  );
}
