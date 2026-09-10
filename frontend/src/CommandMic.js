import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { getToken, wsUrl } from './api';
import { MicPcmStream } from './audioStream';

export default function CommandMic({ language, onCommand, onError }) {
  const { t } = useTranslation();
  const [state, setState] = useState('idle'); // idle | connecting | live
  const [events, setEvents] = useState([]);

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
    wsRef.current?.close();
    cleanup();
    setState('idle');
  };

  const start = async () => {
    setEvents([]);
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
      wsUrl(`/ws/commands?token=${encodeURIComponent(getToken() || '')}&language=${language}`)
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
      } else if (message.type === 'command') {
        setEvents((list) => [
          { kind: 'command', text: message.command, phrase: message.phrase, at: Date.now() },
          ...list,
        ].slice(0, 8));
        onCommand?.(message.command, message.phrase);
      } else if (message.type === 'heard') {
        setEvents((list) =>
          [{ kind: 'heard', text: message.phrase, at: Date.now() }, ...list].slice(0, 8)
        );
      } else if (message.type === 'error') {
        onError(message.error);
        setState('idle');
        cleanup();
      }
    };

    ws.onclose = () => {
      cleanup();
      setState('idle');
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

  const COMMAND_LABELS = {
    new_recording: t('cmd.new'),
    live_mode: t('cmd.live'),
    standard_mode: t('cmd.standard'),
    dashboard: t('cmd.dashboard'),
    history: t('cmd.history'),
    dark_mode: t('cmd.dark'),
    light_mode: t('cmd.light'),
    logout: t('cmd.logout'),
    clear_history: t('cmd.clear'),
    download_word: 'Word',
    download_pdf: 'PDF',
    insights: t('cmd.insights'),
    listen: t('cmd.listen'),
    language_english: 'English',
    language_french: 'Français',
  };

  return (
    <div className="live-panel">
      <p className="live-hint">{t('cmd.hint')}</p>
      <div className="button-row">
        {state === 'idle' ? (
          <button className="record-button" onClick={start}>🎙️ {t('cmd.start')}</button>
        ) : (
          <button className="record-button stop" onClick={stop} disabled={state === 'connecting'}>
            ⏹ {t('cmd.stop')}
          </button>
        )}
      </div>
      {state !== 'idle' && (
        <div className={`recorder-panel ${state === 'connecting' ? 'paused' : ''}`}>
          {state === 'live' && <span className="recording-dot" aria-hidden="true"></span>}
          <span className="recorder-state">
            {state === 'connecting' ? t('live.starting') : t('cmd.listening')}
          </span>
        </div>
      )}
      <ul className="command-list">
        {['nouvel enregistrement', 'mode sombre / clair', 'tableau de bord', 'télécharger word',
          'résumé', 'déconnexion', 'new recording', 'download pdf'].map((example) => (
          <li key={example} className="command-example">{example}</li>
        ))}
      </ul>
      {events.length > 0 && (
        <div className="command-events" aria-live="polite">
          {events.map((event, index) => (
            <div key={`${event.at}-${index}`} className={`command-event ${event.kind}`}>
              {event.kind === 'command' ? '✅' : '🎙️'} {COMMAND_LABELS[event.text] || event.text}
              {event.phrase ? <em> — « {event.phrase} »</em> : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
