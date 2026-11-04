import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import ProtectedRoute from '../components/ProtectedRoute';
import { AuthProvider } from '../context/AuthContext';
import { TOKEN_KEY, USER_KEY } from '../lib/api';

function renderWithRouter(initialEntry) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<div>Login Page Target</div>} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <div>Protected Dashboard View</div>
              </ProtectedRoute>
            }
          />
          <Route
            path="/users"
            element={
              <ProtectedRoute adminOnly>
                <div>Admin Users Management View</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
}

describe('ProtectedRoute Component', () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it('redirects unauthenticated user to /login', async () => {
    renderWithRouter('/dashboard');
    expect(await screen.findByText('Login Page Target')).toBeInTheDocument();
  });

  it('displays access restricted message when investigator accesses admin-only route', async () => {
    sessionStorage.setItem(TOKEN_KEY, 'investigator_token');
    sessionStorage.setItem(
      USER_KEY,
      JSON.stringify({ id: 2, username: 'bob', role: 'investigator' })
    );

    // Mock fetchMeApi during auth restore
    vi.spyOn(global, 'fetch').mockImplementation(() =>
      Promise.resolve({
        status: 200,
        json: () =>
          Promise.resolve({
            success: true,
            data: { id: 2, username: 'bob', role: 'investigator' },
            error: null,
            meta: {},
          }),
      })
    );

    renderWithRouter('/users');

    expect(await screen.findByText(/access restricted/i)).toBeInTheDocument();
    expect(
      screen.getByText(/you do not have administrative privileges/i)
    ).toBeInTheDocument();
    expect(screen.queryByText('Admin Users Management View')).not.toBeInTheDocument();
  });

  it('permits administrator to access admin-only route', async () => {
    sessionStorage.setItem(TOKEN_KEY, 'admin_token');
    sessionStorage.setItem(
      USER_KEY,
      JSON.stringify({ id: 1, username: 'admin', role: 'admin' })
    );

    vi.spyOn(global, 'fetch').mockImplementation(() =>
      Promise.resolve({
        status: 200,
        json: () =>
          Promise.resolve({
            success: true,
            data: { id: 1, username: 'admin', role: 'admin' },
            error: null,
            meta: {},
          }),
      })
    );

    renderWithRouter('/users');

    expect(await screen.findByText('Admin Users Management View')).toBeInTheDocument();
  });
});

