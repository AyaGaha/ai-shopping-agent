import { lazy, Suspense, useCallback, useEffect, useReducer, useRef, useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import {
  Activity as ActivityIcon, AlertTriangle, Check, CheckCheck, ChevronDown, ChevronLeft,
  ChevronRight, Copy, Ellipsis, FileText, Languages, Menu, Moon, Plus, Search, Send, ShieldAlert,
  ShoppingBag, Sparkles, Sun, X, ArrowUp, type LucideIcon,
} from 'lucide-react';
import { api, ApiError } from './api/client';
import type { ChatResponse, Conversation, Message, Product, TraceEntry } from './api/types';
import { formatMoney } from './lib/format';
import { copy as dictionary } from './lib/i18n';
import { readStorage, writeStorage, type Persisted, type Settings } from './lib/storage';

const Markdown = lazy(() => import('./components/Markdown'));
const Inspector = lazy(() => import('./features/inspector/Inspector'));
const stateInit = readStorage();
type State = Persisted & { error: ApiError | null; pending: boolean };
type Action =
  | { type: 'sync'; value: Partial<State> }
  | { type: 'conversation'; value: Conversation; active?: boolean }
  | { type: 'active'; id: string | null }
  | { type: 'settings'; value: Partial<Settings> }
  | { type: 'draft'; id: string; value: string }
  | { type: 'pending'; value: boolean }
  | { type: 'error'; value: ApiError | null }
  | { type: 'clear' };
function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'sync': return { ...state, ...action.value };
    case 'conversation': {
      const conversations = [action.value, ...state.conversations.filter((c) => c.localId !== action.value.localId)].sort((a, b) => b.updatedAt - a.updatedAt);
      return { ...state, conversations, activeLocalId: action.active ? action.value.localId : state.activeLocalId };
    }
    case 'active': return { ...state, activeLocalId: action.id, error: null };
    case 'settings': return { ...state, settings: { ...state.settings, ...action.value } };
    case 'draft': return { ...state, drafts: { ...state.drafts, [action.id]: action.value } };
    case 'pending': return { ...state, pending: action.value };
    case 'error': return { ...state, error: action.value };
    case 'clear': return { ...state, conversations: [], activeLocalId: null, drafts: {}, error: null };
  }
}
const initialState: State = { ...stateInit, error: null, pending: false };
const newConversation = (): Conversation => ({ localId: crypto.randomUUID(), title: 'Nouvelle conversation', updatedAt: Date.now(), messages: [] });
const iconMap: Record<string, LucideIcon> = { search_product: Search, propose_order: ShoppingBag, create_order: ShoppingBag, confirm_order: CheckCheck, cancel_order: X };
function getObject(value: unknown): Record<string, unknown> { return value && typeof value === 'object' ? value as Record<string, unknown> : {}; }
function getProposal(trace?: TraceEntry[]) {
  for (const item of [...(trace ?? [])].reverse()) {
    const result = getObject(item.result);
    if (item.tool_called === 'propose_order' && (result.status === 'proposal_ready' || result.product_name)) return result;
  }
  return null;
}
function getConfirmed(trace?: TraceEntry[]) {
  for (const item of [...(trace ?? [])].reverse()) {
    const result = getObject(item.result);
    if ((item.tool_called === 'confirm_order' || item.tool_called === 'create_order') && !result.error && Object.keys(result).length) return result;
  }
  return null;
}
function isBlocked(message: Message) {
  return message.content.startsWith('Je ne peux pas traiter une demande qui tente de modifier les règles de sécurité');
}
function timeLabel(timestamp: number, language: 'fr' | 'en') {
  return new Intl.DateTimeFormat(language === 'fr' ? 'fr-TN' : 'en', { hour: '2-digit', minute: '2-digit' }).format(timestamp);
}

