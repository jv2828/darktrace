import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  TOKEN_KEY,
  USER_KEY,
  NOTICE_KEY,
  loginApi,
  fetchMeApi,
} from '../lib/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => {
    return typeof sessionStorage !== 'undefined' ? sessionStorage.getItem(TOKEN_KEY) : null;
  });

  const [user, setUser] = useState(() => {
    if (typeof sessionStorage !== 'undefined') {
      const stored = sessionStorage.getItem(USER_KEY);
      if (stored) {
        try {
          return JSON.parse(stored);
        } catch {
          return null;
        }
      }
    }
    return null;
  });

  const [isLoading, setIsLoading] = useState(true);

  // Restore and verify session from backend on page reload
  useEffect(() => {
    let isMounted = true;

    async function restoreSession() {
      const activeToken = sessionStorage.getItem(TOKEN_KEY);
      if (!activeToken) {
        if (isMounted) setIsLoading(false);
        return;
      }

      try {
        const freshUser = await fetchMeApi();
        if (isMounted) {
          setUser(freshUser);
          sessionStorage.setItem(USER_KEY, JSON.stringify(freshUser));
        }
      } catch (err) {
        // If token expired or invalid, clear stored session
        if (isMounted) {
          setToken(null);
          setUser(null);
          sessionStorage.removeItem(TOKEN_KEY);
          sessionStorage.removeItem(USER_KEY);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    restoreSession();

    return () => {
      isMounted = false;
    };
  }, []);

  const login = useCallback(async (identifier, password) => {
    const data = await loginApi(identifier, password);
    const receivedToken = data.access_token;
    const receivedUser = data.user;

    setToken(receivedToken);
    setUser(receivedUser);

    sessionStorage.setItem(TOKEN_KEY, receivedToken);
    sessionStorage.setItem(USER_KEY, JSON.stringify(receivedUser));
    sessionStorage.removeItem(NOTICE_KEY);

    return receivedUser;
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(USER_KEY);
  }, []);

  const value = {
    token,
    user,
    isAuthenticated: Boolean(token && user),
    isAdmin: user?.role === 'admin',
    isLoading,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

