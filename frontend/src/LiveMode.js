import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { getToken, wsUrl } from './api';
import { MicPcmStream } from './audioStream';

export default function LiveMode({ language, onSaved, onError }) {
  const { t } = useTranslation();
  const [state, setState] = useState('idle'); // idle | connecting | live | stopped
  const [committed, setCommitted] = useState('');
  const [partial, setPartial] = useState('');
  const [info, setInfo] = useState('');

  const wsRef = useRef(null);
  const micRef = useRef(null);

  const cleanup = () => {
    micRef.current?.stop();
    micRef.current = null;
  };

  useEffect(() => () => {
    wsRef.current?.close();
    cleanup();
  }, []);

  const stop = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'stop' }));
    }
    cleanup();
    setState('stopped');
    setInfo(t('live.stopped'));
  };

  const start = async () => {
    setCommitted('');
    setPartial('');
    setInfo(t('live.starting'));
    setState('connecting');

    const mic = new MicPcmStream(
      () => {},
      (err) => {
        setState('idle');
        if (err.name === 'NotAllowedError') onError(t('micDenied'));
        else if (err.name === 'NotFoundError') onError(t('micNotFound'));
        else onError(err.message);
      }
    );

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
        cleanup();
      }
    };

    ws.onclose = () => {
      cleanup();
      setInfo((previous) => previous);
    };

    ws.onopen = async () => {
      mic.attachWebSocket(ws);
      try {
        await mic.start();
      } catch {
        ws.close();
      }
    };
    micRef.current = mic;
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
        {!committed && !partial && state === 'idle' && <p className="live-placeholder">—</p>}
      </div>
    </div>
  );
}
