import { describe, it, expect, beforeEach, vi } from 'vitest';
import { apiRequest, TOKEN_KEY, USER_KEY, NOTICE_KEY } from '../lib/api';

describe('API Client (api.js)', () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it('attaches the Bearer token when token is present in sessionStorage', async () => {
    sessionStorage.setItem(TOKEN_KEY, 'test_sample_jwt_token_123');

    let capturedHeaders = null;
    vi.spyOn(global, 'fetch').mockImplementation((url, init) => {
      capturedHeaders = init.headers;
      return Promise.resolve({
        status: 200,
        json: () => Promise.resolve({ success: true, data: { status: 'ok' }, error: null, meta: {} }),
      });
    });

    const data = await apiRequest('/health');
    expect(data).toEqual({ status: 'ok' });
    expect(capturedHeaders['Authorization']).toBe('Bearer test_sample_jwt_token_123');
  });

  it('clears session and sets notice on 401 TOKEN_EXPIRED for authenticated endpoints', async () => {
    sessionStorage.setItem(TOKEN_KEY, 'expired_jwt_token');
    sessionStorage.setItem(USER_KEY, JSON.stringify({ id: 1, username: 'analyst' }));

    vi.spyOn(global, 'fetch').mockImplementation(() => {
      return Promise.resolve({
        status: 401,
        json: () =>
          Promise.resolve({
            success: false,
            data: null,
            error: { code: 'TOKEN_EXPIRED', message: 'Authentication token has expired.' },
            meta: {},
          }),
      });
    });

    await expect(apiRequest('/dashboard/summary')).rejects.toThrow('Authentication token has expired.');

    expect(sessionStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(sessionStorage.getItem(USER_KEY)).toBeNull();
    expect(sessionStorage.getItem(NOTICE_KEY)).toBe('Your session expired. Please sign in again.');
  });

  it('does not clear session on 401 for /auth/login failure', async () => {
    sessionStorage.setItem(TOKEN_KEY, 'existing_token');

    vi.spyOn(global, 'fetch').mockImplementation(() => {
      return Promise.resolve({
        status: 401,
        json: () =>
          Promise.resolve({
            success: false,
            data: null,
            error: { code: 'INVALID_CREDENTIALS', message: 'Invalid credentials' },
            meta: {},
          }),
      });
    });

    await expect(apiRequest('/auth/login', { method: 'POST', body: {} })).rejects.toThrow('Invalid credentials');
    expect(sessionStorage.getItem(TOKEN_KEY)).toBe('existing_token');
  });

  it('serializes query parameters correctly', async () => {
    let capturedUrl = null;
    vi.spyOn(global, 'fetch').mockImplementation((url) => {
      capturedUrl = url;
      return Promise.resolve({
        status: 200,
        json: () => Promise.resolve({ success: true, data: [], error: null, meta: {} }),
      });
    });

    await apiRequest('/investigations', { params: { page: 2, q: 'ransomware', status: 'draft' } });
    expect(capturedUrl).toContain('page=2');
    expect(capturedUrl).toContain('q=ransomware');
    expect(capturedUrl).toContain('status=draft');
  });
});

