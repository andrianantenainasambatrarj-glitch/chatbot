import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  insightsApi, chatApi, shareApi,
  emailApi, webhookApi,
} from './api';
import Icon from './components/Icon';

function Accordion({ icon, title, open, onToggle, children }) {
  return (
    <div className={`accordion ${open ? 'open' : ''}`}>
      <button
        type="button"
        className="accordion-toggle"
        onClick={onToggle}
        aria-expanded={open}
      >
        <Icon name={icon} size={18} />
        <span>{title}</span>
        <Icon name="chevronDown" size={16} className="chev" />
      </button>
      {open && <div className="accordion-body">{children}</div>}
    </div>
  );
}

function CopyButton({ text, t }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  };
  return (
    <button className="btn btn-secondary btn-sm" onClick={copy}>
      <Icon name={copied ? 'check' : 'copy'} size={15} />
      {copied ? t('share.copied') : t('share.copy')}
    </button>
  );
}

function PanelMessage({ children }) {
  return <p className="small muted" style={{ marginTop: 8 }}>{children}</p>;
}

function sentimentKey(rawSentiment) {
  const label = (
    typeof rawSentiment === 'string' ? rawSentiment : rawSentiment?.label || ''
  ).toLowerCase();
  if (label.includes('pos')) return 'positive';
  if (label.includes('neg') || label.includes('nég')) return 'negative';
  return 'neutral';
}

