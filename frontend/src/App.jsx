import { useState, useEffect, useCallback } from 'react';
import { fetchHealth, fetchSystemInfo } from './lib/api';

export default function App() {
  // System Status state
  const [loading, setLoading] = useState(true);
  const [healthData, setHealthData] = useState(null);
  const [errorInfo, setErrorInfo] = useState(null);

  // Database Schema state
  const [schemaLoading, setSchemaLoading] = useState(true);
  const [schemaData, setSchemaData] = useState(null);
  const [schemaError, setSchemaError] = useState(null);

  const checkStatus = useCallback(async () => {
    setLoading(true);
    setErrorInfo(null);

    try {
      const data = await fetchHealth();
      setHealthData(data);
      setErrorInfo(null);
    } catch (err) {
      setHealthData(null);
      setErrorInfo({
        code: err.code || 'REQUEST_FAILED',
        message: err.message,
        details: err.details || null,
        status: err.status || null,
      });
    } finally {
      setLoading(false);
    }
  }, []);

  const checkSchema = useCallback(async () => {
    setSchemaLoading(true);
    setSchemaError(null);

    try {
      const data = await fetchSystemInfo();
      setSchemaData(data);
      setSchemaError(null);
    } catch (err) {
      setSchemaData(null);
      setSchemaError({
        code: err.code || 'REQUEST_FAILED',
        message: err.message,
        details: err.details || null,
        status: err.status || null,
      });
    } finally {
      setSchemaLoading(false);
    }
  }, []);

  const refreshAll = useCallback(() => {
    checkStatus();
    checkSchema();
  }, [checkStatus, checkSchema]);

  useEffect(() => {
    checkStatus();
    checkSchema();
  }, [checkStatus, checkSchema]);

  // Determine real status metrics based on actual API response
  const isBackendReachable = !loading && (healthData !== null || (errorInfo && errorInfo.code === 'DATABASE_UNAVAILABLE'));
  const isDbConnected = !loading && healthData?.database === 'connected';
  const appVersion = healthData?.version || (errorInfo?.code === 'DATABASE_UNAVAILABLE' ? '0.1.0' : 'Unavailable');
  const lastChecked = healthData?.timestamp ? new Date(healthData.timestamp).toLocaleString() : null;

  // Schema metrics
  const isSchemaAuthRequired = Boolean(
    schemaError && (
      schemaError.status === 401 ||
      schemaError.status === 403 ||
      schemaError.code === 'NOT_AUTHENTICATED' ||
      schemaError.code === 'FORBIDDEN'
    )
  );
  const schemaRevision = isSchemaAuthRequired
    ? 'Protected'
    : (schemaData?.schema_revision || (schemaLoading ? '...' : 'None'));
  const tableCount = isSchemaAuthRequired
    ? 'Protected'
    : (schemaData?.tables ? `${Object.keys(schemaData.tables).length} tables` : '0 tables');
  const totalRows = isSchemaAuthRequired
    ? 'Protected'
    : (schemaData?.tables
        ? `${Object.values(schemaData.tables).reduce((sum, count) => sum + count, 0)} rows`
        : '0 rows');

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col justify-between p-6 sm:p-12 font-sans selection:bg-slate-800">
      {/* Top Header */}
      <header className="max-w-4xl w-full mx-auto pb-8 border-b border-slate-800 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-wider text-slate-100 uppercase">
            DARKTRACE
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Dark Web Threat-Intelligence &amp; Actor-Correlation Platform
          </p>
        </div>
        <div className="flex items-center gap-2">
          {schemaData?.environment && (
            <span className="text-xs px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-400 font-mono">
              {schemaData.environment}
            </span>
          )}
          <div className="text-xs px-2.5 py-1 rounded bg-slate-900 border border-slate-800 text-slate-400">
            Phase 3: Auth &amp; Access Control
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="max-w-4xl w-full mx-auto my-auto py-8 space-y-6">
        {/* Card 1: System Status */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 sm:p-8 shadow-sm">
          {/* Card Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
            <div>
              <h2 className="text-lg font-semibold text-slate-200">System Status</h2>
              <p className="text-sm text-slate-400 mt-0.5">
                Live verification of core backend and database connectivity.
              </p>
            </div>
            <div>
              <button
                type="button"
                onClick={refreshAll}
                disabled={loading || schemaLoading}
                className="w-full sm:w-auto px-4 py-2 text-sm font-medium rounded bg-slate-800 hover:bg-slate-700 active:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed border border-slate-700 text-slate-200 transition-colors"
              >
                {loading || schemaLoading ? 'Checking...' : 'Retry'}
              </button>
            </div>
          </div>

          {/* Status Metrics Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-6">
            {/* Backend Service Metric */}
            <div className="bg-slate-950/60 border border-slate-800 rounded p-4">
              <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
                Backend Service
              </span>
              <div className="mt-2 flex items-center gap-2">
                <span
                  className={`w-2.5 h-2.5 rounded-full ${
                    loading
                      ? 'bg-amber-500'
                      : isBackendReachable
                      ? 'bg-emerald-500'
                      : 'bg-rose-500'
                  }`}
                />
                <span className="text-base font-medium text-slate-200">
                  {loading
                    ? 'Probing...'
                    : isBackendReachable
                    ? 'Reachable'
                    : 'Unreachable'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-2">
                {isBackendReachable ? 'FastAPI service online' : 'Unable to connect to port 8000'}
              </p>
            </div>

            {/* PostgreSQL Database Metric */}
            <div className="bg-slate-950/60 border border-slate-800 rounded p-4">
              <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
                PostgreSQL Database
              </span>
              <div className="mt-2 flex items-center gap-2">
                <span
                  className={`w-2.5 h-2.5 rounded-full ${
                    loading
                      ? 'bg-amber-500'
                      : isDbConnected
                      ? 'bg-emerald-500'
                      : 'bg-rose-500'
                  }`}
                />
                <span className="text-base font-medium text-slate-200">
                  {loading
                    ? 'Querying...'
                    : isDbConnected
                    ? 'Connected'
                    : 'Disconnected'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-2">
                {isDbConnected ? 'SELECT 1 ping succeeded' : 'Database server unreachable'}
              </p>
            </div>

            {/* API Version Metric */}
            <div className="bg-slate-950/60 border border-slate-800 rounded p-4">
              <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
                API Version
              </span>
              <div className="mt-2 flex items-center gap-2">
                <span className="text-base font-medium text-slate-200">
                  {loading ? '...' : appVersion}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-2">
                {lastChecked ? `Checked: ${lastChecked}` : 'Target: v1'}
              </p>
            </div>
          </div>

          {/* Error Banner if something failed */}
          {errorInfo && !loading && (
            <div className="mt-6 p-4 rounded bg-rose-950/30 border border-rose-900/50 text-rose-200 text-sm">
              <div className="font-semibold text-rose-300">
                {errorInfo.code}: {errorInfo.message}
              </div>
              {errorInfo.details && (
                <div className="text-xs text-rose-400 mt-1 font-mono break-all">
                  Details: {typeof errorInfo.details === 'object' ? JSON.stringify(errorInfo.details) : String(errorInfo.details)}
                </div>
              )}
            </div>
          )}

          {/* Success Summary when operational */}
          {healthData && !loading && (
            <div className="mt-6 p-3 rounded bg-emerald-950/20 border border-emerald-900/40 text-emerald-300 text-xs flex items-center justify-between">
              <span>All core foundation components are responsive and functioning normally.</span>
              <span className="font-mono text-emerald-400 text-[11px]">{healthData.timestamp}</span>
            </div>
          )}
        </div>

        {/* Card 2: Database Schema */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 sm:p-8 shadow-sm">
          {/* Card Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800">
            <div>
              <h2 className="text-lg font-semibold text-slate-200">Database Schema</h2>
              <p className="text-sm text-slate-400 mt-0.5">
                Alembic migration version and active entity table counts.
              </p>
            </div>
            <div>
              <button
                type="button"
                onClick={checkSchema}
                disabled={schemaLoading}
                className="w-full sm:w-auto px-4 py-2 text-sm font-medium rounded bg-slate-800 hover:bg-slate-700 active:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed border border-slate-700 text-slate-200 transition-colors"
              >
                {schemaLoading ? 'Refreshing...' : 'Refresh Schema'}
              </button>
            </div>
          </div>

          {/* Schema Metrics Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-6">
            {/* Schema Revision */}
            <div className="bg-slate-950/60 border border-slate-800 rounded p-4">
              <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
                Schema Revision
              </span>
              <div className="mt-2 flex items-center gap-2">
                <span
                  className={`w-2.5 h-2.5 rounded-full ${
                    schemaLoading
                      ? 'bg-amber-500'
                      : isSchemaAuthRequired
                      ? 'bg-slate-500'
                      : schemaData?.schema_revision
                      ? 'bg-emerald-500'
                      : 'bg-rose-500'
                  }`}
                />
                <span className="text-base font-mono font-medium text-slate-200 truncate">
                  {schemaLoading ? 'Inspecting...' : schemaRevision}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-2">
                {isSchemaAuthRequired
                  ? 'Admin authentication required'
                  : schemaData?.schema_revision
                  ? 'Alembic revision applied'
                  : 'No migration applied'}
              </p>
            </div>

            {/* Total Tables */}
            <div className="bg-slate-950/60 border border-slate-800 rounded p-4">
              <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
                Total Tables
              </span>
              <div className="mt-2 flex items-center gap-2">
                <span className="text-base font-medium text-slate-200">
                  {schemaLoading ? '...' : tableCount}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-2">
                {isSchemaAuthRequired ? 'Requires admin privileges' : 'Registered ORM entity models'}
              </p>
            </div>

            {/* Total Records */}
            <div className="bg-slate-950/60 border border-slate-800 rounded p-4">
              <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
                Total Rows
              </span>
              <div className="mt-2 flex items-center gap-2">
                <span className="text-base font-medium text-slate-200">
                  {schemaLoading ? '...' : totalRows}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-2">
                {isSchemaAuthRequired ? 'Requires admin privileges' : 'Live COUNT query across tables'}
              </p>
            </div>
          </div>

          {/* Neutral Banner when auth is required */}
          {isSchemaAuthRequired && !schemaLoading && (
            <div className="mt-6 p-4 rounded bg-slate-950/60 border border-slate-800 text-slate-300 text-sm flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-slate-500" />
                <span>Sign-in required (login page arrives in the next phase)</span>
              </div>
              <span className="text-xs font-mono text-slate-500">
                {schemaError.code || 'NOT_AUTHENTICATED'}
              </span>
            </div>
          )}

          {/* Error Banner for Schema (non-auth unexpected errors) */}
          {schemaError && !schemaLoading && !isSchemaAuthRequired && (
            <div className="mt-6 p-4 rounded bg-rose-950/30 border border-rose-900/50 text-rose-200 text-sm">
              <div className="font-semibold text-rose-300">
                {schemaError.code}: {schemaError.message}
              </div>
              {schemaError.details && (
                <div className="text-xs text-rose-400 mt-1 font-mono break-all">
                  Details: {typeof schemaError.details === 'object' ? JSON.stringify(schemaError.details) : String(schemaError.details)}
                </div>
              )}
            </div>
          )}

          {/* Table Breakdown pills if available */}
          {schemaData?.tables && !schemaLoading && (
            <div className="mt-6 pt-4 border-t border-slate-800/80">
              <div className="text-xs text-slate-400 font-medium uppercase tracking-wider mb-3">
                Entity Table Counts
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                {Object.entries(schemaData.tables).map(([tbl, cnt]) => (
                  <div key={tbl} className="flex justify-between px-2.5 py-1.5 rounded bg-slate-950/40 border border-slate-800/60">
                    <span className="text-slate-400 font-mono truncate">{tbl}</span>
                    <span className="text-slate-300 font-mono ml-2">{cnt}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="max-w-4xl w-full mx-auto pt-6 border-t border-slate-800 text-center text-xs text-slate-400">
        DARKTRACE &bull; College Cybersecurity Lab Project &bull; Strictly Authorized &amp; Synthetic Data Only
      </footer>
    </div>
  );
}
