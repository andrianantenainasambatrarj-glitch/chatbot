import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { statsApi, adminStatsApi, adminUsersApi, adminUpdateUserApi } from './api';
import Icon from './components/Icon';

function StatCard({ icon, value, label }) {
  return (
    <div className="stat-card">
      <span className="stat-icon"><Icon name={icon} size={19} /></span>
      <div>
        <div className="stat-value">{value}</div>
        <div className="stat-label">{label}</div>
      </div>
    </div>
  );
}

function QuotaRow({ t, used, quota }) {
  const percent = quota ? Math.min(100, Math.round((used / quota) * 100)) : 0;
  return (
    <div className="dashboard-panel">
      <h3>{t('dashboard.quota')}</h3>
      <div className="progress-track" style={{ height: 10 }}>
        <div className="progress-fill" style={{ width: quota ? `${percent}%` : '100%', opacity: quota ? 1 : 0.35 }} />
      </div>
      <p className="quota-line">
        {quota
          ? t('dashboard.quotaUsed', { used, limit: quota, percent })
          : t('dashboard.quotaUnlimited', { used })}
      </p>
    </div>
  );
}

export default function DashboardView({ user, onError }) {
  const { t } = useTranslation();
  const [stats, setStats] = useState(null);
  const [admin, setAdmin] = useState(null);
  const [adminUsers, setAdminUsers] = useState(null);

  useEffect(() => {
    statsApi().then(setStats).catch((err) => onError(err.message));
    if (user?.role === 'admin' || user?.is_admin) {
      adminStatsApi().then(setAdmin).catch(() => {});
      adminUsersApi().then(setAdminUsers).catch(() => {});
    }
  }, [user, onError]);

  const updateUser = async (id, patch) => {
    try {
      const updated = await adminUpdateUserApi(id, patch);
      setAdminUsers((prev) =>
        prev.map((u) => (u.id === id ? { ...u, ...updated } : u))
      );
    } catch (err) {
      onError(err.message);
    }
  };

  const daily = stats?.daily?.slice(-14) || [];
  const chartMax = Math.max(1, ...daily.map((d) => d.count));
  const engineCount = Object.keys(stats?.by_engine || {}).length;
  const languageCount = Object.keys(stats?.by_language || {}).length;

  return (
    <div className="fade-in">
      <div className="page-head">
        <h2>{t('dashboard.title')}</h2>
        <p>{t('dashboard.subtitle')}</p>
      </div>

      {!stats ? (
        <div className="loader" />
      ) : (
        <>
          <div className="stat-grid">
            <StatCard icon="fileText" value={stats.total_transcriptions} label={t('dashboard.total')} />
            <StatCard icon="clock" value={Math.round(stats.total_minutes)} label={t('dashboard.minutes')} />
            <StatCard icon="cpu" value={engineCount} label={t('dashboard.engines')} />
            <StatCard icon="globe" value={languageCount} label={t('dashboard.languages')} />
          </div>

          <QuotaRow
            t={t}
            used={Math.round(stats.used_minutes_month)}
            quota={stats.quota_minutes}
          />

          <div className="dashboard-panel">
            <h3>{t('dashboard.chart')}</h3>
            {daily.some((d) => d.count > 0) ? (
              <div className="barchart">
                {daily.map((day) => {
                  const date = new Date(day.day);
                  const label = `${date.getDate()}/${date.getMonth() + 1}`;
                  return (
                    <div className="bar-col" key={day.day} title={`${label} — ${day.count}`}>
                      {day.count > 0 && <span className="bar-value">{day.count}</span>}
                      <div
                        className="bar"
                        style={{ height: `${Math.max(day.count ? 4 : 0, (day.count / chartMax) * 110)}px` }}
                      />
                      <span className="bar-label">{label}</span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="small muted">{t('dashboard.noActivity')}</p>
            )}
          </div>
        </>
      )}

      {(user?.role === 'admin' || user?.is_admin) && (
        <div className="dashboard-panel">
          <h3>{t('dashboard.admin')}</h3>
          {!admin || !adminUsers ? (
            <div className="loader" />
          ) : (
            <>
              <div className="stat-grid" style={{ marginBottom: 18 }}>
                <StatCard icon="users" value={admin.users} label={t('dashboard.totalUsers')} />
                <StatCard icon="fileText" value={admin.transcriptions} label={t('dashboard.totalTrans')} />
                <StatCard icon="refresh" value={admin.jobs_pending} label={t('dashboard.jobsPending')} />
              </div>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>{t('dashboard.emailCol')}</th>
                      <th>{t('dashboard.usageCol')}</th>
                      <th>{t('dashboard.quotaCol')}</th>
                      <th>{t('dashboard.roleCol')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {adminUsers.map((u) => (
                      <tr key={u.id}>
                        <td>{u.email}</td>
                        <td>
                          {u.total_transcriptions} · {Math.round(u.total_minutes || 0)} min
                        </td>
                        <td>
                          <input
                            type="number"
                            min="0"
                            defaultValue={u.monthly_quota_minutes ?? 0}
                            onBlur={(e) => {
                              const value = Number(e.target.value) || 0;
                              if (value !== (u.monthly_quota_minutes ?? 0)) {
                                updateUser(u.id, { monthly_quota_minutes: value });
                              }
                            }}
                          />
                        </td>
                        <td>
                          <select
                            value={u.role}
                            onChange={(e) => updateUser(u.id, { role: e.target.value })}
                          >
                            <option value="user">{t('dashboard.roleUser')}</option>
                            <option value="admin">{t('dashboard.roleAdmin')}</option>
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
