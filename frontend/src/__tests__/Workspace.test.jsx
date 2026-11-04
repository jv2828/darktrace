import React from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import InvestigationWorkspacePage from '../pages/InvestigationWorkspacePage';
import ActorProfilePage from '../pages/ActorProfilePage';
import { ToastProvider } from '../components/ui/Toast';

const MOCK_INVESTIGATION = {
  id: 1,
  title: 'Alpha Threat Syndicate',
  description: 'Infiltration and analysis of darknet narcotics vendors',
  status: 'active',
  created_by: { id: 10, username: 'lead_investigator' },
  counts: { posts: 42, indicators: 18 },
};

const MOCK_DATASETS = [
  {
    id: 101,
    name: 'Alpha Benchmark Dataset',
    source_type: 'sample',
    post_count: 42,
    added_at: '2026-11-04T12:00:00Z',
  },
];

const MOCK_STAGES = [
  { name: 'crypto_matching', label: 'Cryptographic Matching', description: 'Keys & Wallets', available: true },
  { name: 'infrastructure_matching', label: 'Infrastructure Matching', description: 'Domains & Mirrors', available: true },
  { name: 'stylometry', label: 'Stylometric Analysis', description: 'N-grams & POS', available: true },
  { name: 'behaviour', label: 'Behavioral Profiling', description: 'Diurnal patterns', available: true },
  { name: 'scoring', label: 'Heuristic Scoring', description: 'Combined strength', available: true },
];

const MOCK_RUN = {
  id: 77,
  investigation_id: 1,
  status: 'completed',
  started_at: '2026-11-04T12:00:00Z',
  finished_at: '2026-11-04T12:00:05Z',
  pairs_scored: 4,
  stages: [
    { stage: 'crypto_matching', status: 'completed', summary: {} },
    { stage: 'infrastructure_matching', status: 'completed', summary: {} },
    { stage: 'stylometry', status: 'completed', summary: {} },
    { stage: 'behaviour', status: 'completed', summary: {} },
    { stage: 'scoring', status: 'completed', summary: {} },
  ],
};

const MOCK_CORRELATIONS = {
  items: [
    {
      id: 501,
      actors: {
        actor_a: { id: 21, username: 'shadow_vendor', marketplace: 'SilkRoad4' },
        actor_b: { id: 22, username: 'ghost_courier', marketplace: 'DarkBazaar' },
      },
      combined_score: 0.885,
      level: 'strong',
      coverage: 0.9,
      contradiction_count: 0,
      dimension_scores: {
        cryptographic: { score: 0.95 },
        infrastructure: { score: 0.82 },
      },
    },
  ],
  total: 1,
  run_id: 77,
};

const MOCK_ACTORS = [
  {
    id: 21,
    actor_id: 21,
    username: 'shadow_vendor',
    marketplace: 'SilkRoad4',
    post_count: 24,
    best_correlated_partner_score: 0.885,
    stylometry: {
      features: {
        mean_sentence_length: 14.2,
        mean_word_length: 4.8,
        digit_ratio: 0.02,
        uppercase_letter_ratio: 0.05,
        'punct_,': 1.2,
      },
    },
    tfidf_summary: [
      { term: 'dispatch', tfidf: 0.42 },
      { term: 'stealth pack', tfidf: 0.38 },
    ],
    behaviour: {
      hourly_distribution: Array(24).fill(0.04),
      daily_distribution: Array(7).fill(0.14),
    },
  },
  {
    id: 22,
    actor_id: 22,
    username: 'ghost_courier',
    marketplace: 'DarkBazaar',
    post_count: 18,
    best_correlated_partner_score: 0.885,
    stylometry: {
      features: {
        mean_sentence_length: 12.5,
        mean_word_length: 5.1,
        digit_ratio: 0.01,
        uppercase_letter_ratio: 0.03,
        'punct_.': 2.4,
      },
    },
    tfidf_summary: [
      { term: 'courier drop', tfidf: 0.35 },
      { term: 'clean escrow', tfidf: 0.29 },
    ],
    behaviour: {
      hourly_distribution: Array(24).fill(0.04),
      daily_distribution: Array(7).fill(0.14),
    },
  },
];

