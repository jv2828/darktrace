import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AppShell from '../components/AppShell';
import { AuthProvider } from '../context/AuthContext';
import { TOKEN_KEY, USER_KEY } from '../lib/api';

function renderAppShell(user) {
  sessionStorage.setItem(TOKEN_KEY, 'mock_token');
  sessionStorage.setItem(USER_KEY, JSON.stringify(user));

  vi.spyOn(global, 'fetch').mockImplementation(() =>
    Promise.resolve({
      status: 200,
      json: () =>
        Promise.resolve({
          success: true,
          data: user,
          error: null,
          meta: {},
        }),
    })
  );

  return render(
    <MemoryRouter>
      <AuthProvider>
        <AppShell />
      </AuthProvider>
    </MemoryRouter>
  );
}

describe('AppShell Sidebar Navigation', () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it('hides Users and System links for an investigator', async () => {
    renderAppShell({
      id: 2,
      username: 'investigator_alice',
      full_name: 'Alice Analyst',
      role: 'investigator',
    });

    expect(await screen.findByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Investigations')).toBeInTheDocument();

    expect(screen.queryByRole('link', { name: 'Users' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'System' })).not.toBeInTheDocument();
  });

  it('displays Users and System links for an administrator', async () => {
    renderAppShell({
      id: 1,
      username: 'admin_carol',
      full_name: 'Carol Administrator',
      role: 'admin',
    });

    expect(await screen.findByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Investigations')).toBeInTheDocument();

    expect(screen.getByRole('link', { name: 'Users' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'System' })).toBeInTheDocument();
  });
});

