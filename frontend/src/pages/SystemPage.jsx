import React, { useState, useEffect, useCallback } from 'react';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Spinner from '../components/ui/Spinner';
import ErrorState from '../components/ui/ErrorState';
import { fetchHealth, fetchSystemInfo } from '../lib/api';

export default function SystemPage() {
  const [healthData, setHealthData] = useState(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [healthError, setHealthError] = useState(null);

  const [schemaData, setSchemaData] = useState(null);
  const [schemaLoading, setSchemaLoading] = useState(true);
  const [schemaError, setSchemaError] = useState(null);

  const checkHealthStatus = useCallback(async () => {
    setHealthLoading(true);
    setHealthError(null);
    try {
      const data = await fetchHealth();
      setHealthData(data);
    } catch (err) {
      setHealthData(null);
      setHealthError(err);
    } finally {
      setHealthLoading(false);
    }
  }, []);

  const checkSchemaStatus = useCallback(async () => {
    setSchemaLoading(true);
    setSchemaError(null);
    try {
      const data = await fetchSystemInfo();
      setSchemaData(data);
    } catch (err) {
      setSchemaData(null);
      setSchemaError(err);
    } finally {
      setSchemaLoading(false);
    }
  }, []);

  const refreshAll = useCallback(() => {
    checkHealthStatus();
    checkSchemaStatus();
  }, [checkHealthStatus, checkSchemaStatus]);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  const isBackendReachable = !healthLoading && healthData !== null;
  const isDbConnected = !healthLoading && healthData?.database === 'connected';
  const tableCount = schemaData?.tables ? Object.keys(schemaData.tables).length : 0;
  const totalRows = schemaData?.tables
    ? Object.values(schemaData.tables).reduce((sum, count) => sum + count, 0)
    : 0;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <PageHeader
        title="System Diagnostics & Schema"
        description="Low-level infrastructure health, database connection, and Alembic ORM schema audit."
        action={
          <Button
            variant="secondary"
            size="sm"
            onClick={refreshAll}
            disabled={healthLoading || schemaLoading}
          >
            {healthLoading || schemaLoading ? 'Refreshing...' : 'Refresh All Diagnostics'}
          </Button>
        }
      />

      {/* Card 1: System Health */}
      <Card className="p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
          <div>
            <h2 className="text-base font-semibold text-slate-100">Service Connectivity</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Live verification of core FastAPI server and PostgreSQL container.
            </p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={checkHealthStatus}
            disabled={healthLoading}
          >
            {healthLoading ? 'Probing...' : 'Probe Service'}
          </Button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4">
          <div className="bg-slate-950/60 border border-slate-800 rounded p-4">
            <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
              Backend Service
            </span>
            <div className="mt-2 flex items-center gap-2">
              <span
                className={`w-2.5 h-2.5 rounded-full ${
                  healthLoading
                    ? 'bg-amber-500'
                    : isBackendReachable
                    ? 'bg-emerald-500'
                    : 'bg-rose-500'
                }`}
              />
              <span className="text-sm font-medium text-slate-200">
                {healthLoading ? 'Probing...' : isBackendReachable ? 'Online' : 'Unreachable'}
              </span>
            </div>
            <p className="text-[11px] text-slate-400 mt-1">FastAPI daemon on port 8000</p>
          </div>

          <div className="bg-slate-950/60 border border-slate-800 rounded p-4">
            <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
              PostgreSQL
            </span>
            <div className="mt-2 flex items-center gap-2">
              <span
                className={`w-2.5 h-2.5 rounded-full ${
                  healthLoading
                    ? 'bg-amber-500'
                    : isDbConnected
                    ? 'bg-emerald-500'
                    : 'bg-rose-500'
                }`}
              />
              <span className="text-sm font-medium text-slate-200">
                {healthLoading ? 'Querying...' : isDbConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
            <p className="text-[11px] text-slate-400 mt-1">PostgreSQL 16 Docker container</p>
          </div>

          <div className="bg-slate-950/60 border border-slate-800 rounded p-4">
            <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
              API Version
            </span>
            <div className="mt-2 text-sm font-mono text-slate-200">
              {healthLoading ? '...' : healthData?.version || 'Unknown'}
            </div>
            <p className="text-[11px] text-slate-400 mt-1 font-mono">
              {healthData?.timestamp ? new Date(healthData.timestamp).toLocaleTimeString() : 'N/A'}
            </p>
          </div>
        </div>

        {healthError && !healthLoading && (
          <div className="mt-4">
            <ErrorState
              title="Healthcheck Failure"
              message={healthError.message}
              details={healthError.details}
              onRetry={checkHealthStatus}
            />
          </div>
        )}
      </Card>

      {/* Card 2: Database Schema & Row Counts */}
      <Card className="p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
          <div>
            <h2 className="text-base font-semibold text-slate-100">Database Schema &amp; Storage</h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Alembic migration revision and live row counts across entity tables.
            </p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={checkSchemaStatus}
            disabled={schemaLoading}
          >
            {schemaLoading ? 'Inspecting...' : 'Refresh Schema'}
          </Button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4">
          <div className="bg-slate-950/60 border border-slate-800 rounded p-4">
            <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
              Alembic Revision
            </span>
            <div className="mt-2 flex items-center gap-2">
              <span
                className={`w-2.5 h-2.5 rounded-full ${
                  schemaLoading
                    ? 'bg-amber-500'
                    : schemaData?.schema_revision
                    ? 'bg-emerald-500'
                    : 'bg-rose-500'
                }`}
              />
              <span className="text-sm font-mono font-medium text-slate-200 truncate">
                {schemaLoading ? 'Inspecting...' : schemaData?.schema_revision || 'None'}
              </span>
            </div>
            <p className="text-[11px] text-slate-400 mt-1">Current migration head</p>
          </div>

          <div className="bg-slate-950/60 border border-slate-800 rounded p-4">
            <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
              Total Tables
            </span>
            <div className="mt-2 text-sm font-mono text-slate-200">
              {schemaLoading ? '...' : `${tableCount} tables`}
            </div>
            <p className="text-[11px] text-slate-400 mt-1">Registered ORM entities</p>
          </div>

          <div className="bg-slate-950/60 border border-slate-800 rounded p-4">
            <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
              Total Stored Rows
            </span>
            <div className="mt-2 text-sm font-mono text-slate-200">
              {schemaLoading ? '...' : `${totalRows.toLocaleString()} rows`}
            </div>
            <p className="text-[11px] text-slate-400 mt-1">Live COUNT across relational tables</p>
          </div>
        </div>

        {schemaError && !schemaLoading && (
          <div className="mt-4">
            <ErrorState
              title="Schema Inspection Failure"
              message={schemaError.message}
              details={schemaError.details}
              onRetry={checkSchemaStatus}
            />
          </div>
        )}

        {/* Entity Table Counts Breakdown */}
        {schemaData?.tables && !schemaLoading && (
          <div className="mt-6 pt-4 border-t border-slate-800">
            <div className="text-xs text-slate-400 font-medium uppercase tracking-wider mb-3">
              Relational Tables Breakdown
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
              {Object.entries(schemaData.tables).map(([tbl, cnt]) => (
                <div
                  key={tbl}
                  className="flex justify-between items-center px-2.5 py-1.5 rounded bg-slate-950/40 border border-slate-800/60"
                >
                  <span className="text-slate-400 font-mono truncate">{tbl}</span>
                  <span className="text-slate-200 font-mono ml-2">{cnt}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