export default function TranscriptionActions({
  item,
  insights, setInsights,
  chatMessages, setChatMessages,
  openPanel, setOpenPanel,
  notify, onError,
}) {
  const { t } = useTranslation();
  const [loadingInsights, setLoadingInsights] = useState(false);

  const [question, setQuestion] = useState('');
  const [chatBusy, setChatBusy] = useState(false);

  const [email, setEmail] = useState('');
  const [webhookUrl, setWebhookUrl] = useState('');
  const [shareToken, setShareToken] = useState(null);
  const [sendingEmail, setSendingEmail] = useState(false);
  const [sendingWebhook, setSendingWebhook] = useState(false);

  const sendQuestion = async () => {
    const q = question.trim();
    if (!q) return;
    setChatBusy(true);
    const history = [...chatMessages, { role: 'user', content: q }];
    setChatMessages(history);
    setQuestion('');
    try {
      const answer = await chatApi(item.id, q, chatMessages);
      setChatMessages([...history, { role: 'assistant', content: answer }]);
    } catch (err) {
      onError(err.message);
    } finally {
      setChatBusy(false);
    }
  };

  const askInsights = async () => {
    setLoadingInsights(true);
    try {
      setInsights(await insightsApi(item.id));
    } catch (err) {
      onError(err.message);
    } finally {
      setLoadingInsights(false);
    }
  };

  const createShare = async () => {
    try {
      const data = await shareApi(item.id);
      setShareToken(data.token);
      notify(t('share.created'));
    } catch (err) {
      onError(err.message);
    }
  };

  const sendEmail = async () => {
    if (!email.trim() || !email.includes('@')) {
      onError(t('share.emailRequired'));
      return;
    }
    setSendingEmail(true);
    try {
      await emailApi(item.id, email.trim());
      notify(t('share.emailSent'));
      setEmail('');
    } catch (err) {
      onError(err.message);
    } finally {
      setSendingEmail(false);
    }
  };

  const sendWebhook = async () => {
    if (!/^https?:\/\//.test(webhookUrl.trim())) {
      onError(t('share.webhookInvalid'));
      return;
    }
    setSendingWebhook(true);
    try {
      await webhookApi(item.id, webhookUrl.trim());
      notify(t('share.webhookSent'));
      setWebhookUrl('');
    } catch (err) {
      onError(err.message);
    } finally {
      setSendingWebhook(false);
    }
  };

  const shareUrl = shareToken
    ? `${window.location.origin}/shared/${shareToken}`
    : '';

  return (
    <div>
      <Accordion
        icon="sparkles"
        title={t('insights.title')}
        open={openPanel === 'insights'}
        onToggle={() => setOpenPanel(openPanel === 'insights' ? null : 'insights')}
      >
        {!insights && (
          <button className="btn btn-primary btn-sm" onClick={askInsights} disabled={loadingInsights}>
            {loadingInsights ? <span className="loader sm" /> : <Icon name="sparkles" size={15} />}
            {t('insights.generate')}
          </button>
        )}
        {insights && (
          <>
            <h4>{t('insights.summary')}</h4>
            <p className="small">{insights.summary}</p>

            <h4>{t('insights.tasks')}</h4>
            {insights.action_items?.length ? (
              <ul className="task-list">
                {insights.action_items.map((task, i) => <li key={i}>{task}</li>)}
              </ul>
            ) : <PanelMessage>{t('insights.noTasks')}</PanelMessage>}

            <h4>{t('insights.keywords')}</h4>
            <div className="keyword-cloud">
              {(insights.keywords || []).map((kw, i) => (
                <span key={i} className={`keyword-chip${i < 3 ? ' accent' : ''}`}>{kw}</span>
              ))}
            </div>

            <h4>{t('insights.sentiment')}</h4>
            <p className="sentiment">
              <Icon
                name={sentimentKey(insights.sentiment) === 'positive'
                  ? 'check'
                  : sentimentKey(insights.sentiment) === 'negative' ? 'x' : 'clock'}
                size={16}
              />
              {t(`insights.sentiments.${sentimentKey(insights.sentiment)}`)}
            </p>
          </>
        )}
      </Accordion>

      <Accordion
        icon="chat"
        title={t('chat.title')}
        open={openPanel === 'chat'}
        onToggle={() => setOpenPanel(openPanel === 'chat' ? null : 'chat')}
      >
        <div className="chat-messages">
          {chatMessages.length === 0 && <PanelMessage>{t('chat.placeholder')}</PanelMessage>}
          {chatMessages.map((msg, i) => (
            <div key={i} className={`chat-msg ${msg.role === 'user' ? 'user' : 'assistant'}`}>
              <Icon name={msg.role === 'user' ? 'mic' : 'cpu'} size={15} />
              <span>{msg.content}</span>
            </div>
          ))}
        </div>
        <div className="chat-input">
          <input
            type="text"
            value={question}
            placeholder={t('chat.askPlaceholder')}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') sendQuestion(); }}
          />
          <button className="btn btn-primary btn-sm" onClick={sendQuestion} disabled={chatBusy}>
            {chatBusy ? <span className="loader sm" /> : <Icon name="send" size={15} />}
          </button>
        </div>
      </Accordion>

      <Accordion
        icon="share"
        title={t('share.title')}
        open={openPanel === 'share'}
        onToggle={() => setOpenPanel(openPanel === 'share' ? null : 'share')}
      >
        <h4>{t('share.linkTitle')}</h4>
        {!shareToken ? (
          <button className="btn btn-primary btn-sm" onClick={createShare}>
            <Icon name="link" size={15} /> {t('share.create')}
          </button>
        ) : (
          <div className="share-row">
            <code>{shareUrl}</code>
            <CopyButton text={shareUrl} t={t} />
          </div>
        )}

        <h4>{t('share.emailTitle')}</h4>
        <div className="inline-form">
          <input
            type="email"
            placeholder={t('share.emailPlaceholder')}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <button className="btn btn-secondary btn-sm" onClick={sendEmail} disabled={sendingEmail}>
            {sendingEmail ? <span className="loader sm" /> : <Icon name="mail" size={15} />}
            {t('share.sendEmail')}
          </button>
        </div>
        <PanelMessage>{t('share.emailHint')}</PanelMessage>

        <h4>{t('share.webhookTitle')}</h4>
        <div className="inline-form">
          <input
            type="url"
            placeholder="https://exemple.com/webhook"
            value={webhookUrl}
            onChange={(e) => setWebhookUrl(e.target.value)}
          />
          <button className="btn btn-secondary btn-sm" onClick={sendWebhook} disabled={sendingWebhook}>
            {sendingWebhook ? <span className="loader sm" /> : <Icon name="webhook" size={15} />}
            {t('share.sendWebhook')}
          </button>
        </div>
      </Accordion>
    </div>
  );
}
