import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { apiFetch } from './api';

function BarChart({ daily }) {
  const max = Math.max(1, ...daily.map((day) => day.count));
  if (!daily.length) return <p className="muted">—</p>;
  return (
    <div className="barchart" role="img" aria-label="Transcriptions par jour">
      {daily.map((day) => (
        <div key={day.day} className="bar-col" title={`${day.day}: ${day.count}`}>
          <div className="bar" style={{ height: `${Math.round((day.count / max) * 100)}%` }}>
            <span className="bar-value">{day.count}</span>
          </div>
          <span className="bar-label">{day.day.slice(5)}</span>
        </div>
      ))}
    </div>
  );
}

export default function DashboardView({ user, onReloadUser }) {
  const { t } = useTranslation();
  const [stats, setStats] = useState(null);
  const [adminUsers, setAdminUsers] = useState(null);
  const [totals, setTotals] = useState(null);
  const [error, setError] = useState('');

  const isAdmin = user?.role === 'admin';

  useEffect(() => {
    apiFetch('/api/stats').then(setStats).catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!isAdmin) return undefined;
    apiFetch('/api/admin/users').then(setAdminUsers).catch((err) => setError(err.message));
    apiFetch('/api/admin/stats').then(setTotals).catch(() => {});
    return undefined;
  }, [isAdmin]);

  const changeQuota = async (userId, minutes) => {
    try {
      await apiFetch(`/api/admin/users/${userId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ monthly_quota_minutes: minutes ? Number(minutes) : null }),
      });
      const refreshed = await apiFetch('/api/admin/users');
      setAdminUsers(refreshed);
    } catch (err) {
      setError(err.message);
    }
  };

  const changeRole = async (userId, role) => {
    await apiFetch(`/api/admin/users/${userId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role }),
    });
    setAdminUsers(await apiFetch('/api/admin/users'));
  };

  if (!stats) return <div className="centered-loader"><div className="loader"></div></div>;

  const quotaPercent = stats.quota_minutes
    ? Math.min(100, Math.round((stats.used_minutes_month / stats.quota_minutes) * 100))
    : null;

  return (
    <section className="dashboard">
      <h2>{t('dashboard.title')}</h2>
      {error && <div className="error-message">⚠️ {error}</div>}

      <div className="stat-cards">
        <div className="stat-card">
          <span className="stat-value">{stats.total_transcriptions}</span>
          <span className="stat-label">{t('dashboard.transcriptions')}</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{stats.total_minutes}</span>
          <span className="stat-label">{t('dashboard.minutes')}</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">
            {Object.keys(stats.by_engine).map((engine) => engine).join(', ') || '—'}
          </span>
          <span className="stat-label">{t('dashboard.engines')}</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">
            {Object.keys(stats.by_language).map((language) => language.toUpperCase()).join(', ') || '—'}
          </span>
          <span className="stat-label">{t('dashboard.languages')}</span>
        </div>
      </div>

      <div className="dashboard-panel">
        <h3>{t('dashboard.daily')}</h3>
        <BarChart daily={stats.daily} />
      </div>

      {quotaPercent !== null && (
        <div className="dashboard-panel">
          <h3>{t('dashboard.quota')}</h3>
          <div className="progress-bar">
            <div
              className={`progress-fill ${quotaPercent > 90 ? 'danger' : ''}`}
              style={{ width: `${quotaPercent}%` }}
            ></div>
          </div>
          <p>{stats.used_minutes_month} / {stats.quota_minutes} {t('dashboard.minutesUsedMonth')}</p>
        </div>
      )}

      {isAdmin && (
        <div className="dashboard-panel admin-panel">
          <h3>🛠️ {t('dashboard.admin')}</h3>
          {totals && (
            <p className="muted">
              {totals.users} {t('dashboard.usersUnit')} · {totals.transcriptions}{' '}
              {t('dashboard.transcriptionsUnit')}
            </p>
          )}
          <div className="table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>E-mail</th>
                  <th>Rôle</th>
                  <th>{t('dashboard.monthUsage')}</th>
                  <th>{t('dashboard.quotaCol')}</th>
                </tr>
              </thead>
              <tbody>
                {(adminUsers || []).map((row) => (
                  <tr key={row.id}>
                    <td>{row.email}</td>
                    <td>
                      <select
                        value={row.role}
                        onChange={(event) => changeRole(row.id, event.target.value)}
                      >
                        <option value="user">user</option>
                        <option value="admin">admin</option>
                      </select>
                    </td>
                    <td>{row.used_minutes_month} min</td>
                    <td>
                      <input
                        type="number"
                        min="0"
                        defaultValue={row.monthly_quota_minutes || 0}
                        onBlur={(event) => changeQuota(row.id, event.target.value)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
