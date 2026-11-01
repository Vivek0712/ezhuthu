/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // contracts/ lives at the repo root; the JSONL validator imports the benchmark schema from there.
    fs: { allow: ['../..'] },
  },
  build: {
    target: 'es2022',
    sourcemap: true,
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: false,
    coverage: { provider: 'v8', include: ['src/**'] },
  },
});