export default function App() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [config, setConfig] = useState({ max_message_length: 2000, version: '0.1.0' });
  const [products, setProducts] = useState<Product[]>([]);
  const [inspector, setInspector] = useState<'activity' | 'catalog'>('activity');
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [mobileMenu, setMobileMenu] = useState<'sidebar' | 'inspector' | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [copied, setCopied] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const reducedMotion = useReducedMotion();
  const active = state.conversations.find((conversation) => conversation.localId === state.activeLocalId) ?? null;
  const t = dictionary[state.settings.language];
  const messages = active?.messages ?? [];
  const currentDraft = state.drafts[active?.localId ?? ''] ?? '';

  useEffect(() => {
    writeStorage({ conversations: state.conversations, activeLocalId: state.activeLocalId, drafts: state.drafts, settings: state.settings });
    document.documentElement.lang = state.settings.language;
    document.documentElement.dataset.theme = state.settings.theme;
  }, [state.conversations, state.activeLocalId, state.drafts, state.settings]);
  useEffect(() => {
    void api.config().then(setConfig).catch(() => undefined);
    void api.products().then(setProducts).catch(() => undefined);
  }, []);
  useEffect(() => {
    if (!active?.id || !active.messages.length) return;
    let cancelled = false;
    void api.history(active.id).then((data) => {
      if (cancelled || !Array.isArray(data.messages)) return;
      const restored: Message[] = data.messages.flatMap((raw: unknown, index: number) => {
        const row = getObject(raw);
        if ((row.role !== 'user' && row.role !== 'assistant') || typeof row.content !== 'string') return [];
        return [{ id: `${active.id}-${index}`, role: row.role, content: row.content, status: 'done' as const,
          trace: Array.isArray(row.trace) ? row.trace as TraceEntry[] : [], createdAt: Date.parse(String(row.created_at ?? '')) || Date.now() }];
      });
      if (restored.length) dispatch({ type: 'conversation', value: { ...active, messages: restored } });
    }).catch((error: unknown) => {
      if (cancelled || !(error instanceof ApiError) || error.kind !== 'not-found') return;
      dispatch({ type: 'conversation', value: { ...active, id: undefined, messages: [] } });
      dispatch({ type: 'error', value: new ApiError(404, 'Cette conversation a expiré. Un nouveau chat est prêt.', 'not-found') });
    });
    return () => { cancelled = true; };
  // Hydrate each server conversation once when selected.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active?.localId]);
  useEffect(() => {
    if (!state.pending) { setElapsed(0); return; }
    const started = Date.now(); const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [state.pending]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: reducedMotion ? 'auto' : 'smooth' }); }, [messages.length, state.pending, reducedMotion]);

  const updateConversation = useCallback((conversation: Conversation) => dispatch({ type: 'conversation', value: conversation }), []);
  const freshChat = () => {
    const conversation = newConversation();
    dispatch({ type: 'conversation', value: conversation, active: true });
    dispatch({ type: 'error', value: null });
    setMobileMenu(null);
    window.setTimeout(() => composerRef.current?.focus(), 30);
  };
  const send = async (raw: string, retryMessage?: Message) => {
    const text = raw.trim();
    if (!text || state.pending || text.length > config.max_message_length) return;
    let conversation = active ?? newConversation();
    if (!active) dispatch({ type: 'active', id: conversation.localId });
    const userMessage: Message = retryMessage ?? { id: crypto.randomUUID(), role: 'user', content: text, status: 'pending', createdAt: Date.now() };
    const previousMessages = retryMessage ? conversation.messages.filter((message) => message.id !== retryMessage.id) : conversation.messages;
    const markedPrevious = previousMessages.map((message) => getProposal(message.trace) ? { ...message, stale: true } : message);
    conversation = { ...conversation, title: conversation.messages.length ? conversation.title : text.slice(0, 44), updatedAt: Date.now(), messages: [...markedPrevious, { ...userMessage, status: 'pending', error: undefined }] };
    updateConversation(conversation);
    dispatch({ type: 'draft', id: conversation.localId, value: '' });
    dispatch({ type: 'pending', value: true });
    dispatch({ type: 'error', value: null });
    const controller = new AbortController(); abortRef.current = controller;
    try {
      const response = await api.chat(text, conversation.id, controller.signal) as ChatResponse;
      const updated: Conversation = { ...conversation, id: response.conversation_id, updatedAt: Date.now(), messages: [
        ...conversation.messages.map((message) => message.id === userMessage.id ? { ...message, status: 'done' as const } : message),
        { id: crypto.randomUUID(), role: 'assistant', content: response.final_response, status: 'done', trace: response.trace, createdAt: Date.now(), degraded: response.degraded },
      ] };
      updateConversation(updated);
    } catch (caught) {
      const error = caught instanceof ApiError ? caught : new ApiError(0, 'Connexion impossible. Vérifiez votre réseau.', 'network');
      const failed = { ...conversation, messages: conversation.messages.map((message) => message.id === userMessage.id ? { ...message, status: 'failed' as const, error: error.message } : message) };
      updateConversation(failed);
      dispatch({ type: 'error', value: error });
      if (error.kind === 'not-found') {
        dispatch({ type: 'conversation', value: { ...failed, id: undefined, messages: failed.messages.slice(0, -1) } });
      }
    } finally { abortRef.current = null; dispatch({ type: 'pending', value: false }); composerRef.current?.focus(); }
  };
  const stop = () => abortRef.current?.abort();
  const retry = (message: Message) => { void send(message.content, message); };
  const chooseSuggestion = (text: string) => { dispatch({ type: 'draft', id: active?.localId ?? '', value: text }); void send(text); };
  const setDraft = (value: string) => { if (active) dispatch({ type: 'draft', id: active.localId, value }); else dispatch({ type: 'sync', value: { drafts: { ...state.drafts, '': value } } }); };
  const doCopy = async (id: string, value: string) => { try { await navigator.clipboard.writeText(value); setCopied(id); window.setTimeout(() => setCopied(null), 1400); } catch { dispatch({ type: 'error', value: new ApiError(0, 'Impossible de copier dans le presse-papiers.', 'unknown') }); } };
  const removeConversation = async (conversation: Conversation) => {
    if (!window.confirm(`Supprimer « ${conversation.title} » ?`)) return;
    if (conversation.id) try { await api.deleteConversation(conversation.id); } catch (error) { if (!(error instanceof ApiError && error.kind === 'not-found')) { dispatch({ type: 'error', value: error instanceof ApiError ? error : null }); return; } }
    const remaining = state.conversations.filter((item) => item.localId !== conversation.localId);
    dispatch({ type: 'sync', value: { conversations: remaining, activeLocalId: state.activeLocalId === conversation.localId ? (remaining[0]?.localId ?? null) : state.activeLocalId } });
    dispatch({ type: 'draft', id: conversation.localId, value: '' });
  };
  const renameConversation = (conversation: Conversation) => {
    const title = window.prompt(t.rename, conversation.title)?.trim();
    if (title) updateConversation({ ...conversation, title: title.slice(0, 64) });
  };
  const confirmPhrase = state.settings.language === 'fr' ? 'oui je confirme la commande' : 'i confirm the order';
  const cancelPhrase = state.settings.language === 'fr' ? 'annule la commande' : 'cancel the order';
  const themeIcon = state.settings.theme === 'dark' ? Moon : Sun;
  const ThemeIcon = themeIcon;

  return <div className="app-shell">
    <aside className={`sidebar ${mobileMenu === 'sidebar' ? 'drawer-open' : ''}`} aria-label={t.conversations}>
      <div className="brand"><div className="brand-mark"><ShoppingBag size={19} /><Sparkles size={10} className="brand-spark" /></div><div><strong>{t.title}</strong><span>AI shopping companion</span></div><button className="icon-button mobile-only" aria-label={t.close} onClick={() => setMobileMenu(null)}><X size={18} /></button></div>
      <button className="new-chat" onClick={freshChat}><Plus size={17} />{t.newChat}<kbd>⌘ K</kbd></button>
      <div className="section-label">{t.conversations}<span>{state.conversations.length}</span></div>
      <nav className="conversation-list" aria-label={t.conversations}>
        {state.conversations.map((conversation) => <div key={conversation.localId} className={`conversation-row ${state.activeLocalId === conversation.localId ? 'selected' : ''}`}>
          <button className="conversation-select" onClick={() => { dispatch({ type: 'active', id: conversation.localId }); setMobileMenu(null); }}><FileText size={15} /><span>{conversation.title}</span></button>
          <details className="row-menu"><summary aria-label="Options de conversation"><Ellipsis size={16} /></summary><div className="popover"><button onClick={() => renameConversation(conversation)}>{t.rename}</button><button onClick={() => void removeConversation(conversation)} className="danger-text">{t.delete}</button></div></details>
        </div>)}
        {!state.conversations.length && <p className="sidebar-empty">Vos prochains échanges apparaîtront ici.</p>}
      </nav>
      <div className="sidebar-bottom">
        <button className={`demo-toggle ${state.settings.demo ? 'enabled' : ''}`} onClick={() => dispatch({ type: 'settings', value: { demo: !state.settings.demo } })} aria-pressed={state.settings.demo}><span className="toggle-dot" />{t.demo}<span className="demo-tag">{state.settings.demo ? 'ON' : 'OFF'}</span></button>
        <button className="settings-trigger" onClick={() => setSettingsOpen((open) => !open)}><ThemeIcon size={16} />{t.settings}<ChevronDown size={15} /></button>
        {settingsOpen && <div className="settings-panel">
          <label>{t.settings}<select value={state.settings.theme} onChange={(event) => dispatch({ type: 'settings', value: { theme: event.target.value as Settings['theme'] } })}><option value="system">{t.system}</option><option value="light">{t.light}</option><option value="dark">{t.dark}</option></select></label>
          <label><Languages size={15} /> FR / EN<select value={state.settings.language} onChange={(event) => dispatch({ type: 'settings', value: { language: event.target.value as Settings['language'] } })}><option value="fr">Français</option><option value="en">English</option></select></label>
          <button className="clear-data" onClick={() => { localStorage.removeItem('p059-shopping-agent:v1'); dispatch({ type: 'clear' }); setSettingsOpen(false); }}>{t.clear}</button>
        </div>}
        <div className="profile"><div className="avatar avatar-user">AM</div><div><strong>Amira M.</strong><span>Compte invité</span></div><span className="online-dot" /></div>
      </div>
    </aside>
    {mobileMenu === 'sidebar' && <button className="backdrop" aria-label={t.close} onClick={() => setMobileMenu(null)} />}

    <main className="main-column">
      <header className="topbar"><button className="icon-button mobile-only" aria-label={t.menu} onClick={() => setMobileMenu('sidebar')}><Menu size={20} /></button><div className="mobile-brand"><div className="brand-mark"><ShoppingBag size={17} /><Sparkles size={9} className="brand-spark" /></div><strong>{t.title}</strong></div><div className="secure-indicator"><span className="secure-dot" /><span>Agent sécurisé</span><ChevronDown size={14} /></div><div className="top-actions"><span className="model-badge"><span /> GPT · assistant</span><button className="icon-button inspector-toggle" title={t.inspector} aria-label={t.inspector} onClick={() => setInspectorOpen((open) => !open)}><ActivityIcon size={18} /></button><button className="icon-button mobile-only" aria-label={t.inspector} onClick={() => setMobileMenu('inspector')}><ActivityIcon size={18} /></button></div></header>
      {state.error && <div className={`error-banner ${state.error.kind === 'validation' ? 'inline-error' : ''}`} role="alert"><AlertTriangle size={17} /><span>{state.error.message}</span>{state.error.kind === 'unavailable' && messages.some((message) => message.status === 'failed') && <button onClick={() => { const failed = [...messages].reverse().find((message) => message.status === 'failed'); if (failed) retry(failed); }}>{t.retry}</button>}<button className="icon-button" aria-label={t.close} onClick={() => dispatch({ type: 'error', value: null })}><X size={16} /></button></div>}
      {messages.length === 0 ? <section className="welcome-area">
        <div className="welcome-badge"><span className="pulse-ring" /><Sparkles size={15} />Un shopping plus simple</div>
        <h1>{t.welcome}</h1><p>{t.welcomeText}</p>
        <div className="suggestions">{t.suggestions.map((suggestion, index) => <button key={suggestion} onClick={() => chooseSuggestion(suggestion)} className={`suggestion suggestion-${index}`}><span>{['☕', '🎁', '✦', '🛍'][index]}</span>{suggestion}<ArrowUp size={14} /></button>)}</div>
        {state.settings.demo && <div className="security-demo"><div><ShieldAlert size={16} /><strong>{t.securityDemo}</strong><span>Les requêtes d’attaque restent isolées.</span></div><button onClick={() => chooseSuggestion(t.promptInjection)}>{t.promptInjection}</button><button onClick={() => chooseSuggestion(t.immediateOrder)}>{t.immediateOrder}</button></div>}
        <div className="trust-row"><span><ShieldAlert size={14} /> Confirmation obligatoire</span><i /><span><ActivityIcon size={14} /> Traçabilité visible</span><i /><span><Check size={14} /> Prix vérifiés</span></div>
      </section> : <section className="messages" aria-label="Conversation" aria-live="polite" aria-busy={state.pending}>
        {messages.map((message) => <MessageView key={message.id} message={message} language={state.settings.language} demo={state.settings.demo} latest={messages.at(-1)?.id === message.id} onCopy={doCopy} copied={copied === message.id} retry={retry} confirm={() => void send(confirmPhrase)} cancel={() => void send(cancelPhrase)} t={t} />)}
        {state.pending && <div className="pending-row"><div className="avatar avatar-agent"><Sparkles size={15} /></div><div className="pending-card"><div className="typing"><i /><i /><i /></div><span>{elapsed >= 15 ? t.still : t.working}</span><small>{elapsed}s</small></div></div>}
        <div ref={bottomRef} />
      </section>}
      <div className="composer-wrap"><form className="composer" onSubmit={(event) => { event.preventDefault(); void send(currentDraft); }}>
        <textarea ref={composerRef} value={currentDraft} rows={1} maxLength={config.max_message_length} placeholder={t.placeholder} aria-label={t.placeholder} disabled={state.pending}
          onChange={(event) => { setDraft(event.target.value); event.currentTarget.style.height = 'auto'; event.currentTarget.style.height = `${Math.min(event.currentTarget.scrollHeight, 160)}px`; }}
          onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void send(currentDraft); } }} />
        <div className="composer-footer"><span className={currentDraft.length >= config.max_message_length * 0.9 ? 'char-warning' : ''}>{currentDraft.length} / {config.max_message_length} {t.limit}</span><div><span className="enter-hint">↵ Entrée pour envoyer · ⇧↵ nouvelle ligne</span>{state.pending ? <button type="button" className="stop-button" onClick={stop}><X size={15} />{t.cancel}</button> : <button className="send-button" type="submit" disabled={!currentDraft.trim() || currentDraft.length > config.max_message_length}><Send size={15} />{t.send}</button>}</div></div>
      </form><div className="composer-footnote">Shopping Agent peut se tromper. Vérifiez les détails avant de confirmer une commande.</div></div>
    </main>

      <Suspense fallback={<aside className="inspector inspector-loading" aria-label={t.inspector} />}><Inspector messages={messages} products={products} t={t} language={state.settings.language} demo={state.settings.demo} version={config.version} tab={inspector} setTab={setInspector} open={inspectorOpen} mobileOpen={mobileMenu === 'inspector'} onHide={() => setInspectorOpen(false)} onClose={() => setMobileMenu(null)} onAsk={(name) => { setDraft(`${state.settings.language === 'fr' ? 'Parle-moi de' : 'Tell me about'} ${name}`); setMobileMenu(null); }} /></Suspense>
    {mobileMenu === 'inspector' && <button className="backdrop inspector-backdrop" aria-label={t.close} onClick={() => setMobileMenu(null)} />}
    {!inspectorOpen && <button className="reopen-inspector" aria-label={t.inspector} title={t.inspector} onClick={() => setInspectorOpen(true)}><ChevronLeft size={17} /><ActivityIcon size={17} /></button>}
  </div>;
}

