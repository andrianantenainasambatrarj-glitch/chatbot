import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { apiFetch } from './api';
import { isSpeechSupported, speak, stopSpeaking } from './speech';

function Accordion({ icon, title, children, open, onToggle }) {
  return (
    <div className={`action-block ${open ? 'open' : ''}`}>
      <button type="button" className="action-toggle" onClick={onToggle}>
        {icon} {title} <span className="chevron">{open ? '▾' : '▸'}</span>
      </button>
      {open && <div className="action-body">{children}</div>}
    </div>
  );
}

export default function TranscriptionActions({ transcription, language, onChanged }) {
  const { t } = useTranslation();
  const [openPanel, setOpenPanel] = useState('');
  const [insights, setInsights] = useState(null);
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState('');
  const [shareLinks, setShareLinks] = useState([]);
  const [copied, setCopied] = useState('');
  const [email, setEmail] = useState('');
  const [webhookUrl, setWebhookUrl] = useState('');
  const [feedback, setFeedback] = useState('');
  const [speaking, setSpeaking] = useState(false);

  const toggle = (name) => setOpenPanel((current) => (current === name ? '' : name));

  const showFeedback = (message) => {
    setFeedback(message);
    setTimeout(() => setFeedback(''), 4000);
  };

  const loadInsights = async () => {
    if (openPanel === 'insights') {
      toggle('insights');
      return;
    }
    setOpenPanel('insights');
    if (!insights || insights._id !== transcription.id) {
      setBusy(true);
      try {
        const data = await apiFetch(`/api/transcriptions/${transcription.id}/insights`, {
          method: 'POST',
        });
        setInsights({ ...data, _id: transcription.id });
      } catch (err) {
        showFeedback(err.message);
      } finally {
        setBusy(false);
      }
    }
  };

  const askQuestion = async (event) => {
    event.preventDefault();
    if (!question.trim()) return;
    const newMessages = [...messages, { role: 'user', content: question.trim() }];
    setMessages(newMessages);
    setQuestion('');
    try {
      const data = await apiFetch(`/api/transcriptions/${transcription.id}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: newMessages[newMessages.length - 1].content,
                               history: newMessages.slice(0, -1) }),
      });
      setMessages([...newMessages, { role: 'assistant', content: data.reply }]);
    } catch (err) {
      setMessages([...newMessages, { role: 'assistant', content: `⚠️ ${err.message}` }]);
    }
  };

  const createShare = async () => {
    try {
      const link = await apiFetch(`/api/transcriptions/${transcription.id}/share`, {
        method: 'POST',
      });
      setShareLinks((links) => [link, ...links]);
    } catch (err) {
      showFeedback(err.message);
    }
  };

  const revokeShare = async (token) => {
    await apiFetch(`/api/transcriptions/${transcription.id}/share/${token}`, { method: 'DELETE' });
    setShareLinks((links) => links.filter((link) => link.token !== token));
  };

  const copyLink = async (path) => {
    const url = `${window.location.origin}${path}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(path);
      setTimeout(() => setCopied(''), 2000);
    } catch {
      showFeedback(url);
    }
  };

  const sendEmail = async (event) => {
    event.preventDefault();
    try {
      await apiFetch(`/api/transcriptions/${transcription.id}/email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      showFeedback(`✅ ${t('actions.emailSent')}`);
      setEmail('');
    } catch (err) {
      showFeedback(`⚠️ ${err.message}`);
    }
  };

  const sendWebhook = async (event) => {
    event.preventDefault();
    try {
      await apiFetch(`/api/transcriptions/${transcription.id}/webhook`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: webhookUrl }),
      });
      showFeedback(`✅ ${t('actions.webhookSent')}`);
      setWebhookUrl('');
    } catch (err) {
      showFeedback(`⚠️ ${err.message}`);
    }
  };

  const toggleSpeech = () => {
    if (speaking) {
      stopSpeaking();
      setSpeaking(false);
      return;
    }
    if (speak(transcription.text, language, { onEnd: () => setSpeaking(false) })) {
      setSpeaking(true);
    }
  };

  const sentimentLabel = insights?.sentiment
    ? `${insights.sentiment.label} (${insights.sentiment.score})`
    : '';

  return (
    <div className="actions">
      {feedback && <div className="feedback-toast" role="status">{feedback}</div>}
      <div className="action-row">
        <button type="button" className="secondary-button small" onClick={loadInsights}>
          🧠 {t('actions.insights')}
        </button>
        <button
          type="button"
          className="secondary-button small"
          onClick={() => toggle('chat')}
        >
          💬 {t('actions.chat')}
        </button>
        {isSpeechSupported() && (
          <button type="button" className="secondary-button small" onClick={toggleSpeech}>
            {speaking ? `⏹️ ${t('actions.stopListening')}` : `🔊 ${t('actions.listen')}`}
          </button>
        )}
        <button type="button" className="secondary-button small" onClick={() => toggle('share')}>
          🔗 {t('actions.share')}
        </button>
        <button type="button" className="secondary-button small" onClick={() => toggle('email')}>
          ✉️ {t('actions.email')}
        </button>
        <button type="button" className="secondary-button small" onClick={() => toggle('webhook')}>
          🔔 {t('actions.webhook')}
        </button>
      </div>

      {busy && <div className="loader small"></div>}

      <Accordion icon="🧠" title={t('actions.insights')} open={openPanel === 'insights'}
        onToggle={loadInsights}>
        {insights && insights._id === transcription.id && (
          <div className="insights">
            <h4>{t('actions.summary')} {insights.engine === 'llm' ? '· IA' : '· hors-ligne'}</h4>
            <p>{insights.summary}</p>

            <h4>{t('actions.tasks')}</h4>
            {insights.action_items.length === 0 ? (
              <p className="muted">{t('actions.noTasks')}</p>
            ) : (
              <ul className="task-list">
                {insights.action_items.map((item, index) => (
                  <li key={index}>☐ {item}</li>
                ))}
              </ul>
            )}

            <h4>{t('actions.keywords')}</h4>
            <div className="keyword-cloud">
              {insights.keywords.map((word) => (
                <span key={word} className="keyword-chip">{word}</span>
              ))}
            </div>

            <h4>{t('actions.sentiment')}</h4>
            <p>{sentimentLabel}</p>
          </div>
        )}
      </Accordion>

      <Accordion icon="💬" title={t('actions.chat')} open={openPanel === 'chat'}
        onToggle={() => toggle('chat')}>
        <div className="chat-panel">
          <div className="chat-messages">
            {messages.length === 0 && <p className="muted">{t('actions.chatHint')}</p>}
            {messages.map((message, index) => (
              <div key={index} className={`chat-msg ${message.role}`}>
                <button
                  type="button"
                  className="icon-button"
                  title={t('actions.listen')}
                  onClick={() => speak(message.content, language)}
                >
                  🔊
                </button>
                <span>{message.content}</span>
              </div>
            ))}
          </div>
          <form className="chat-input" onSubmit={askQuestion}>
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder={t('actions.askPlaceholder')}
            />
            <button className="record-button small" type="submit">➤</button>
          </form>
        </div>
      </Accordion>

      <Accordion icon="🔗" title={t('actions.share')} open={openPanel === 'share'}
        onToggle={() => toggle('share')}>
        <button type="button" className="secondary-button" onClick={createShare}>
          {t('actions.createLink')}
        </button>
        {shareLinks.map((link) => (
          <div key={link.token} className="share-link-row">
            <code>{window.location.origin}{link.url}</code>
            <button type="button" className="link-button" onClick={() => copyLink(link.url)}>
              {copied === link.url ? t('actions.copied') : t('actions.copy')}
            </button>
            <button type="button" className="icon-button" onClick={() => revokeShare(link.token)}>
              🗑️
            </button>
          </div>
        ))}
        <p className="muted small-text">{t('actions.shareHint')}</p>
      </Accordion>

      <Accordion icon="✉️" title={t('actions.email')} open={openPanel === 'email'}
        onToggle={() => toggle('email')}>
        <form className="inline-form" onSubmit={sendEmail}>
          <input
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="destinataire@exemple.com"
          />
          <button className="record-button small" type="submit">{t('actions.send')}</button>
        </form>
        <p className="muted small-text">{t('actions.emailHint')}</p>
      </Accordion>

      <Accordion icon="🔔" title={t('actions.webhook')} open={openPanel === 'webhook'}
        onToggle={() => toggle('webhook')}>
        <form className="inline-form" onSubmit={sendWebhook}>
          <input
            type="url"
            required
            value={webhookUrl}
            onChange={(event) => setWebhookUrl(event.target.value)}
            placeholder="https://n8n.exemple.com/webhook/..."
          />
          <button className="record-button small" type="submit">{t('actions.send')}</button>
        </form>
        <p className="muted small-text">{t('actions.webhookHint')}</p>
      </Accordion>
    </div>
  );
}
