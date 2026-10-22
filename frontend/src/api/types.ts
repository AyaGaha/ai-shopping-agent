import { z } from 'zod';

export const TraceSchema = z.object({
  step: z.number().optional(),
  tool_called: z.string(),
  args: z.record(z.unknown()).default({}),
  result: z.unknown(),
}).passthrough();
export const ChatSchema = z.object({
  conversation_id: z.string().uuid(), final_response: z.string(), steps_used: z.number(),
  trace: z.array(TraceSchema).default([]), degraded: z.boolean().optional(),
}).passthrough();
export const ConfigSchema = z.object({ max_message_length: z.number().int().positive(), version: z.string() }).passthrough();
export const ProductSchema = z.object({
  id: z.union([z.string(), z.number()]), name: z.string(), price: z.union([z.string(), z.number()]),
  currency: z.string().nullable().optional(), description: z.string().default(''), image_url: z.string().optional(),
}).passthrough();
export const ProductsSchema = z.array(ProductSchema);
export type TraceEntry = z.infer<typeof TraceSchema>;
export type Product = z.infer<typeof ProductSchema>;
export type ChatResponse = z.infer<typeof ChatSchema>;
export type Message = {
  id: string; role: 'user' | 'assistant'; content: string; status: 'pending' | 'streaming' | 'done' | 'failed';
  trace?: TraceEntry[]; createdAt: number; error?: string; stale?: boolean; degraded?: boolean;
};
export type Conversation = { id?: string; localId: string; title: string; updatedAt: number; messages: Message[] };
