import { describe, expect, it } from 'vitest';
import { formatMoney } from './format';

describe('formatMoney', () => {
  it('formats TND with three fractional digits', () => {
    expect(formatMoney('19.9', 'TND', 'en')).toContain('19.900');
  });
  it('does not invent a currency symbol when the code is missing', () => {
    const result = formatMoney(19.9, undefined, 'en');
    expect(result).toContain('19.9');
    expect(result).not.toMatch(/[€$£]/);
  });
});
