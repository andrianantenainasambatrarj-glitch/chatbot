import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { getToken, wsUrl } from './api';
import { MicPcmStream } from './audioStream';
import Icon from './components/Icon';
import Waveform from './components/Waveform';

export default function LiveMode({ language, onSaved, onError }) {
  const { t } = useTranslation();
  const [state, setState] = useState('idle'); // idle | connecting | live | stopped
  const [committed, setCommitted] = useState('');
  const [partial, setPartial] = useState('');
  const [analyser, setAnalyser] = useState(null);

  const wsRef = useRef(null);
  const micRef = useRef(null);

  const cleanup = () => {
    micRef.current?.stop();
    micRef.current = null;
    setAnalyser(null);
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
  };

  const start = async () => {
    setCommitted('');
    setPartial('');
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
      } else if (message.type === 'partial') {
        setPartial(message.text || '');
      } else if (message.type === 'final') {
        if (message.transcription) {
          setCommitted(message.transcription.text);
          setPartial('');
          onSaved?.(message.transcription);
        }
        setState('stopped');
        cleanup();
      } else if (message.type === 'error') {
        onError(message.error);
        setState('idle');
        cleanup();
      }
    };

    ws.onclose = () => cleanup();

    ws.onopen = async () => {
      mic.attachWebSocket(ws);
      try {
        await mic.start();
        setAnalyser(mic.analyser);
      } catch {
        ws.close();
      }
    };
    micRef.current = mic;
  };

  const isLive = state === 'live';

  return (
    <div className="card live-panel fade-in">
      <div className="waveform-frame">
        <Waveform analyser={analyser} active={isLive} height={84} />
      </div>

      <p className="hint">{t('live.hint')}</p>

      <div className="record-stage">
        {state === 'idle' || state === 'stopped' ? (
          <button className="record-circle" onClick={start} aria-label={t('live.start')}>
            <Icon name="live" size={30} />
          </button>
        ) : (
          <button
            className={`record-circle ${isLive ? 'recording' : ''}`}
            onClick={stop}
            disabled={state === 'connecting'}
            aria-label={t('live.stop')}
          >
            <Icon name="stop" size={27} />
          </button>
        )}
        <span className="record-caption">
          {state === 'connecting' && t('live.starting')}
          {isLive && t('live.ready')}
          {state === 'stopped' && t('live.stopped')}
          {state === 'idle' && t('live.start')}
        </span>
      </div>

      <div className="live-transcript" aria-live="polite">
        {committed && <p className="live-committed">{committed}</p>}
        {partial && <p className="live-partial">{partial}</p>}
        {!committed && !partial && state === 'idle' && <p className="live-placeholder">—</p>}
      </div>
    </div>
  );
}
