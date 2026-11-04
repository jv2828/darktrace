import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { NOTICE_KEY } from '../lib/api';
import Card from '../components/ui/Card';
import Input from '../components/ui/Input';
import Button from '../components/ui/Button';
import Logo from '../components/ui/Logo';

function MatrixBackground() {
  const canvasRef = useRef(null);

  useEffect(() => {
    // Respect reduced motion preference
    const prefersReducedMotion =
      typeof window !== 'undefined' &&
      window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    // Guard against environments where getContext is null (e.g. jsdom in Vitest)
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId;
    let lastTime = 0;
    const fps = 20; // 20fps frame rate cap
    const interval = 1000 / fps;

    // Monospace hex digits 0-9 A-F, binary 0/1, and half-width katakana
    const characters = '0123456789ABCDEF0101ｦｱｳｴｵｶｷｹｺｻｼｽｾｿﾀﾂﾃﾅﾆﾇﾈﾊﾋﾎﾏﾐﾑﾒﾓﾔﾕﾗﾘﾜ'.split('');
    const fontSize = 14;
    let columns = 0;
    let drops = [];

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      columns = Math.max(1, Math.floor(canvas.width / fontSize));
      drops = Array.from({ length: columns }, () => Math.floor(Math.random() * -50));
    };

    resize();
    window.addEventListener('resize', resize);

    const render = (currentTime) => {
      animationFrameId = requestAnimationFrame(render);

      // Pause rendering while tab is in the background
      if (document.hidden) return;

      const delta = currentTime - lastTime;
      if (delta < interval) return;
      lastTime = currentTime - (delta % interval);

      // Soft fading trail
      ctx.fillStyle = 'rgba(2, 6, 23, 0.25)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      ctx.fillStyle = '#38bdf8'; // dim sky-blue
      ctx.font = `${fontSize}px monospace`;

      for (let i = 0; i < drops.length; i++) {
        const text = characters[Math.floor(Math.random() * characters.length)];
        const x = i * fontSize;
        const y = drops[i] * fontSize;

        if (y > 0) {
          ctx.fillText(text, x, y);
        }

        if (y > canvas.height && Math.random() > 0.985) {
          drops[i] = 0;
        }
        drops[i]++;
      }
    };

    animationFrameId = requestAnimationFrame(render);

    const handleVisibilityChange = () => {
      if (!document.hidden) {
        lastTime = performance.now();
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', resize);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none z-0"
      style={{ opacity: 0.15 }}
      aria-hidden="true"
    />
  );
}

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
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center p-4 selection:bg-slate-800 relative overflow-hidden">
      {/* Subtle Terminal Matrix Canvas */}
      <MatrixBackground />

      {/* Faint Scanlines Overlay */}
      <div className="cyber-scanlines fixed inset-0 pointer-events-none z-0" aria-hidden="true" />

      <div className="max-w-md w-full space-y-6 relative z-10">
        {/* Brand Header */}
        <div className="text-center space-y-3">
          <div className="flex justify-center">
            <Logo size="xl" />
          </div>
          <div className="space-y-1">
            <h1
              className="glitch-title text-3xl font-extrabold tracking-widest text-slate-100 uppercase"
              data-text="DARKTRACE"
            >
              DARKTRACE
            </h1>
            <p className="text-sm text-slate-400">
              <span className="typewriter-text inline-block">
                Dark web threat-intelligence and actor correlation.
              </span>
            </p>
          </div>
        </div>

        {/* Login Card */}
        <Card className="login-card-animated p-8 border-slate-800 bg-slate-900 shadow-xl relative z-10">
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