type Labels = typeof dictionary.fr;
function MessageView({ message, language, demo, latest, onCopy, copied, retry, confirm, cancel, t }: {
  message: Message; language: 'fr' | 'en'; demo: boolean; latest: boolean; onCopy: (id: string, text: string) => void; copied: boolean;
  retry: (message: Message) => void; confirm: () => void; cancel: () => void; t: Labels;
}) {
  const proposal = getProposal(message.trace); const confirmed = getConfirmed(message.trace); const blocked = isBlocked(message);
  if (message.role === 'user') return <motion.article className="message-row user-message" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
    <div className={`message-bubble user-bubble ${message.status === 'failed' ? 'failed-bubble' : ''}`}><p>{message.content}</p><div className="message-meta"><time>{timeLabel(message.createdAt, language)}</time>{message.status === 'failed' ? <button className="retry-inline" onClick={() => retry(message)}><AlertTriangle size={12} />{t.retry}</button> : <Check size={13} />}</div></div>
  </motion.article>;
  return <motion.article className="message-row assistant-message" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.22 }}>
    <div className="avatar avatar-agent"><Sparkles size={15} /></div><div className="assistant-content">
      {blocked ? <div className="blocked-notice"><ShieldAlert size={19} /><div><strong>{t.blocked}</strong><p>prompt_injection_pattern</p></div><span>Bloqué</span></div> : <div className="assistant-bubble"><Suspense fallback={<div className="skeleton-lines"><i /><i /><i /></div>}><Markdown content={message.content} /></Suspense>{message.degraded && <div className="degraded-note"><AlertTriangle size={14} />Réponse de secours basée sur les résultats disponibles.</div>}
        {proposal && <OrderCard data={proposal} readOnly={!latest || message.stale} confirm={confirm} cancel={cancel} t={t} language={language} />}
        {confirmed && !proposal && <SuccessCard data={confirmed} t={t} language={language} onCopy={(text) => onCopy(message.id, text)} copied={copied} />}
      </div>}
      <div className="assistant-tools"><time>{timeLabel(message.createdAt, language)}</time><button onClick={() => onCopy(message.id, message.content)} aria-label={t.copy}><Copy size={13} />{copied ? 'Copié' : t.copy}</button></div>
      {message.trace?.length ? <details className="message-activity"><summary><ActivityIcon size={14} />{t.how}<ChevronDown size={13} /></summary><div className="timeline">{message.trace.map((item, index) => <TraceRow key={`${item.tool_called}-${index}`} item={item} demo={demo} t={t} />)}</div></details> : null}
    </div>
  </motion.article>;
}

