import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/chat': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/conversations': 'http://localhost:8000',
      '/products': 'http://localhost:8000',
      '/config': 'http://localhost:8000',
    },
  },
  test: { environment: 'jsdom', setupFiles: ['./src/test/setup.ts'], css: true },
});
