import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';

beforeEach(() => {
  localStorage.clear();
});

test('affiche l’écran de connexion pour un visiteur anonyme', async () => {
  render(<App />);
  expect(
    await screen.findByRole('heading', { name: /connexion|sign in/i })
  ).toBeInTheDocument();
  expect(screen.getByLabelText(/e-mail|email/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/mot de passe|password/i)).toBeInTheDocument();
});

test('bascule entre connexion et inscription', async () => {
  render(<App />);
  await userEvent.click(await screen.findByRole('button', { name: /inscrivez|sign up/i }));
  expect(
    screen.getByRole('heading', { name: /créer un compte|create an account/i })
  ).toBeInTheDocument();
});

test('affiche le studio pour un utilisateur connecté', async () => {
  const jsonOk = (data) =>
    Promise.resolve({
      ok: true,
      status: 200,
      headers: new Headers(),
      json: () => Promise.resolve(data),
    });
  global.fetch = jest.fn((url) => {
    const target = String(url);
    if (target.includes('/api/auth/me')) {
      // /me renvoie l'utilisateur à plat (pas de clé "user")
      return jsonOk({ id: 'u1', email: 'test@example.com', role: 'user' });
    }
    if (target.includes('/api/transcriptions')) return jsonOk([]);
    if (target.includes('/api/stats')) {
      return jsonOk({
        total_transcriptions: 0, total_minutes: 0, used_minutes_month: 0,
        quota_minutes: null, by_engine: {}, by_language: {}, daily: [],
      });
    }
    return jsonOk({});
  });
  localStorage.setItem('cv_token', 'jeton-de-test');

  render(<App />);

  expect(
    await screen.findByRole('button', { name: /enregistrer|record/i })
  ).toBeInTheDocument();

  // La navigation latérale mène au tableau de bord
  await userEvent.click(await screen.findByRole('button', { name: /tableau de bord|dashboard/i }));
  expect(
    await screen.findByRole('heading', { level: 2, name: /tableau de bord|dashboard/i })
  ).toBeInTheDocument();

  // Naviguer d'onglet en onglet ne doit jamais ramener à l'écran de connexion
  await userEvent.click(screen.getByRole('button', { name: /historique|history/i }));
  await userEvent.click(screen.getByRole('button', { name: /en direct|live/i }));
  await userEvent.click(screen.getByRole('button', { name: /^studio$/i }));
  expect(screen.queryByLabelText(/mot de passe|password/i)).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: /enregistrer|record/i })).toBeInTheDocument();
});
