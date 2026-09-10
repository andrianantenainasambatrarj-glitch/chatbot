import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { getToken, wsUrl } from './api';
import { MicPcmStream } from './audioStream';
import Icon from './components/Icon';
import Waveform from './components/Waveform';

const COMMAND_NAMES = [
  'new_recording', 'live_mode', 'standard_mode', 'dashboard', 'history',
  'dark_mode', 'light_mode', 'logout', 'clear_history', 'download_word',
  'download_pdf', 'insights', 'listen', 'language_english', 'language_french',
];

export default function CommandMic({ language = 'fr', onCommand, onError, disabled }) {
  const { t } = useTranslation();
  const [listening, setListening] = useState(false);
  const [events, setEvents] = useState([]);
  const [analyser, setAnalyser] = useState(null);
  const wsRef = useRef(null);
  const micRef = useRef(null);

  useEffect(() => () => {
    wsRef.current?.close();
    micRef.current?.stop();
  }, []);

  const pushEvent = (event) =>
    setEvents((prev) => [...prev.slice(-6), event]);

  const stop = () => {
    micRef.current?.stop();
    micRef.current = null;
    setAnalyser(null);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.close();
    }
    setListening(false);
  };

  const start = async () => {
    setEvents([]);
    const ws = new WebSocket(
      wsUrl(`/ws/commands?token=${encodeURIComponent(getToken() || '')}&language=${language}`)
    );
    ws.binaryType = 'arraybuffer';
    wsRef.current = ws;

    const mic = new MicPcmStream(
      () => {},
      (err) => {
        stop();
        if (err.name === 'NotAllowedError') onError(t('micDenied'));
        else if (err.name === 'NotFoundError') onError(t('micNotFound'));
        else onError(err.message);
      }
    );
    micRef.current = mic;

    ws.onmessage = (event) => {
      let message;
      try {
        message = JSON.parse(event.data);
      } catch {
        return;
      }
      if (message.type === 'ready') {
        setListening(true);
      } else if (message.type === 'heard' && message.phrase) {
        pushEvent({ kind: 'heard', text: message.phrase });
      } else if (message.type === 'command') {
        pushEvent({ kind: 'command', text: message.phrase, command: message.command });
        onCommand(message.command);
        setTimeout(stop, 700);
      } else if (message.type === 'error') {
        onError(message.error);
        stop();
      }
    };

    ws.onclose = () => {
      mic.stop();
      micRef.current = null;
      setAnalyser(null);
      setListening(false);
    };

    ws.onopen = async () => {
      mic.attachWebSocket(ws);
      try {
        await mic.start();
        setAnalyser(mic.analyser);
      } catch {
        ws.close();
      }
    };
  };

  return (
    <div className="card live-panel fade-in">
      <div className="waveform-frame">
        <Waveform analyser={analyser} active={listening} height={72} />
      </div>

      <p className="hint">{t('commands.hint')}</p>

      <div className="record-stage">
        <button
          className={`record-circle ${listening ? 'recording' : ''}`}
          onClick={listening ? stop : start}
          disabled={disabled}
          aria-label={listening ? t('commands.stop') : t('commands.start')}
        >
          <Icon name={listening ? 'stop' : 'command'} size={listening ? 26 : 29} />
        </button>
        <span className="record-caption">
          {listening ? t('commands.listening') : t('commands.start')}
        </span>
      </div>

      <ul className="command-examples">
        {COMMAND_NAMES.map((name) => (
          <li key={name}>{t(`commands.examples.${name}`)}</li>
        ))}
      </ul>

      {events.length > 0 && (
        <div className="command-events" aria-live="polite">
          {events.map((event, index) =>
            event.kind === 'command' ? (
              <div key={index} className="command-event command">
                {t('commands.executed', { command: t(`commands.examples.${event.command}`) })}
              </div>
            ) : (
              <div key={index} className="command-event heard">
                {event.text}
              </div>
            )
          )}
        </div>
      )}
    </div>
  );
}
