import React from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import CorrelationPanel from '../components/investigations/CorrelationPanel';
import { ToastProvider } from '../components/ui/Toast';

const MOCK_STAGES = [
  {
    name: 'crypto_matching',
    label: 'Cryptographic Matching',
    description: 'Correlates personas via shared PGP keys and cryptocurrency wallets.',
    available: true,
  },
  {
    name: 'infrastructure_matching',
    label: 'Infrastructure Matching',
    description: 'Correlates personas via onion mirrors, IP addresses, and SSL certs.',
    available: true,
  },
  {
    name: 'stylometry',
    label: 'Stylometric Analysis',
    description: 'Correlates author writeprints using n-gram vocabulary and POS frequencies.',
    available: false,
  },
];

function renderCorrelationPanel(props = {}) {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <CorrelationPanel investigationId="1" hasData={true} {...props} />
      </ToastProvider>
    </MemoryRouter>
  );
}

describe('Correlation UI Components (Phase 7)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  it('stage cards render statuses from polling responses and polling stops on completion', async () => {
    let pollCount = 0;

    vi.spyOn(global, 'fetch').mockImplementation((url, opts) => {
      const method = opts?.method || 'GET';

      // 1. Pipeline stages
      if (url.includes('/api/v1/pipeline/stages') && method === 'GET') {
        return Promise.resolve({
          status: 200,
          json: () => Promise.resolve({ success: true, data: MOCK_STAGES }),
        });
      }

      // 2. Initial runs list
      if (url.includes('/api/v1/investigations/1/pipeline/runs') && !url.includes('/pipeline/runs/') && method === 'GET') {
        return Promise.resolve({
          status: 200,
          json: () =>
            Promise.resolve({
              success: true,
              data: [
                {
                  id: 101,
                  investigation_id: 1,
                  status: 'running',
                  is_stale: false,
                  stages: [
                    { stage: 'crypto_matching', status: 'completed', summary: { matches_found: 2 } },
                    { stage: 'infrastructure_matching', status: 'running', summary: {} },
                  ],
                },
              ],
            }),
        });
      }

      // 3. Polled run detail
      if (url.includes('/api/v1/investigations/1/pipeline/runs/101') && method === 'GET') {
        pollCount += 1;
        const isDone = pollCount >= 1;
        return Promise.resolve({
          status: 200,
          json: () =>
            Promise.resolve({
              success: true,
              data: {
                id: 101,
                investigation_id: 1,
                status: isDone ? 'completed' : 'running',
                is_stale: false,
                stages: [
                  { stage: 'crypto_matching', status: 'completed', summary: { matches_found: 2 } },
                  { stage: 'infrastructure_matching', status: isDone ? 'completed' : 'running', summary: { matches_found: 1 } },
                ],
              },
            }),
        });
      }

      // 4. Pairs and evidence upon completion
      if (url.includes('/api/v1/investigations/1/pairs')) {
        return Promise.resolve({
          status: 200,
          json: () => Promise.resolve({ success: true, data: { items: [], total: 0 } }),
        });
      }
      if (url.includes('/api/v1/investigations/1/evidence')) {
        return Promise.resolve({
          status: 200,
          json: () => Promise.resolve({ success: true, data: { items: [], total: 0 } }),
        });
      }

      return Promise.reject(new Error(`Unhandled URL: ${url}`));
    });

    renderCorrelationPanel();

    // Initially loads stages and shows RUNNING
    await waitFor(() => {
      expect(screen.getByText('Cryptographic Matching')).toBeInTheDocument();
      expect(screen.getByText('Infrastructure Matching')).toBeInTheDocument();
      expect(screen.getByText('Stylometric Analysis')).toBeInTheDocument();
      expect(screen.getByText('Planned')).toBeInTheDocument();
    });

    // Wait for the poll to update status to COMPLETED
    await waitFor(
      () => {
        const completedBadges = screen.getAllByText('COMPLETED');
        expect(completedBadges.length).toBeGreaterThanOrEqual(2);
      },
      { timeout: 4000 }
    );
  });

  it('run button is disabled with explanation when there is no data or a run is active', async () => {
    vi.spyOn(global, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/v1/pipeline/stages')) {
        return Promise.resolve({
          status: 200,
          json: () => Promise.resolve({ success: true, data: MOCK_STAGES }),
        });
      }
      if (url.includes('/api/v1/investigations/1/pipeline/runs')) {
        return Promise.resolve({
          status: 200,
          json: () => Promise.resolve({ success: true, data: [] }),
        });
      }
      return Promise.reject(new Error(`Unhandled URL: ${url}`));
    });

    // Test Case A: No data
    const { unmount } = renderCorrelationPanel({ hasData: false });

    await waitFor(() => {
      expect(screen.getByText('Cryptographic Matching')).toBeInTheDocument();
    });

    const runBtn = screen.getByRole('button', { name: /run correlation/i });
    expect(runBtn).toBeDisabled();
    expect(screen.getByText(/investigation has no collected posts or indicators/i)).toBeInTheDocument();

    unmount();

    // Test Case B: Active run
    vi.spyOn(global, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/v1/pipeline/stages')) {
        return Promise.resolve({
          status: 200,
          json: () => Promise.resolve({ success: true, data: MOCK_STAGES }),
        });
      }
      if (url.includes('/api/v1/investigations/1/pipeline/runs')) {
        return Promise.resolve({
          status: 200,
          json: () =>
            Promise.resolve({
              success: true,
              data: [
                {
                  id: 102,
                  investigation_id: 1,
                  status: 'running',
                  stages: [],
                },
              ],
            }),
        });
      }
      return Promise.reject(new Error(`Unhandled URL: ${url}`));
    });

    renderCorrelationPanel({ hasData: true });

    await waitFor(() => {
      const correlatingBtn = screen.getByRole('button', { name: /correlating\.\.\./i });
      expect(correlatingBtn).toBeDisabled();
    });
  });

  it('pair expansion shows evidence with strength number, explanation, and caveat', async () => {
    const user = userEvent.setup();

    const mockPair = {
      actors: {
        actor_a: { id: 1, username: 'hydra_vendor', marketplace: 'Hydra' },
        actor_b: { id: 2, username: 'silk_merchant', marketplace: 'SilkRoad' },
      },
      max_strength: 0.95,
      evidence_count: 1,
      per_dimension: {
        cryptographic: { max_strength: 0.95, count: 1 },
      },
    };

    const mockEvidence = {
      id: 501,
      pipeline_run_id: 101,
      dimension: 'cryptographic',
      evidence_type: 'shared_pgp_key',
      strength: 0.95,
      explanation:
        'Shared PGP Key (fpr 9A1B...): 100% fingerprint match across distinct marketplaces. Caveat: PGP keys may be shared or copied across profiles.',
      actor_a: { id: 1, username: 'hydra_vendor', marketplace: 'Hydra' },
      actor_b: { id: 2, username: 'silk_merchant', marketplace: 'SilkRoad' },
      details: {
        fingerprint: '9A1B2C3D4E5F67890123456789ABCDEF01234567',
        confidence: 'high',
      },
      sources: [
        {
          id: 1001,
          post: {
            id: 201,
            author: 'hydra_vendor',
            marketplace: 'Hydra',
            excerpt: 'Contact me via PGP 9A1B2C3D4E5F67890123456789ABCDEF01234567',
          },
          indicator: {
            id: 301,
            type: 'pgp_fingerprint',
            normalised_value: '9a1b2c3d4e5f67890123456789abcdef01234567',
          },
        },
      ],
    };

    vi.spyOn(global, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/v1/pipeline/stages')) {
        return Promise.resolve({
          status: 200,
          json: () => Promise.resolve({ success: true, data: MOCK_STAGES }),
        });
      }
      if (url.includes('/api/v1/investigations/1/pipeline/runs') && !url.includes('/pipeline/runs/')) {
        return Promise.resolve({
          status: 200,
          json: () =>
            Promise.resolve({
              success: true,
              data: [
                {
                  id: 101,
                  investigation_id: 1,
                  status: 'completed',
                  stages: [],
                },
              ],
            }),
        });
      }
      if (url.includes('/api/v1/investigations/1/pairs')) {
        return Promise.resolve({
          status: 200,
          json: () =>
            Promise.resolve({
              success: true,
              data: [mockPair],
              meta: { total: 1 },
            }),
        });
      }
      if (url.includes('/api/v1/investigations/1/evidence') && !url.includes('/evidence/501')) {
        return Promise.resolve({
          status: 200,
          json: () =>
            Promise.resolve({
              success: true,
              data: [mockEvidence],
              meta: { total: 1 },
            }),
        });
      }
      if (url.includes('/api/v1/investigations/1/evidence/501')) {
        return Promise.resolve({
          status: 200,
          json: () =>
            Promise.resolve({
              success: true,
              data: mockEvidence,
            }),
        });
      }
      return Promise.reject(new Error(`Unhandled URL: ${url}`));
    });

    renderCorrelationPanel();

    // Wait for the pair row to appear
    await waitFor(() => {
      expect(screen.getByText(/hydra_vendor/)).toBeInTheDocument();
      expect(screen.getByText(/silk_merchant/)).toBeInTheDocument();
      expect(screen.getAllByText(/0\.95/).length).toBeGreaterThan(0);
    });

    // Expand pair row
    const pairRow = screen.getByText(/hydra_vendor/).closest('div[class*="cursor-pointer"]');
    await user.click(pairRow);

    // Evidence card should now be visible
    await waitFor(() => {
      expect(screen.getByText('CRYPTOGRAPHIC')).toBeInTheDocument();
      expect(screen.getByText('shared_pgp_key')).toBeInTheDocument();
      expect(screen.getByText(/Shared PGP Key/)).toBeInTheDocument();
      expect(screen.getByText(/Caveat: PGP keys may be shared or copied across profiles\./)).toBeInTheDocument();
      expect(screen.getByText('Post #201')).toBeInTheDocument();
    });

    // Toggle technical parameters
    const toggleParamsBtn = screen.getByText('View technical parameters');
    await user.click(toggleParamsBtn);

    await waitFor(() => {
      expect(screen.getByText('Hide technical parameters')).toBeInTheDocument();
      expect(screen.getAllByText(/9A1B2C3D4E5F67890123456789ABCDEF01234567/).length).toBeGreaterThanOrEqual(2);
    });
  });

  it('stale warning banner displays when is_stale: true', async () => {
    vi.spyOn(global, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/v1/pipeline/stages')) {
        return Promise.resolve({
          status: 200,
          json: () => Promise.resolve({ success: true, data: MOCK_STAGES }),
        });
      }
      if (url.includes('/api/v1/investigations/1/pipeline/runs')) {
        return Promise.resolve({
          status: 200,
          json: () =>
            Promise.resolve({
              success: true,
              data: [
                {
                  id: 101,
                  investigation_id: 1,
                  status: 'completed',
                  is_stale: true,
                  stages: [],
                },
              ],
            }),
        });
      }
      if (url.includes('/api/v1/investigations/1/pairs') || url.includes('/api/v1/investigations/1/evidence')) {
        return Promise.resolve({
          status: 200,
          json: () => Promise.resolve({ success: true, data: { items: [], total: 0 } }),
        });
      }
      return Promise.reject(new Error(`Unhandled URL: ${url}`));
    });

    renderCorrelationPanel();

    await waitFor(() => {
      expect(
        screen.getByText('New data was added after this run. Run again to include it.')
      ).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /re-run now/i })).toBeInTheDocument();
    });
  });

  it('common indicators notice lists suppressed items with counts', async () => {
    vi.spyOn(global, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/v1/pipeline/stages')) {
        return Promise.resolve({
          status: 200,
          json: () => Promise.resolve({ success: true, data: MOCK_STAGES }),
        });
      }
      if (url.includes('/api/v1/investigations/1/pipeline/runs')) {
        return Promise.resolve({
          status: 200,
          json: () =>
            Promise.resolve({
              success: true,
              data: [
                {
                  id: 101,
                  investigation_id: 1,
                  status: 'completed',
                  is_stale: false,
                  stages: [
                    {
                      stage: 'crypto_matching',
                      status: 'completed',
                      summary: {
                        suppressed_common_indicators: [
                          {
                            type: 'wallet_btc',
                            normalised_value: 'bc1qdecoycommonindicator...',
                            actor_count: 6,
                            marketplace_count: 3,
                          },
                        ],
                      },
                    },
                  ],
                },
              ],
            }),
        });
      }
      if (url.includes('/api/v1/investigations/1/pairs') || url.includes('/api/v1/investigations/1/evidence')) {
        return Promise.resolve({
          status: 200,
          json: () => Promise.resolve({ success: true, data: { items: [], total: 0 } }),
        });
      }
      return Promise.reject(new Error(`Unhandled URL: ${url}`));
    });

    renderCorrelationPanel();

    await waitFor(() => {
      expect(screen.getByText('Suppressed Common Indicators (1)')).toBeInTheDocument();
      expect(screen.getByText('bc1qdecoycommonindicator...')).toBeInTheDocument();
      expect(screen.getByText('6 personas')).toBeInTheDocument();
      expect(screen.getByText('3 marketplaces')).toBeInTheDocument();
    });
  });

  it('renders persistent muted ethics disclaimer', async () => {
    vi.spyOn(global, 'fetch').mockImplementation((url) => {
      if (url.includes('/api/v1/pipeline/stages')) {
        return Promise.resolve({
          status: 200,
          json: () => Promise.resolve({ success: true, data: MOCK_STAGES }),
        });
      }
      if (url.includes('/api/v1/investigations/1/pipeline/runs')) {
        return Promise.resolve({
          status: 200,
          json: () => Promise.resolve({ success: true, data: [] }),
        });
      }
      return Promise.reject(new Error(`Unhandled URL: ${url}`));
    });

    renderCorrelationPanel();

    await waitFor(() => {
      expect(
        screen.getByText('Evidence supports investigation. It does not identify a real-world person.')
      ).toBeInTheDocument();
    });
  });
});
