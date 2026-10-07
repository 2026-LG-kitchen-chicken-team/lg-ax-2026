import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    fs: { allow: [fileURLToPath(new URL('.', import.meta.url)), fileURLToPath(new URL('../../packages/contracts', import.meta.url)), fileURLToPath(new URL('../../evals/core-contract/schemas', import.meta.url))] },
    // LGAX_WORKSPACE_PROXY lets a separate planning-enabled workspace server (e.g. 18879) be used without touching 18869.
    // LGAX_PUBLIC_API_PROXY lets a test public API (e.g. one serving a dated demo dataset) be used without touching 18867.
    proxy: { '/api/research': process.env.LGAX_WORKSPACE_PROXY ?? 'http://127.0.0.1:18869', '/api/workspace': process.env.LGAX_WORKSPACE_PROXY ?? 'http://127.0.0.1:18869', '/api': process.env.LGAX_PUBLIC_API_PROXY ?? 'http://127.0.0.1:18867', '/health': process.env.LGAX_PUBLIC_API_PROXY ?? 'http://127.0.0.1:18867' },
  },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
});
