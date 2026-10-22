import { beforeEach, describe, expect, it } from 'vitest';
import { readStorage, STORAGE_KEY, writeStorage } from './storage';

describe('versioned local persistence', () => {
  beforeEach(() => localStorage.clear());
  it('returns defaults for malformed storage', () => {
    localStorage.setItem(STORAGE_KEY, '{bad json');
    expect(readStorage().conversations).toEqual([]);
  });
  it('ignores invalid settings from old or edited local data', () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ settings: { language: 'xx', theme: 'surprise', demo: 'yes' } }));
    expect(readStorage().settings).toEqual({ theme: 'system', language: 'fr', demo: false });
  });
  it('safely persists settings and conversation index', () => {
    const value = readStorage(); value.settings.language = 'en';
    writeStorage(value);
    expect(readStorage().settings.language).toBe('en');
  });
});
