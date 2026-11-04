import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import DashboardPage from '../pages/DashboardPage';
import { ToastProvider } from '../components/ui/Toast';

function renderDashboardPage() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <DashboardPage />
      </ToastProvider>
    </MemoryRouter>
  );
}

describe('DashboardPage Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders aggregate metrics and recent lists from API', async () => {
    vi.spyOn(global, 'fetch').mockImplementation((url) => {
      if (url.includes('/dashboard/summary')) {
        return Promise.resolve({
          status: 200,
          json: () =>
            Promise.resolve({
              success: true,
              data: {
                totals: {
                  investigations: 4,
                  posts: 120,
                  indicators: 85,
                  potential_linkages: 12,
                },
                recent_investigations: [
                  { id: 1, title: 'Operation Nightshade', status: 'processing', created_at: '2026-11-04T10:00:00Z' },
                ],
                recent_correlation_activity: [
                  {
                    id: 101,
                    investigation_id: 1,
                    investigation_title: 'Operation Nightshade',
                    status: 'completed',
                    started_at: '2026-11-04T10:05:00Z',
                    finished_at: '2026-11-04T10:06:00Z',
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

    renderDashboardPage();

    expect(await screen.findByText('4')).toBeInTheDocument();
    expect(screen.getByText('120')).toBeInTheDocument();
    expect(screen.getByText('85')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();

    expect(screen.getAllByText('Operation Nightshade')).toHaveLength(2);
    expect(screen.getByText(/run #101/i)).toBeInTheDocument();
    expect(
      screen.getByText(/potential linkages are heuristic evidence scores for investigation/i)
    ).toBeInTheDocument();
  });

  it('displays empty states when all metric counters are zero and lists are empty', async () => {
    vi.spyOn(global, 'fetch').mockImplementation((url) => {
      if (url.includes('/dashboard/summary')) {
        return Promise.resolve({
          status: 200,
          json: () =>
            Promise.resolve({
              success: true,
              data: {
                totals: {
                  investigations: 0,
                  posts: 0,
                  indicators: 0,
                  potential_linkages: 0,
                },
                recent_investigations: [],
                recent_correlation_activity: [],
              },
              error: null,
              meta: {},
            }),
        });
      }
      return Promise.reject(new Error(`Unhandled URL: ${url}`));
    });

    renderDashboardPage();

    // Four zeros for each stat card
    const zeros = await screen.findAllByText('0');
    expect(zeros).toHaveLength(4);

    expect(screen.getByText('No investigations yet')).toBeInTheDocument();
    expect(screen.getByText(/no pipeline runs recorded/i)).toBeInTheDocument();
  });
});
