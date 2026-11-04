import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ToastProvider } from './components/ui/Toast';
import ProtectedRoute from './components/ProtectedRoute';
import AppShell from './components/AppShell';

import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import InvestigationsPage from './pages/InvestigationsPage';
import InvestigationDetailPage from './pages/InvestigationDetailPage';
import CollectPage from './pages/CollectPage';
import PostDetailPage from './pages/PostDetailPage';
import ActorProfilePage from './pages/ActorProfilePage';
import UsersPage from './pages/UsersPage';
import SystemPage from './pages/SystemPage';
import NotFoundPage from './pages/NotFoundPage';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            {/* Public Authentication Route */}
            <Route path="/login" element={<LoginPage />} />

            {/* Authenticated Workspace Routes */}
            <Route
              element={
                <ProtectedRoute>
                  <AppShell />
                </ProtectedRoute>
              }
            >
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/investigations" element={<InvestigationsPage />} />
              <Route path="/investigations/:id" element={<InvestigationDetailPage />} />
              <Route path="/investigations/:id/collect" element={<CollectPage />} />
              <Route path="/investigations/:id/posts/:postId" element={<PostDetailPage />} />
              <Route path="/investigations/:id/actors/:actorId" element={<ActorProfilePage />} />

              {/* Administrator Only Routes */}
              <Route
                path="/users"
                element={
                  <ProtectedRoute adminOnly>
                    <UsersPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/system"
                element={
                  <ProtectedRoute adminOnly>
                    <SystemPage />
                  </ProtectedRoute>
                }
              />
            </Route>

            {/* Fallback 404 Route */}
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
