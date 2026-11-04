import React from 'react';
import { Navigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Spinner from './ui/Spinner';
import Card from './ui/Card';
import Button from './ui/Button';

export default function ProtectedRoute({ children, adminOnly = false }) {
  const { isAuthenticated, isAdmin, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center gap-3">
        <Spinner size="lg" />
        <span className="text-xs text-slate-400 font-mono">Verifying DARKTRACE session...</span>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (adminOnly && !isAdmin) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center p-6">
        <Card className="max-w-md w-full text-center space-y-4 p-8">
          <div className="w-10 h-10 rounded-full bg-rose-950/80 border border-rose-800 text-rose-300 flex items-center justify-center mx-auto text-lg font-bold">
            !
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-100">Access Restricted</h2>
            <p className="text-xs text-slate-400 mt-2">
              You do not have administrative privileges to access this area. This section is restricted to system administrators.
            </p>
          </div>
          <div className="pt-2">
            <Link to="/dashboard">
              <Button variant="secondary" size="sm">
                Return to Dashboard
              </Button>
            </Link>
          </div>
        </Card>
      </div>
    );
  }

  return children;
}