const MOCK_REPORTS = [
  {
    id: 901,
    file_name: 'DARKTRACE_Dossier_Case_1_Run_77.pdf',
    format: 'pdf',
    file_size_bytes: 45200,
    created_at: '2026-11-04T12:05:00Z',
  },
];

const MOCK_ACTOR_PROFILE = {
  actor_id: 21,
  primary_username: 'shadow_vendor',
  marketplace: 'SilkRoad4',
  post_count: 24,
  first_seen: '2026-10-01T10:00:00Z',
  last_seen: '2026-11-04T11:00:00Z',
  aliases: ['sv_dispatch', 'vendor_shadow'],
  marketplaces: ['SilkRoad4', 'DarkBazaar'],
  pgp_identifiers: ['4A8B9C1D2E3F4051'],
  wallet_identifiers: ['bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq'],
  infrastructure_indicators: ['shadowvendor7xky.onion'],
  behaviour_summary: {
    active_hour_window_str: '14:00-22:00 UTC',
    peak_hour: 18,
    posts_per_week: 6.2,
    total_posts: 24,
    sufficiency: 'sufficient',
  },
  stylometry_summary: {
    avg_sentence_len: 14.8,
    avg_word_len: 4.82,
    punctuation_rate: 0.045,
    uppercase_rate: 0.032,
  },
  recent_posts: [
    {
      id: 301,
      title: 'PGP key transition announcement',
      marketplace: 'SilkRoad4',
      posted_at: '2026-11-04T10:30:00Z',
      content_preview: 'New key active for escrow transactions. Verified on mirrors.',
    },
  ],
  contradictions: [],
  possible_related_personas: [
    {
      actor_id: 22,
      username: 'ghost_courier',
      marketplace: 'DarkBazaar',
      score: 0.885,
      level: 'strong',
      coverage: 0.9,
      top_explanation: 'Identical PGP key fingerprint and matching temporal active window.',
    },
  ],
};

function setupMockFetch() {
  return vi.spyOn(global, 'fetch').mockImplementation((url, opts) => {
    const urlStr = String(url);
    const _method = opts?.method || 'GET';

    if (urlStr.includes('/api/v1/investigations/1/actors/21')) {
      return Promise.resolve({
        status: 200,
        json: () => Promise.resolve({ success: true, data: MOCK_ACTOR_PROFILE }),
      });
    }

    if (urlStr.includes('/api/v1/investigations/1/analysis/actors') || urlStr.includes('/api/v1/investigations/1/actors')) {
      return Promise.resolve({
        status: 200,
        json: () => Promise.resolve({ success: true, data: MOCK_ACTORS }),
      });
    }

    if (urlStr.includes('/api/v1/investigations/1/correlations')) {
      return Promise.resolve({
        status: 200,
        json: () => Promise.resolve({ success: true, data: MOCK_CORRELATIONS }),
      });
    }

    if (urlStr.includes('/api/v1/investigations/1/reports')) {
      return Promise.resolve({
        status: 200,
        json: () => Promise.resolve({ success: true, data: MOCK_REPORTS }),
      });
    }

    if (urlStr.includes('/api/v1/investigations/1/datasets')) {
      return Promise.resolve({
        status: 200,
        json: () => Promise.resolve({ success: true, data: MOCK_DATASETS }),
      });
    }

    if (urlStr.includes('/api/v1/investigations/1/pipeline/runs')) {
      return Promise.resolve({
        status: 200,
        json: () => Promise.resolve({ success: true, data: [MOCK_RUN] }),
      });
    }

    if (urlStr.includes('/api/v1/pipeline/stages')) {
      return Promise.resolve({
        status: 200,
        json: () => Promise.resolve({ success: true, data: MOCK_STAGES }),
      });
    }

    if (urlStr.includes('/api/v1/investigations/1')) {
      return Promise.resolve({
        status: 200,
        json: () => Promise.resolve({ success: true, data: MOCK_INVESTIGATION }),
      });
    }

    return Promise.resolve({
      status: 200,
      json: () => Promise.resolve({ success: true, data: {} }),
    });
  });
}

