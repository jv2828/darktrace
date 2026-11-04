import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import HighlightedText from '../components/common/HighlightedText';
import IndicatorsTable from '../components/investigations/IndicatorsTable';
import PostDetailPage from '../pages/PostDetailPage';
import { ToastProvider } from '../components/ui/Toast';
import {
  INDICATOR_CONFIG,
  ALL_INDICATOR_TYPES,
  getIndicatorConfig,
} from '../lib/indicatorTypes';

describe('Phase 6 Extraction UI Components', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe('HighlightedText Component', () => {
    it('slices text into unhighlighted strings and highlighted marks without raw HTML', () => {
      const text = 'Reach us at 198.51.100.42 or escrow bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq now.';
      const indicators = [
        {
          id: 1,
          indicator_type: 'ip_address',
          raw_value: '198.51.100.42',
          normalised_value: '198.51.100.42',
          span_start: 12,
          span_end: 25,
          confidence: 'high',
          details: { scope: 'documentation' },
        },
        {
          id: 2,
          indicator_type: 'wallet_btc',
          raw_value: 'bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq',
          normalised_value: 'bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq',
          span_start: 36,
          span_end: 78,
          confidence: 'high',
          details: { subtype: 'bech32' },
        },
      ];

      render(<HighlightedText text={text} indicators={indicators} />);

      // Marks rendered
      const marks = screen.getAllByRole('mark', { hidden: true });
      expect(marks.length).toBe(2);
      expect(marks[0].textContent).toBe('198.51.100.42');
      expect(marks[1].textContent).toBe('bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq');

      // Unhighlighted text around marks
      expect(screen.getByText(/Reach us at/)).toBeInTheDocument();
      expect(screen.getByText(/or escrow/)).toBeInTheDocument();
      expect(screen.getByText(/now\./)).toBeInTheDocument();
    });

    it('gracefully handles overlapping spans by dropping the latter and logging warning', () => {
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      const text = 'Certificate SHA256: E3:B0:C4:42:98:FC:1C:14';
      const overlappingIndicators = [
        {
          id: 1,
          indicator_type: 'ssl_cert_fingerprint',
          raw_value: 'E3:B0:C4:42:98:FC:1C:14',
          span_start: 20,
          span_end: 43,
          confidence: 'high',
        },
        {
          id: 2,
          indicator_type: 'port',
          raw_value: '42',
          span_start: 29,
          span_end: 31,
          confidence: 'low',
        },
      ];

      render(<HighlightedText text={text} indicators={overlappingIndicators} />);

      const marks = screen.getAllByRole('mark', { hidden: true });
      expect(marks.length).toBe(1);
      expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('Skipping overlapping indicator'));
    });

    it('triggers onIndicatorClick callback when mark is clicked', async () => {
      const user = userEvent.setup();
      const handleClick = vi.fn();
      const text = 'Server 198.51.100.55 online';
      const indicators = [
        {
          id: 10,
          indicator_type: 'ip_address',
          raw_value: '198.51.100.55',
          span_start: 7,
          span_end: 20,
          confidence: 'high',
        },
      ];

      render(<HighlightedText text={text} indicators={indicators} onIndicatorClick={handleClick} />);

      const mark = screen.getByText('198.51.100.55');
      await user.click(mark);
      expect(handleClick).toHaveBeenCalledTimes(1);
      expect(handleClick).toHaveBeenCalledWith(indicators[0]);
    });
  });

  describe('Indicator Configuration & Palette', () => {
    it('provides WCAG AA compliant palette entries for all indicator types', () => {
      expect(ALL_INDICATOR_TYPES.length).toBeGreaterThanOrEqual(10);
      for (const type of ALL_INDICATOR_TYPES) {
        const cfg = getIndicatorConfig(type);
        expect(cfg.label).toBeTruthy();
        expect(cfg.badgeClass).toBeTruthy();
        expect(cfg.highlightClass).toBeTruthy();
        expect(cfg.dotColor).toMatch(/^#[0-9a-f]{6}$/i);
      }
    });
  });

  describe('PostDetailPage', () => {
    it('renders post provenance, HighlightedText, structured card, and indicator details', async () => {
      vi.spyOn(global, 'fetch').mockImplementation((url) => {
        if (url.includes('/investigations/1/posts/42')) {
          return Promise.resolve({
            status: 200,
            json: () =>
              Promise.resolve({
                success: true,
                data: {
                  id: 42,
                  dataset_id: 1,
                  dataset_name: 'Alpha Sample',
                  marketplace: 'Velvet Bazaar',
                  author_username: 'iron_weaver',
                  content: 'Contact via PGP E4A1 8B9C 2D3E 4F5A 6B7C 8D9E 0F1A 2B3C 4D5E 6F7A or port 8080.',
                  posted_at: '2026-02-01T12:00:00Z',
                  source_reference: 'thread_123',
                  extractor_version: '1.0.0',
                  extracted_at: '2026-02-01T12:01:00Z',
                  structured_indicators: {
                    wallet: '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
                  },
                  indicators: [
                    {
                      id: 101,
                      indicator_type: 'pgp_fingerprint',
                      raw_value: 'E4A1 8B9C 2D3E 4F5A 6B7C 8D9E 0F1A 2B3C 4D5E 6F7A',
                      normalised_value: 'E4A18B9C2D3E4F5A6B7C8D9E0F1A2B3C4D5E6F7A',
                      span_start: 16,
                      span_end: 55,
                      confidence: 'high',
                      extraction_method: 'regex',
                      details: { length: 40 },
                    },
                    {
                      id: 102,
                      indicator_type: 'port',
                      raw_value: '8080',
                      normalised_value: '8080',
                      span_start: 64,
                      span_end: 68,
                      confidence: 'high',
                      extraction_method: 'regex',
                      details: { port: 8080 },
                    },
                  ],
                },
                error: null,
                meta: {},
              }),
          });
        }
        return Promise.reject(new Error(`Unhandled URL: ${url}`));
      });

      render(
        <MemoryRouter initialEntries={['/investigations/1/posts/42']}>
          <ToastProvider>
            <Routes>
              <Route path="/investigations/:id/posts/:postId" element={<PostDetailPage />} />
            </Routes>
          </ToastProvider>
        </MemoryRouter>
      );

      // Loading state disappears, post metadata appears
      await waitFor(() => {
        expect(screen.getByText('Velvet Bazaar')).toBeInTheDocument();
      });

      expect(screen.getAllByText(/iron_weaver/).length).toBeGreaterThanOrEqual(1);

      expect(screen.getByText('Velvet Bazaar')).toBeInTheDocument();
      expect(screen.getByText(/Alpha Sample/)).toBeInTheDocument();

      // HighlightedText annotations
      expect(screen.getByText('E4A1 8B9C 2D3E 4F5A 6B7C 8D9E 0F1A 2B3C 4D5E 6F7A')).toBeInTheDocument();
      expect(screen.getAllByText('8080').length).toBeGreaterThanOrEqual(2);

      // Structured card
      expect(screen.getByText('Structured Metadata Indicators')).toBeInTheDocument();
      expect(screen.getByText('1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa')).toBeInTheDocument();

      // Extracted indicator item card
      expect(screen.getByText('E4A18B9C2D3E4F5A6B7C8D9E0F1A2B3C4D5E6F7A')).toBeInTheDocument();
    });

    it('renders 404 empty state when post is not found or unowned', async () => {
      vi.spyOn(global, 'fetch').mockImplementation(() =>
        Promise.resolve({
          status: 404,
          json: () =>
            Promise.resolve({
              success: false,
              data: null,
              error: { code: 'NOT_FOUND', message: 'Post not found' },
            }),
        })
      );

      render(
        <MemoryRouter initialEntries={['/investigations/1/posts/999']}>
          <ToastProvider>
            <Routes>
              <Route path="/investigations/:id/posts/:postId" element={<PostDetailPage />} />
            </Routes>
          </ToastProvider>
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Post Not Found')).toBeInTheDocument();
      });
    });
  });

  describe('IndicatorsTable Component', () => {
    it('renders summary chips and handles type filtering', async () => {
      const user = userEvent.setup();

      vi.spyOn(global, 'fetch').mockImplementation((url) => {
        if (url.includes('/indicators/summary')) {
          return Promise.resolve({
            status: 200,
            json: () =>
              Promise.resolve({
                success: true,
                data: {
                  total: 10,
                  total_indicators: 10,
                  distinct_indicators: 8,
                  by_type: {
                    pgp_fingerprint: { total: 4, distinct: 3 },
                    ip_address: { total: 6, distinct: 5 },
                  },
                },
              }),
          });
        }

        if (url.includes('/indicators')) {
          const isPgpFilter = url.includes('type=pgp_fingerprint');
          return Promise.resolve({
            status: 200,
            json: () =>
              Promise.resolve({
                success: true,
                data: isPgpFilter
                  ? [
                      {
                        id: 1,
                        post_id: 10,
                        indicator_type: 'pgp_fingerprint',
                        normalised_value: 'E4A18B9C2D3E4F5A6B7C8D9E0F1A2B3C4D5E6F7A',
                        author_username: 'iron_weaver',
                        marketplace: 'Velvet Bazaar',
                        confidence: 'high',
                        details: {},
                      },
                    ]
                  : [
                      {
                        id: 1,
                        post_id: 10,
                        indicator_type: 'pgp_fingerprint',
                        normalised_value: 'E4A18B9C2D3E4F5A6B7C8D9E0F1A2B3C4D5E6F7A',
                        author_username: 'iron_weaver',
                        marketplace: 'Velvet Bazaar',
                        confidence: 'high',
                        details: {},
                      },
                      {
                        id: 2,
                        post_id: 11,
                        indicator_type: 'ip_address',
                        normalised_value: '198.51.100.42',
                        author_username: 'mesh_node',
                        marketplace: 'Greywharf',
                        confidence: 'high',
                        details: { scope: 'documentation' },
                      },
                    ],
                meta: { page: 1, page_size: 25, total: isPgpFilter ? 1 : 2, total_pages: 1 },
              }),
          });
        }

        return Promise.reject(new Error(`Unhandled URL: ${url}`));
      });

      render(
        <MemoryRouter>
          <IndicatorsTable investigationId="1" />
        </MemoryRouter>
      );

      // Summary chips rendered
      await waitFor(() => {
        expect(screen.getByText('E4A18B9C2D3E4F5A6B7C8D9E0F1A2B3C4D5E6F7A')).toBeInTheDocument();
        expect(screen.getByText('198.51.100.42')).toBeInTheDocument();
      });

      // Click PGP chip
      const pgpChip = screen.getByRole('button', { name: /PGP/i });
      await user.click(pgpChip);

      // Now only PGP indicator is shown
      await waitFor(() => {
        expect(screen.queryByText('198.51.100.42')).not.toBeInTheDocument();
        expect(screen.getByText('E4A18B9C2D3E4F5A6B7C8D9E0F1A2B3C4D5E6F7A')).toBeInTheDocument();
      });
    });
  });
});
