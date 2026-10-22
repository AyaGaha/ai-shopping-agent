import { useMemo, useState } from 'react';
import { Activity, AlertTriangle, CheckCheck, ChevronDown, ChevronRight, Search, ShieldAlert, ShoppingBag, Sparkles, X, type LucideIcon } from 'lucide-react';
import type { Message, Product, TraceEntry } from '../../api/types';
import { formatMoney, initials } from '../../lib/format';
import type { copy } from '../../lib/i18n';

type Labels = typeof copy.fr;
type Props = {
  messages: Message[]; products: Product[]; t: Labels; language: 'fr' | 'en'; demo: boolean; version: string;
  tab: 'activity' | 'catalog'; setTab: (tab: 'activity' | 'catalog') => void; open: boolean; mobileOpen: boolean;
  onHide: () => void; onClose: () => void; onAsk: (text: string) => void;
};
const toolIcons: Record<string, LucideIcon> = { search_product: Search, propose_order: ShoppingBag, create_order: ShoppingBag, confirm_order: CheckCheck, cancel_order: X };
const object = (value: unknown): Record<string, unknown> => value && typeof value === 'object' ? value as Record<string, unknown> : {};
const blocked = (message: Message) => message.content.startsWith('Je ne peux pas traiter une demande qui tente de modifier les règles de sécurité');
const time = (value: number, language: 'fr' | 'en') => new Intl.DateTimeFormat(language === 'fr' ? 'fr-TN' : 'en', { hour: '2-digit', minute: '2-digit' }).format(value);

export default function Inspector(props: Props) {
  const { messages, products, t, language, demo, version, tab, setTab, open, mobileOpen, onHide, onClose, onAsk } = props;
  const [query, setQuery] = useState('');
  const filtered = useMemo(() => products.filter((product) => `${product.name} ${product.description}`.toLowerCase().includes(query.toLowerCase())), [products, query]);
  return <aside className={`inspector ${open ? '' : 'inspector-collapsed'} ${mobileOpen ? 'drawer-open' : ''}`} aria-label={t.inspector}>
    <div className="inspector-head"><div><span className="eyebrow">APERÇU EN DIRECT</span><strong>{t.inspector}</strong></div><button className="icon-button mobile-only" aria-label={t.close} onClick={onClose}><X size={18} /></button><button className="icon-button inspector-hide" aria-label="Masquer l’inspecteur" onClick={onHide}><ChevronRight size={18} /></button></div>
    <div className="tabs" role="tablist"><button role="tab" aria-selected={tab === 'activity'} onClick={() => setTab('activity')}><Activity size={15} />{t.activity}</button><button role="tab" aria-selected={tab === 'catalog'} onClick={() => setTab('catalog')}><ShoppingBag size={15} />{t.catalog}<span className="tab-count">{products.length}</span></button></div>
    {tab === 'activity' ? <ActivityPanel messages={messages} t={t} demo={demo} language={language} /> : <div className="catalog-panel"><div className="catalog-search"><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t.searchProducts} aria-label={t.searchProducts} /><kbd>/</kbd></div><p className="catalog-count">{filtered.length} {t.productCount}</p><div className="product-list">{filtered.map((product) => <div className="product-card" key={product.id}>
      {product.image_url ? <img src={product.image_url} alt="" loading="lazy" /> : <div className="product-placeholder"><span>{initials(product.name)}</span><Sparkles size={15} /></div>}
      <div className="product-info"><strong>{product.name}</strong><span>{formatMoney(product.price, product.currency, language === 'fr' ? 'fr-TN' : 'en')}</span><p>{product.description || 'Un article soigneusement sélectionné pour votre quotidien.'}</p><button onClick={() => onAsk(product.name)}>{t.ask}<ChevronRight size={13} /></button></div>
    </div>)}{!filtered.length && <p className="empty-catalog">{t.emptyCatalog}</p>}</div></div>}
    <div className="inspector-foot"><div className="online-dot" />Système opérationnel<span>v{version}</span></div>
  </aside>;
}

function ActivityPanel({ messages, t, demo, language }: { messages: Message[]; t: Labels; demo: boolean; language: 'fr' | 'en' }) {
  const entries = messages.filter((message) => message.role === 'assistant');
  if (!entries.length) return <div className="activity-empty"><div className="activity-empty-icon"><Activity size={18} /></div><strong>Une transparence à chaque étape</strong><p>Les recherches et les actions de commande apparaîtront ici pendant la conversation.</p><div className="activity-legend"><span><i className="legend-green" />Vérifié</span><span><i className="legend-amber" />Confirmation requise</span></div></div>;
  return <div className="activity-panel"><div className="activity-summary"><div><span>ÉTAPES OBSERVÉES</span><strong>{entries.reduce((count, message) => count + (message.trace?.length ?? 0), 0)}</strong></div><div className="activity-live"><i />Historique</div></div>{entries.map((message) => <section className="activity-group" key={message.id}><span className="activity-time">{time(message.createdAt, language)}</span><p className="activity-answer">{message.content.slice(0, 88)}{message.content.length > 88 ? '…' : ''}</p>{blocked(message) && <div className="activity-blocked"><ShieldAlert size={15} />{t.blocked}<small>prompt_injection_pattern</small></div>}<div className="timeline">{message.trace?.map((item, index) => <TraceRow key={`${item.tool_called}-${index}`} item={item} demo={demo} t={t} />)}</div></section>)}</div>;
}
function TraceRow({ item, demo, t }: { item: TraceEntry; demo: boolean; t: Labels }) {
  const Icon = toolIcons[item.tool_called] ?? Activity; const result = object(item.result); const failed = Boolean(result.error); const refused = failed && /bloqu|refus|confirm/i.test(String(result.error));
  const label = item.tool_called === 'search_product' ? t.search : item.tool_called === 'propose_order' ? t.proposal : item.tool_called === 'confirm_order' || item.tool_called === 'create_order' ? t.confirmation : item.tool_called === 'cancel_order' ? t.cancellation : item.tool_called;
  const summary = item.tool_called === 'search_product' ? `${Array.isArray(result.produits_trouves) ? result.produits_trouves.length : 0} résultats` : String(result.product_name ?? result.statut ?? result.status ?? (failed ? 'Action refusée' : 'Terminé'));
  return <div className={`trace-row ${failed ? 'trace-failed' : ''}`}><div className="trace-icon"><Icon size={14} /></div><div className="trace-text"><strong>{label}</strong><span>{refused ? 'Refusé par les règles de sécurité' : summary}</span>{demo && <details className="trace-json"><summary>JSON technique</summary><pre>{JSON.stringify({ step: item.step, tool_called: item.tool_called, args: item.args, result: item.result }, null, 2)}</pre></details>}</div><span className={`trace-state ${failed ? 'is-failed' : ''}`}>{failed ? (refused ? 'Refusé' : 'Erreur') : 'OK'}</span></div>;
}
