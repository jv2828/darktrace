import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import PageHeader from '../components/ui/PageHeader';
import StatCard from '../components/ui/StatCard';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import ErrorState from '../components/ui/ErrorState';
import NewInvestigationModal from '../components/investigations/NewInvestigationModal';
import { fetchDashboardSummary } from '../lib/api';
import { useToast } from '../components/ui/Toast';

export default function DashboardPage() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const navigate = useNavigate();
  const toast = useToast();

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchDashboardSummary();
      setSummary(data);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  function handleInvestigationCreated(created) {
    setIsModalOpen(false);
    toast.success(`Investigation "${created.title}" successfully initiated.`);
    navigate(`/investigations/${created.id}`);
  }

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <PageHeader
        title="Threat Intelligence Dashboard"
        description="Unified threat overview, aggregated metrics, and recent case activity."
        action={
          <Button variant="primary" onClick={() => setIsModalOpen(true)}>
            + Start New Investigation
          </Button>
        }
      />

      {/* Loading State */}
      {loading && (
        <div className="py-20 flex flex-col items-center justify-center gap-3">
          <Spinner size="lg" />
          <p className="text-xs text-slate-400 font-mono">Loading dashboard metrics...</p>
        </div>
      )}

      {/* Error State with Retry */}
      {!loading && error && (
        <ErrorState
          title="Failed to Load Dashboard"
          message={error.message || 'Unable to retrieve summary data from the API server.'}
          details={error.details}
          onRetry={loadData}
        />
      )}

      {/* Summary Content */}
      {!loading && !error && summary && (
        <>
          {/* Top Stat Cards Grid */}
          <div className="space-y-2">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard
                title="Total Investigations"
                value={summary.totals.investigations}
                subtitle="Active & completed cases"
              />
              <StatCard
                title="Collected Posts"
                value={summary.totals.posts}
                subtitle="Dark web listings & messages"
              />
              <StatCard
                title="Extracted Indicators"
                value={summary.totals.indicators}
                subtitle="Wallets, PGP, and domains"
              />
              <StatCard
                title="Potential Linkages"
                value={summary.totals.potential_linkages}
                subtitle="Cross-actor heuristic correlations"
              />
            </div>
            {/* Disclaimer under Stat Cards */}
            <p className="text-xs text-slate-400 italic pt-1">
              Potential linkages are heuristic evidence scores for investigation, not confirmed identities.
            </p>
          </div>

          {/* Activity Grid: Recent Investigations & Recent Pipeline Activity */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pt-2">
            {/* Recent Investigations List */}
            <Card className="flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between pb-4 border-b border-slate-800">
                  <h2 className="text-sm font-semibold text-slate-100 uppercase tracking-wider">
                    Recent Investigations
                  </h2>
                  <Link
                    to="/investigations"
                    className="text-xs text-sky-400 hover:text-sky-300 font-medium"
                  >
                    View All &rarr;
                  </Link>
                </div>

                <div className="pt-3">
                  {summary.recent_investigations.length === 0 ? (
                    <EmptyState
                      title="No investigations yet"
                      message="Start your first investigation to track threat actors and correlate dark web evidence."
                      action={
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => setIsModalOpen(true)}
                        >
                          Create Investigation
                        </Button>
                      }
                    />
                  ) : (
                    <ul className="divide-y divide-slate-800/60">
                      {summary.recent_investigations.map((inv) => (
                        <li key={inv.id} className="py-3 flex items-center justify-between gap-3">
                          <div className="min-w-0">
                            <Link
                              to={`/investigations/${inv.id}`}
                              className="text-sm font-medium text-slate-200 hover:text-sky-400 truncate block"
                            >
                              {inv.title}
                            </Link>
                            <span className="text-[11px] font-mono text-slate-400">
                              {inv.created_at ? new Date(inv.created_at).toLocaleDateString() : 'Pending'}
                            </span>
                          </div>
                          <Badge variant={inv.status}>{inv.status}</Badge>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </Card>

            {/* Recent Correlation Activity */}
            <Card className="flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between pb-4 border-b border-slate-800">
                  <h2 className="text-sm font-semibold text-slate-100 uppercase tracking-wider">
                    Recent Correlation Activity
                  </h2>
                  <span className="text-xs font-mono text-slate-400">Pipeline Runs</span>
                </div>

                <div className="pt-3">
                  {summary.recent_correlation_activity.length === 0 ? (
                    <EmptyState
                      title="No pipeline runs recorded"
                      message="Correlation and scoring runs will appear here as data analytics are triggered in future phases."
                    />
                  ) : (
                    <ul className="divide-y divide-slate-800/60">
                      {summary.recent_correlation_activity.map((run) => (
                        <li key={run.id} className="py-3 flex items-center justify-between gap-3">
                          <div className="min-w-0">
                            <div className="text-sm font-medium text-slate-200 truncate">
                              {run.investigation_title}
                            </div>
                            <span className="text-[11px] font-mono text-slate-400">
                              Run #{run.id} &bull;{' '}
                              {run.started_at ? new Date(run.started_at).toLocaleString() : 'Queued'}
                            </span>
                          </div>
                          <Badge variant={run.status}>{run.status}</Badge>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </Card>
          </div>
        </>
      )}

      {/* New Investigation Dialog */}
      <NewInvestigationModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={handleInvestigationCreated}
      />
    </div>
  );
}

