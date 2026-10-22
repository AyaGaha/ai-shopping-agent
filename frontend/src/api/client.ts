import { z } from 'zod';
import { ChatSchema, ConfigSchema, ProductsSchema, type ChatResponse } from './types';

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') ?? '';
export class ApiError extends Error {
  constructor(public status: number, message: string, public kind: 'validation' | 'unavailable' | 'network' | 'budget' | 'not-found' | 'unknown') {
    super(message); this.name = 'ApiError';
  }
}
export function mapError(status: number, detail = ''): ApiError {
  if (status === 404) return new ApiError(status, 'Cette conversation a expiré. Démarrez-en une nouvelle.', 'not-found');
  if (status === 422) return new ApiError(status, detail || 'Votre message ne peut pas être envoyé tel quel.', 'validation');
  if (status === 429) return new ApiError(status, 'Le budget de requêtes est temporairement atteint. Réessayez bientôt.', 'budget');
  if (status === 502 || status >= 500) return new ApiError(status, 'Le modèle de langue est momentanément indisponible.', 'unavailable');
  return new ApiError(status, 'La requête n’a pas abouti. Réessayez.', 'unknown');
}
async function request<T>(path: string, schema: z.ZodType<T>, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(new DOMException('Request timed out', 'TimeoutError')), 60_000);
  const externalSignal = init?.signal;
  const forwardAbort = () => controller.abort(externalSignal?.reason);
  if (externalSignal?.aborted) forwardAbort();
  else externalSignal?.addEventListener('abort', forwardAbort, { once: true });
  try {
    const response = await fetch(`${API_BASE}${path}`, { ...init, signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...init?.headers } });
    if (!response.ok) {
      let detail = '';
      try { const body: unknown = await response.json(); if (typeof body === 'object' && body && 'detail' in body) detail = String(body.detail); } catch { /* use mapped message */ }
      throw mapError(response.status, detail);
    }
    const payload: unknown = await response.json();
    const parsed = schema.safeParse(payload);
    if (!parsed.success) throw new ApiError(0, 'La réponse du serveur est invalide.', 'unknown');
    return parsed.data;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === 'AbortError') throw new ApiError(0, 'Requête annulée.', 'network');
    if (error instanceof TypeError) throw new ApiError(0, 'Connexion impossible. Vérifiez votre réseau.', 'network');
    throw new ApiError(0, 'Une erreur inattendue est survenue.', 'unknown');
  } finally { clearTimeout(timeout); externalSignal?.removeEventListener('abort', forwardAbort); }
}
export const api = {
  chat: (message: string, conversationId?: string, signal?: AbortSignal) => request('/chat', ChatSchema, {
    method: 'POST', signal, body: JSON.stringify({ message, ...(conversationId ? { conversation_id: conversationId } : {}) }),
  }) as Promise<ChatResponse>,
  config: () => request('/config', ConfigSchema),
  products: () => request('/products', ProductsSchema),
  history: (id: string) => request(`/conversations/${encodeURIComponent(id)}/messages`, z.object({ messages: z.array(z.unknown()) }).passthrough()),
  deleteConversation: (id: string) => request(`/conversations/${encodeURIComponent(id)}`, z.object({ deleted: z.boolean() }), { method: 'DELETE' }),
};
