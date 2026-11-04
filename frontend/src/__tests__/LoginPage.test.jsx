import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import LoginPage from '../pages/LoginPage';
import { AuthProvider } from '../context/AuthContext';
import { TOKEN_KEY, USER_KEY } from '../lib/api';

const mockedNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockedNavigate,
  };
});

function renderLoginPage() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <LoginPage />
      </AuthProvider>
    </MemoryRouter>
  );
}

describe('LoginPage Component', () => {
  beforeEach(() => {
    sessionStorage.clear();
    mockedNavigate.mockReset();
    vi.restoreAllMocks();
  });

  it('displays client-side required validation error when submitting with empty fields', async () => {
    renderLoginPage();

    const submitButton = screen.getByRole('button', { name: /sign in/i });
    await userEvent.click(submitButton);

    expect(await screen.findByText(/username or email is required/i)).toBeInTheDocument();
  });

  it('displays backend error message when invalid credentials are provided', async () => {
    vi.spyOn(global, 'fetch').mockImplementation(() =>
      Promise.resolve({
        status: 401,
        json: () =>
          Promise.resolve({
            success: false,
            data: null,
            error: { code: 'INVALID_CREDENTIALS', message: 'Invalid credentials' },
            meta: {},
          }),
      })
    );

    renderLoginPage();

    const identifierInput = screen.getByLabelText(/username or email/i);
    const passwordInput = screen.getByPlaceholderText(/••••••••••••/i);
    const submitButton = screen.getByRole('button', { name: /sign in/i });

    await userEvent.type(identifierInput, 'bad_analyst');
    await userEvent.type(passwordInput, 'WrongPass123!');
    await userEvent.click(submitButton);

    expect(await screen.findByText(/invalid credentials/i)).toBeInTheDocument();
  });

  it('stores session tokens and navigates to dashboard on successful login', async () => {
    vi.spyOn(global, 'fetch').mockImplementation(() =>
      Promise.resolve({
        status: 200,
        json: () =>
          Promise.resolve({
            success: true,
            data: {
              access_token: 'valid_mock_jwt_token',
              token_type: 'bearer',
              expires_in: 3600,
              user: {
                id: 1,
                email: 'admin@darktrace.org',
                username: 'admin',
                full_name: 'Chief Admin',
                role: 'admin',
              },
            },
            error: null,
            meta: {},
          }),
      })
    );

    renderLoginPage();

    const identifierInput = screen.getByLabelText(/username or email/i);
    const passwordInput = screen.getByPlaceholderText(/••••••••••••/i);
    const submitButton = screen.getByRole('button', { name: /sign in/i });

    await userEvent.type(identifierInput, 'admin');
    await userEvent.type(passwordInput, 'CorrectPassword123!');
    await userEvent.click(submitButton);

    await waitFor(() => {
      expect(sessionStorage.getItem(TOKEN_KEY)).toBe('valid_mock_jwt_token');
      expect(JSON.parse(sessionStorage.getItem(USER_KEY)).username).toBe('admin');
      expect(mockedNavigate).toHaveBeenCalledWith('/dashboard', { replace: true });
    });
  });
});

