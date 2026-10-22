import type { Conversation } from '../api/types';

export const STORAGE_KEY = 'p059-shopping-agent:v1';
export type Settings = { theme: 'system' | 'light' | 'dark'; language: 'fr' | 'en'; demo: boolean };
export type Persisted = { conversations: Conversation[]; activeLocalId: string | null; drafts: Record<string, string>; settings: Settings };
const defaults: Persisted = { conversations: [], activeLocalId: null, drafts: {}, settings: { theme: 'system', language: 'fr', demo: false } };
export function readStorage(): Persisted {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaults;
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== 'object') return defaults;
    const data = value as Partial<Persisted>;
    const conversations = Array.isArray(data.conversations) ? data.conversations.filter(isConversation) : [];
    const theme = data.settings?.theme;
    const language = data.settings?.language;
    const demo = data.settings?.demo;
    const drafts = data.drafts && typeof data.drafts === 'object' && !Array.isArray(data.drafts)
      ? Object.fromEntries(Object.entries(data.drafts).filter((entry): entry is [string, string] => typeof entry[1] === 'string'))
      : {};
    const active = typeof data.activeLocalId === 'string' && conversations.some((item) => item.localId === data.activeLocalId) ? data.activeLocalId : null;
    return {
      conversations,
      activeLocalId: active,
      drafts,
      settings: {
        theme: theme === 'light' || theme === 'dark' || theme === 'system' ? theme : defaults.settings.theme,
        language: language === 'en' || language === 'fr' ? language : defaults.settings.language,
        demo: typeof demo === 'boolean' ? demo : defaults.settings.demo,
      },
    };
  } catch { return defaults; }
}
function isConversation(value: unknown): value is Conversation {
  if (!value || typeof value !== 'object') return false;
  const item = value as Partial<Conversation>;
  return typeof item.localId === 'string' && typeof item.title === 'string'
    && typeof item.updatedAt === 'number' && Number.isFinite(item.updatedAt)
    && Array.isArray(item.messages) && item.messages.every((message) => {
      if (!message || typeof message !== 'object') return false;
      const row = message as Partial<Conversation['messages'][number]>;
      return typeof row.id === 'string' && (row.role === 'user' || row.role === 'assistant')
        && typeof row.content === 'string' && ['pending', 'streaming', 'done', 'failed'].includes(String(row.status))
        && typeof row.createdAt === 'number'
        && (row.trace === undefined || (Array.isArray(row.trace) && row.trace.every((event) => !!event && typeof event.tool_called === 'string')));
    });
}
export function writeStorage(value: Persisted): void {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(value)); } catch { /* storage may be disabled or full */ }
}
