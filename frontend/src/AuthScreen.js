import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { authApi, setToken } from './api';

export default function AuthScreen({ onAuthed }) {
  const { t } = useTranslation();
  const [mode, setMode] = useState('login'); // 'login' | 'register'
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
      if (err.status === 401) setError(t('auth.login') + ' : ' + err.message);
      else setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-screen">
      <form className="auth-card" onSubmit={submit}>
        <h2>{mode === 'login' ? t('auth.loginTitle') : t('auth.registerTitle')}</h2>
        <p className="auth-welcome">{t('auth.welcome')}</p>

        <label className="field">
          <span>{t('auth.email')}</span>
          <input
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
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
          />
        </label>

        {error && (
          <div className="error-message" role="alert">
            ⚠️ {error}
          </div>
        )}

        <button className="record-button auth-submit" type="submit" disabled={busy}>
          {mode === 'login' ? t('auth.login') : t('auth.register')}
        </button>

        <button
          type="button"
          className="link-button"
          onClick={() => {
            setError('');
            setMode(mode === 'login' ? 'register' : 'login');
          }}
        >
          {mode === 'login' ? t('auth.switchToRegister') : t('auth.switchToLogin')}
        </button>
      </form>
    </div>
  );
}
