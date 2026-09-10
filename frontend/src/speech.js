// Synthèse vocale côté navigateur (Web Speech API), sans dépendance serveur.

let currentUtterance = null;

export function isSpeechSupported() {
  return typeof window !== 'undefined' && 'speechSynthesis' in window;
}

export function stopSpeaking() {
  if (isSpeechSupported() && currentUtterance) {
    window.speechSynthesis.cancel();
    currentUtterance = null;
  }
}

export function speak(text, language = 'fr', { onEnd } = {}) {
  if (!isSpeechSupported() || !text) return false;
  window.speechSynthesis.cancel();

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = language === 'en' ? 'en-US' : 'fr-FR';
  utterance.rate = 1;

  // Préfère une voix dans la bonne langue si disponible
  const voices = window.speechSynthesis.getVoices();
  const match = voices.find((voice) => voice.lang?.startsWith(language === 'en' ? 'en' : 'fr'));
  if (match) utterance.voice = match;

  utterance.onend = () => {
    currentUtterance = null;
    onEnd?.();
  };
  utterance.onerror = () => {
    currentUtterance = null;
    onEnd?.();
  };
  currentUtterance = utterance;
  window.speechSynthesis.speak(utterance);
  return true;
}
