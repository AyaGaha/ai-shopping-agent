import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from './App';

const id = '2e79ca44-b0d0-4b03-8ef8-aeb24f00d8f0';
function json(body: unknown) { return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }); }

describe('shopping flow', () => {
  afterEach(() => { vi.restoreAllMocks(); localStorage.clear(); });
  it('shows an order proposal and confirms it in a later message', async () => {
    let turn = 0;
    const chatMessages: string[] = [];
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/config')) return json({ max_message_length: 2000, version: 'test' });
      if (url.endsWith('/products')) return json([]);
      turn += 1;
      chatMessages.push(JSON.parse(String(init?.body)).message as string);
      return json(turn === 1 ? {
        conversation_id: id, final_response: '2 × Mug céramique blanc — confirmez ?', steps_used: 1,
        trace: [{ step: 0, tool_called: 'propose_order', args: { product_id: 21, quantity: 2 }, result: { status: 'proposal_ready', product_name: 'Mug céramique blanc', quantity: 2, unit_price: '9.90', total: '19.80', currency: 'TND' } }],
      } : {
        conversation_id: id, final_response: 'Commande confirmée.', steps_used: 2,
        trace: [{ step: 0, tool_called: 'confirm_order', args: { order_id: 56 }, result: { order_id: 56, status: 'processing', total: '19.80', devise: 'TND' } }],
      });
    }));
    render(<App />);
    fireEvent.change(screen.getByRole('textbox', { name: /décrivez/i }), { target: { value: 'Commande 2 mugs blancs' } });
    fireEvent.keyDown(screen.getByRole('textbox', { name: /décrivez/i }), { key: 'Enter', code: 'Enter' });
    expect(await screen.findByText('Mug céramique blanc')).toBeInTheDocument();
    expect(screen.getByText(/19,800|19.800/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /confirmer la commande/i }));
    await waitFor(() => expect(screen.getByText('Commande confirmée')).toBeInTheDocument());
    expect(turn).toBe(2);
    expect(chatMessages[1]).toBe('oui je confirme la commande');
  });

  it('keeps Shift+Enter as a newline and enforces the server limit', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/config')) return json({ max_message_length: 10, version: 'test' });
      if (url.endsWith('/products')) return json([]);
      throw new Error('Chat should not be sent in this test');
    }));
    render(<App />);
    const composer = screen.getByRole('textbox', { name: /décrivez/i });
    await waitFor(() => expect(composer).toHaveAttribute('maxlength', '10'));
    fireEvent.change(composer, { target: { value: 'café' } });
    fireEvent.keyDown(composer, { key: 'Enter', code: 'Enter', shiftKey: true });
    expect(composer).toHaveValue('café');
    fireEvent.change(composer, { target: { value: '12345678901' } });
    expect(screen.getByRole('button', { name: /envoyer/i })).toBeDisabled();
  });
});
