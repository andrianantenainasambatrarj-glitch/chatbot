import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { authApi, setToken } from './api';
import Icon from './components/Icon';
import Waveform from './components/Waveform';

export default function AuthScreen({ onAuthed }) {
  const { t } = useTranslation();
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      const action = mode === 'login' ? authApi.login : authApi.register;
      const data = await action(email.trim().toLowerCase(), password);
      setToken(data.token);
      onAuthed(data.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-shell">
      <aside className="auth-aside">
        <div className="brand">
          <span className="brand-mark"><Icon name="waveform" size={21} /></span>
          <span>
            <span className="brand-name">Chatbot Vocal</span>
            <span className="brand-tag">Transcription privée</span>
          </span>
        </div>

        <div className="auth-quote">
          <h2>{t('auth.brandTitle')}</h2>
          <p>{t('auth.brandText')}</p>
        </div>

        <div className="auth-wave">
          <Waveform active={false} height={120} />
        </div>
      </aside>

      <main className="auth-main">
        <div className="auth-card fade-in">
          <h2>{mode === 'login' ? t('auth.loginTitle') : t('auth.registerTitle')}</h2>
          <p className="auth-subtitle">{t('auth.welcome')}</p>

          <form className="auth-form" onSubmit={submit}>
            <label className="field">
              <span>{t('auth.email')}</span>
              <input
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="vous@exemple.com"
              />
            </label>

            <label className="field">
              <span>{t('auth.password')}</span>
              <input
                type="password"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
              />
            </label>

            {error && (
              <div className="alert" role="alert">
                <Icon name="x" size={16} />
                <span>{error}</span>
              </div>
            )}

            <button className="btn btn-primary" type="submit" disabled={busy}>
              {busy ? <span className="loader sm" /> : mode === 'login' ? t('auth.login') : t('auth.register')}
              {!busy && <Icon name="arrowRight" size={17} />}
            </button>

            <button
              type="button"
              className="auth-switch"
              onClick={() => {
                setError('');
                setMode(mode === 'login' ? 'register' : 'login');
              }}
            >
              {mode === 'login' ? t('auth.switchToRegister') : t('auth.switchToLogin')}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}
