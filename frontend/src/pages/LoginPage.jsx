import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { NOTICE_KEY } from '../lib/api';
import Card from '../components/ui/Card';
import Input from '../components/ui/Input';
import Button from '../components/ui/Button';

export default function LoginPage() {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState(null);
  const [sessionNotice, setSessionNotice] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  useEffect(() => {
    const notice = sessionStorage.getItem(NOTICE_KEY);
    if (notice) {
      setSessionNotice(notice);
      sessionStorage.removeItem(NOTICE_KEY);
    }
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    const cleanIdentifier = identifier.trim();

    if (!cleanIdentifier) {
      setError('Username or email is required.');
      return;
    }

    if (!password) {
      setError('Password is required.');
      return;
    }

    setSubmitting(true);
    setError(null);
    setSessionNotice(null);

    try {
      await login(cleanIdentifier, password);
      const destination = location.state?.from?.pathname || '/dashboard';
      navigate(destination, { replace: true });
    } catch (err) {
      setError(err.message || 'Authentication failed. Please verify your credentials.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center p-4 selection:bg-slate-800">
      <div className="max-w-md w-full space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <h1 className="text-3xl font-extrabold tracking-widest text-slate-100 uppercase">
            DARKTRACE
          </h1>
          <p className="text-sm text-slate-400">
            Dark web threat-intelligence and actor correlation.
          </p>
        </div>

        {/* Login Card */}
        <Card className="p-8 border-slate-800 bg-slate-900 shadow-xl">
          <form onSubmit={handleSubmit} className="space-y-5" noValidate>
            {/* Session Expiry Notice */}
            {sessionNotice && (
              <div className="p-3 rounded bg-amber-950/40 border border-amber-800/60 text-amber-200 text-xs">
                {sessionNotice}
              </div>
            )}

            {/* Error Message */}
            {error && (
              <div
                role="alert"
                className="p-3 rounded bg-rose-950/40 border border-rose-900/60 text-rose-200 text-xs"
              >
                {error}
              </div>
            )}

            <Input
              label="Username or Email"
              id="login-identifier"
              type="text"
              placeholder="e.g. analyst@darktrace.org or username"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              disabled={submitting}
              autoFocus
              required
            />

            <div className="w-full space-y-1.5">
              <div className="flex items-center justify-between">
                <label
                  htmlFor="login-password"
                  className="block text-xs font-medium text-slate-300"
                >
                  Password <span className="text-rose-400">*</span>
                </label>
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="text-xs text-slate-400 hover:text-slate-200 cursor-pointer"
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
              <input
                id="login-password"
                type={showPassword ? 'text' : 'password'}
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={submitting}
                required
                className="w-full px-3 py-2 text-sm bg-slate-950 border border-slate-800 rounded text-slate-100 placeholder:text-slate-500 focus:outline-hidden focus:border-sky-400"
              />
            </div>

            <Button
              type="submit"
              variant="primary"
              loading={submitting}
              className="w-full justify-center py-2.5 mt-2"
            >
              Sign In
            </Button>
          </form>
        </Card>

        {/* Security / Compliance Disclaimer */}
        <p className="text-center text-xs text-slate-400 max-w-sm mx-auto leading-relaxed">
          Authorised use with fictional or authorised data only.
        </p>
      </div>
    </div>
  );
}

