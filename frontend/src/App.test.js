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
