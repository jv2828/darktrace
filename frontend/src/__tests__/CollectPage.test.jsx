import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import CollectPage from '../pages/CollectPage';
import { ToastProvider } from '../components/ui/Toast';

function renderCollectPage(investigationId = '1') {
  return render(
    <MemoryRouter initialEntries={[`/investigations/${investigationId}/collect`]}>
      <ToastProvider>
        <Routes>
          <Route path="/investigations/:id/collect" element={<CollectPage />} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>
  );
}

describe('CollectPage Component (Phase 5 Ingestion)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders sample benchmark datasets and handles loading into investigation', async () => {
    const user = userEvent.setup();

    vi.spyOn(global, 'fetch').mockImplementation((url, opts) => {
      const method = opts?.method || 'GET';

      if (url.endsWith('/investigations/1') && method === 'GET') {
        return Promise.resolve({
          status: 200,
          json: () =>
            Promise.resolve({
              success: true,
              data: { id: 1, title: 'Operation Nightshade', status: 'draft', created_by: { id: 10, username: 'analyst' } },
              error: null,
              meta: {},
            }),
        });
      }

      if (url.includes('/datasets/samples') && method === 'GET') {
        return Promise.resolve({
          status: 200,
          json: () =>
            Promise.resolve({
              success: true,
              data: [
                {
                  key: 'alpha',
                  name: 'Alpha Benchmark Sample',
                  description: 'Synthetic marketplace chatter with ground truth.',
                  version: 1,
                  post_count: 180,
                  marketplace_count: 4,
                  persona_count: 10,
                  loaded: false,
                },
              ],
              error: null,
              meta: {},
            }),
        });
      }

      if (url.includes('/investigations/1/datasets/samples/alpha') && method === 'POST') {
        return Promise.resolve({
          status: 200,
          json: () =>
            Promise.resolve({
              success: true,
              data: {
                dataset_id: 42,
                dataset_name: 'Sample: Alpha Benchmark Sample (v1)',
                imported: 180,
                new_actors: 10,
                new_marketplaces: 4,
              },
              error: null,
              meta: {},
            }),
        });
      }

      return Promise.reject(new Error(`Unhandled URL: ${url} (method: ${method})`));
    });

    renderCollectPage('1');

    // Verify sample card rendered
    expect(await screen.findByText('Alpha Benchmark Sample')).toBeInTheDocument();
    expect(screen.getByText('180')).toBeInTheDocument(); // post count
    expect(screen.getByText('Available')).toBeInTheDocument();

    const loadBtn = screen.getByRole('button', { name: /load into case/i });
    await user.click(loadBtn);

    // Verify success banner appears
    expect(await screen.findByText(/attached to investigation/i)).toBeInTheDocument();
  });

  it('validates file upload and renders ValidationSummary, PreviewTable, and dynamic import button label', async () => {
    const user = userEvent.setup();

    vi.spyOn(global, 'fetch').mockImplementation((url, opts) => {
      const method = opts?.method || 'GET';

      if (url.endsWith('/investigations/1') && method === 'GET') {
        return Promise.resolve({
          status: 200,
          json: () =>
            Promise.resolve({
              success: true,
              data: { id: 1, title: 'Operation Nightshade', status: 'draft', created_by: { id: 10, username: 'analyst' } },
              error: null,
              meta: {},
            }),
        });
      }

      if (url.includes('/investigations/1/ingest/file/preview') && method === 'POST') {
        return Promise.resolve({
          status: 200,
          json: () =>
            Promise.resolve({
              success: true,
              data: {
                file_info: { filename: 'intel.csv', size_bytes: 512, format: 'csv' },
                summary: {
                  total: 3,
                  valid: 1,
                  valid_with_warnings: 1,
                  duplicates: 0,
                  invalid: 1,
                },
                rows: [
                  {
                    row_number: 1,
                    status: 'valid',
                    marketplace: 'Velvet Bazaar',
                    username: 'iron_weaver',
                    timestamp: '2026-02-01T12:00:00Z',
                    content_excerpt: 'Escrow confirmed for batch #100.',
                    errors: [],
                    warnings: [],
                  },
                  {
                    row_number: 2,
                    status: 'valid_with_warnings',
                    marketplace: 'Greywharf',
                    username: 'dusk_merchant',
                    timestamp: '2026-02-01T13:00:00Z',
                    content_excerpt: 'Notice without explicit timezone.',
                    errors: [],
                    warnings: ['timezone assumed UTC'],
                  },
                  {
                    row_number: 3,
                    status: 'invalid',
                    marketplace: 'V',
                    username: 'bad_user',
                    timestamp: null,
                    content_excerpt: 'Too short marketplace name.',
                    errors: ['Marketplace name must be between 2 and 100 characters'],
                    warnings: [],
                  },
                ],
                truncated: false,
              },
              error: null,
              meta: {},
            }),
        });
      }

      if (url.includes('/investigations/1/ingest/file/commit') && method === 'POST') {
        return Promise.resolve({
          status: 201,
          json: () =>
            Promise.resolve({
              success: true,
              data: {
                dataset_id: 99,
                dataset_name: 'CSV upload: intel.csv',
                imported: 2,
                skipped_duplicates: 0,
                skipped_invalid: 1,
                new_actors: 2,
                new_marketplaces: 2,
              },
              error: null,
              meta: {},
            }),
        });
      }

      return Promise.reject(new Error(`Unhandled URL: ${url} (method: ${method})`));
    });

    renderCollectPage('1');

    // Switch to File Upload tab
    const fileTabBtn = await screen.findByRole('button', { name: /batch file upload/i });
    await user.click(fileTabBtn);

    // Pick file
    const fileInput = document.getElementById('file-upload-input');
    const fakeFile = new File(['Marketplace,Username,Content\n'], 'intel.csv', { type: 'text/csv' });
    await user.upload(fileInput, fakeFile);

    // Click Validate File
    const validateBtn = screen.getByRole('button', { name: /validate file/i });
    await user.click(validateBtn);

    // Check ValidationSummary counts
    expect(await screen.findByText('Total: 3')).toBeInTheDocument();
    expect(screen.getByText('Valid: 1')).toBeInTheDocument();
    expect(screen.getByText('Warnings: 1')).toBeInTheDocument();
    expect(screen.getByText('Invalid: 1')).toBeInTheDocument();

    // Check color-and-text badges in preview table
    expect(screen.getByText('VALID')).toBeInTheDocument();
    expect(screen.getByText('WARNING')).toBeInTheDocument();
    expect(screen.getByText('INVALID')).toBeInTheDocument();
    expect(screen.getByText(/Marketplace name must be between 2 and 100 characters/i)).toBeInTheDocument();

    // Dynamic import button reflects 1 valid + 1 warning = 2 valid rows
    const commitBtn = screen.getByRole('button', { name: /import 2 valid rows/i });
    expect(commitBtn).toBeEnabled();

    // Commit file
    await user.click(commitBtn);

    // Check success state
    expect(await screen.findByText('Dataset Ingested Successfully')).toBeInTheDocument();
    expect(screen.getByText(/Imported 2 posts into dataset/i)).toBeInTheDocument();
  });
});
