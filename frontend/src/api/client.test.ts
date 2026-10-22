import { describe, expect, it } from 'vitest';
import { mapError } from './client';

describe('API error mapping', () => {
  it.each([[404, 'not-found'], [422, 'validation'], [429, 'budget'], [502, 'unavailable']] as const)(
    'maps HTTP %i to a human-readable kind', (status, kind) => {
      const error = mapError(status);
      expect(error.kind).toBe(kind);
      expect(error.message).not.toMatch(/\{|Traceback/);
    },
  );
});
