import React, { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Badge from './ui/Badge';
import Button from './ui/Button';

export default function AppShell() {
  const { user, isAdmin, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  function handleLogout() {
    logout();
    navigate('/login');
  }

  const navItems = [
    { label: 'Dashboard', path: '/dashboard' },
    { label: 'Investigations', path: '/investigations' },
  ];

  if (isAdmin) {
    navItems.push(
      { label: 'Users', path: '/users' },
      { label: 'System', path: '/system' }
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col md:flex-row font-sans">
      {/* Mobile Top Header */}
      <div className="md:hidden flex items-center justify-between px-4 py-3 bg-slate-900 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <span className="font-bold tracking-wider text-slate-100 text-sm">DARKTRACE</span>
          <Badge variant={user?.role || 'neutral'}>{user?.role || 'user'}</Badge>
        </div>
        <button
          type="button"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="p-1.5 rounded bg-slate-800 text-slate-300 hover:text-slate-100 border border-slate-700 cursor-pointer"
          aria-label="Toggle navigation menu"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            {mobileMenuOpen ? (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>
      </div>

      {/* Sidebar Navigation */}
      <aside
        className={`${
          mobileMenuOpen ? 'block' : 'hidden'
        } md:block md:w-64 bg-slate-900/95 border-r border-slate-800 flex flex-col justify-between shrink-0 z-40`}
      >
        <div>
          {/* Logo Brand Header */}
          <div className="hidden md:flex items-center justify-between p-6 border-b border-slate-800">
            <div>
              <div className="text-base font-bold tracking-wider text-slate-100">DARKTRACE</div>
              <div className="text-[11px] text-slate-400 font-mono mt-0.5">Threat Intelligence</div>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="p-4 space-y-1">
            {navItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={() => setMobileMenuOpen(false)}
                className={({ isActive }) =>
                  `flex items-center px-3 py-2 text-sm rounded font-medium transition-colors ${
                    isActive
                      ? 'bg-slate-800 text-slate-100 border border-slate-700'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>

        {/* User Card & Logout in Sidebar Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/40">
          <div className="flex items-center justify-between mb-3">
            <div className="truncate mr-2">
              <div className="text-xs font-medium text-slate-200 truncate">
                {user?.full_name || user?.username}
              </div>
              <div className="text-[11px] font-mono text-slate-400 truncate">
                {user?.email}
              </div>
            </div>
            <Badge variant={user?.role || 'neutral'}>{user?.role || 'user'}</Badge>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleLogout}
            className="w-full justify-center text-slate-400 hover:text-rose-300"
          >
            Sign Out
          </Button>
        </div>
      </aside>

      {/* Main Content Pane */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Desktop Topbar */}
        <header className="hidden md:flex items-center justify-between px-8 py-4 bg-slate-900/60 border-b border-slate-800">
          <div className="text-xs text-slate-400 font-mono">
            College Cybersecurity Lab Project &bull; Strictly Synthetic Data
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-xs">
              <span className="text-slate-300 font-medium">{user?.full_name || user?.username}</span>
              <Badge variant={user?.role || 'neutral'}>{user?.role}</Badge>
            </div>
            <Button variant="secondary" size="sm" onClick={handleLogout}>
              Logout
            </Button>
          </div>
        </header>

        {/* Content Body Container */}
        <main className="flex-1 p-6 sm:p-8 max-w-5xl w-full mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

