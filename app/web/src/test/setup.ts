import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterAll, afterEach, beforeAll } from 'vitest';
import { server } from '../mocks/server';
import { resetMockState } from '../mocks/handlers';

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
  resetMockState();
  try {
    window.localStorage.clear();
    window.sessionStorage.clear();
  } catch {
    /* ignore */
  }
});
afterAll(() => server.close());
