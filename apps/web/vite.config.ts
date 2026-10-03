import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    fs: { allow: [fileURLToPath(new URL('.', import.meta.url)), fileURLToPath(new URL('../../packages/contracts', import.meta.url))] },
    proxy: { '/api': 'http://127.0.0.1:18867', '/health': 'http://127.0.0.1:18867' },
  },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
});
