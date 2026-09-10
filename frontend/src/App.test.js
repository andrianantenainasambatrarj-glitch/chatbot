import { render, screen } from '@testing-library/react';
import App from './App';

test('affiche le titre et les contrôles d’enregistrement', () => {
  render(<App />);
  expect(
    screen.getByRole('heading', { name: /chatbot vocal/i })
  ).toBeInTheDocument();
  expect(
    screen.getByRole('button', { name: /enregistrer/i })
  ).toBeInTheDocument();
});