function OrderCard({ data, readOnly, confirm, cancel, t, language }: { data: Record<string, unknown>; readOnly: boolean; confirm: () => void; cancel: () => void; t: Labels; language: 'fr' | 'en' }) {
  const name = String(data.product_name ?? 'Produit'); const qty = Number(data.quantity ?? 1); const currency = typeof data.currency === 'string' ? data.currency : undefined;
  return <div className="order-card"><div className="order-card-title"><div className="order-icon"><ShoppingBag size={16} /></div><div><span className="eyebrow">ÉTAPE SUIVANTE</span><strong>{t.order}</strong></div><span className={`status-pill ${readOnly ? 'muted-status' : 'awaiting-status'}`}>{readOnly ? 'En attente' : 'À confirmer'}</span></div>
    <div className="order-line"><div className="order-product-thumb"><ShoppingBag size={17} /></div><div><strong>{name}</strong><span>{qty} × {formatMoney(String(data.unit_price ?? data.total ?? '0'), currency, language === 'fr' ? 'fr-TN' : 'en')}</span></div><strong>{formatMoney(String(data.total ?? 0), currency, language === 'fr' ? 'fr-TN' : 'en')}</strong></div>
    <div className="order-total"><span>Total vérifié</span><strong>{formatMoney(String(data.total ?? 0), currency, language === 'fr' ? 'fr-TN' : 'en')}</strong></div>
    {readOnly ? <p className="readonly-note">Cette proposition n’est plus active. Demandez un nouveau récapitulatif pour continuer.</p> : <div className="order-actions"><button onClick={confirm}><Check size={15} />{t.confirmOrder}</button><button onClick={cancel}>{t.cancelOrder}</button></div>}
  </div>;
}
function SuccessCard({ data, t, language, onCopy, copied }: { data: Record<string, unknown>; t: Labels; language: 'fr' | 'en'; onCopy: (text: string) => void; copied: boolean }) {
  const summary = `${t.confirmed}: ${String(data.order_id ?? '')} · ${formatMoney(String(data.total ?? 0), typeof data.devise === 'string' ? data.devise : undefined, language === 'fr' ? 'fr-TN' : 'en')}`;
  return <div className="success-card"><div className="success-check"><Check size={19} /></div><div className="success-copy"><strong>{t.confirmed}</strong><span>Commande #{String(data.order_id ?? '—')} · {String(data.statut ?? data.status ?? 'confirmée')}</span></div><button onClick={() => onCopy(summary)} aria-label="Copier le récapitulatif"><Copy size={14} />{copied ? 'Copié' : t.copy}</button></div>;
}
function TraceRow({ item, demo, t }: { item: TraceEntry; demo: boolean; t: Labels }) {
  const Icon = iconMap[item.tool_called] ?? ActivityIcon; const result = getObject(item.result); const failed = Boolean(result.error); const blocked = failed && /bloqu|refus|confirm/i.test(String(result.error));
  const label = item.tool_called === 'search_product' ? t.search : item.tool_called === 'propose_order' ? t.proposal : item.tool_called === 'confirm_order' || item.tool_called === 'create_order' ? t.confirmation : item.tool_called === 'cancel_order' ? t.cancellation : item.tool_called;
  const summary = item.tool_called === 'search_product' ? `${Array.isArray(result.produits_trouves) ? result.produits_trouves.length : 0} résultats` : String(result.product_name ?? result.statut ?? result.status ?? (failed ? 'Action refusée' : 'Terminé'));
  return <div className={`trace-row ${failed ? 'trace-failed' : ''}`}><div className="trace-icon"><Icon size={14} /></div><div className="trace-text"><strong>{label}</strong><span>{blocked ? 'Refusé par les règles de sécurité' : summary}</span>{demo && <details className="trace-json"><summary>JSON technique</summary><pre>{JSON.stringify({ step: item.step, tool_called: item.tool_called, args: item.args, result: item.result }, null, 2)}</pre></details>}</div><span className={`trace-state ${failed ? 'is-failed' : ''}`}>{failed ? (blocked ? 'Refusé' : 'Erreur') : 'OK'}</span></div>;
}