describe('Investigation Workspace & Forensic Tabs (Phase 9)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    setupMockFetch();
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  it('renders all 7 investigation workspace tabs and case header metrics', async () => {
    render(
      <MemoryRouter initialEntries={['/investigations/1']}>
        <ToastProvider>
          <Routes>
            <Route path="/investigations/:id" element={<InvestigationWorkspacePage />} />
          </Routes>
        </ToastProvider>
      </MemoryRouter>
    );

    // Header metrics
    await waitFor(() => {
      expect(screen.getByText('Alpha Threat Syndicate')).toBeInTheDocument();
    });
    expect(screen.getByText('lead_investigator')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText('18')).toBeInTheDocument();

    // Verify all 7 tabs exist
    expect(screen.getByRole('button', { name: /overview/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /evidence graph/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /chronology/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /infrastructure/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /behaviour/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /stylometry/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /dossier/i })).toBeInTheDocument();
  });

  it('overview tab displays linked personas with heuristic score bar and non-probability notice', async () => {
    render(
      <MemoryRouter initialEntries={['/investigations/1?tab=overview']}>
        <ToastProvider>
          <Routes>
            <Route path="/investigations/:id" element={<InvestigationWorkspacePage />} />
          </Routes>
        </ToastProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getAllByText('shadow_vendor').length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getAllByText('ghost_courier').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('0.89').length).toBeGreaterThanOrEqual(1);

    // Check non-probability notice
    expect(
      screen.getByText(/Heuristic Evidence Strengths — Not Identity Probabilities/i)
    ).toBeInTheDocument();
  });

  it('navigates to dossier tab and shows export controls and dossier archive', async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={['/investigations/1?tab=overview']}>
        <ToastProvider>
          <Routes>
            <Route path="/investigations/:id" element={<InvestigationWorkspacePage />} />
          </Routes>
        </ToastProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /dossier/i })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /dossier/i }));

    await waitFor(() => {
      expect(screen.getByText(/Generate Forensic Dossier Export/i)).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /generate dossier/i })).toBeInTheDocument();
    expect(screen.getByText('DARKTRACE_Dossier_Case_1_Run_77.pdf')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /download/i })).toBeInTheDocument();
  });

  it('renders actor profile page with possible related personas and heuristic disclaimer', async () => {
    render(
      <MemoryRouter initialEntries={['/investigations/1/actors/21']}>
        <ToastProvider>
          <Routes>
            <Route path="/investigations/:id/actors/:actorId" element={<ActorProfilePage />} />
          </Routes>
        </ToastProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('shadow_vendor');
    });

    // Known aliases and marketplaces
    expect(screen.getByText('sv_dispatch')).toBeInTheDocument();
    expect(screen.getByText('vendor_shadow')).toBeInTheDocument();

    // Cryptographic & infrastructure indicators
    expect(screen.getByText('4A8B9C1D2E3F4051')).toBeInTheDocument();
    expect(screen.getByText('bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq')).toBeInTheDocument();
    expect(screen.getByText('shadowvendor7xky.onion')).toBeInTheDocument();

    // Possible Related Personas section
    expect(screen.getByText(/Possible Related Personas/i)).toBeInTheDocument();
    expect(screen.getByText('ghost_courier')).toBeInTheDocument();
    expect(screen.getByText(/Heuristic Correlation Notice/i)).toBeInTheDocument();
    expect(screen.getByText(/definitive identity confirmation/i)).toBeInTheDocument();
  });

  it('renders stylometry tab with linguistic feature comparison and TF-IDF terms without crashing', async () => {
    render(
      <MemoryRouter initialEntries={['/investigations/1?tab=stylometry']}>
        <ToastProvider>
          <Routes>
            <Route path="/investigations/:id" element={<InvestigationWorkspacePage />} />
          </Routes>
        </ToastProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Linguistic Feature Comparison/i)).toBeInTheDocument();
    });

    // Check that distinctive vocabulary section is rendered with TF-IDF terms
    expect(screen.getByText(/Distinctive Vocabulary & TF-IDF Terms/i)).toBeInTheDocument();
    expect(screen.getByText('dispatch')).toBeInTheDocument();
    expect(screen.getByText('stealth pack')).toBeInTheDocument();
    expect(screen.getByText(/Interactive Stylometric Sample Comparator/i)).toBeInTheDocument();
  });
});
