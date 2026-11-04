import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import ErrorState from '../components/ui/ErrorState';
import PostsTable from '../components/investigations/PostsTable';
import { fetchInvestigationById, fetchInvestigationDatasets } from '../lib/api';

export default function InvestigationDetailPage() {
  const { id } = useParams();
  const [investigation, setInvestigation] = useState(null);
  const [datasets, setDatasets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadInvestigation = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [invData, datasetsData] = await Promise.all([
        fetchInvestigationById(id),
        fetchInvestigationDatasets(id),
      ]);
      setInvestigation(invData);
      setDatasets(datasetsData || []);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadInvestigation();
  }, [loadInvestigation]);

  if (loading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center gap-3">
        <Spinner size="lg" />
        <p className="text-xs text-slate-400 font-mono">Loading investigation #{id}...</p>
      </div>
    );
  }

  if (error) {
    if (error.status === 404 || error.code === 'NOT_FOUND') {
      return (
        <div className="py-12 space-y-4">
          <Link to="/investigations" className="text-xs text-sky-400 hover:text-sky-300 font-medium">
            &larr; Back to Investigations
          </Link>
          <EmptyState
            title="Investigation Not Found"
            message={`The requested investigation #${id} does not exist or you do not have permission to access it.`}
            action={
              <Link to="/investigations">
                <Button variant="secondary" size="sm">
                  View My Investigations
                </Button>
              </Link>
            }
          />
        </div>
      );
    }

    return (
      <div className="py-12 space-y-4">
        <Link to="/investigations" className="text-xs text-sky-400 hover:text-sky-300 font-medium">
          &larr; Back to Investigations
        </Link>
        <ErrorState
          title="Failed to Load Investigation"
          message={error.message || 'Unable to retrieve case workspace.'}
          details={error.details}
          onRetry={loadInvestigation}
        />
      </div>
    );
  }

  if (!investigation) return null;

  return (
    <div className="space-y-6">
      {/* Navigation Breadcrumb */}
      <div className="flex items-center justify-between">
        <Link
          to="/investigations"
          className="text-xs text-sky-400 hover:text-sky-300 font-medium inline-flex items-center gap-1"
        >
          &larr; Back to Investigations
        </Link>
        <Link to={`/investigations/${id}/collect`}>
          <Button variant="primary" size="sm">
            + Add Data
          </Button>
        </Link>
      </div>

      {/* Case Header */}
      <PageHeader
        title={investigation.title}
        description={investigation.description || 'No description provided.'}
        action={<Badge variant={investigation.status}>{investigation.status}</Badge>}
      />

      {/* Metadata & Metric Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4">
          <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
            Case Status
          </span>
          <div className="mt-2">
            <Badge variant={investigation.status}>{investigation.status}</Badge>
          </div>
          <p className="text-[11px] text-slate-400 mt-2">Current investigation lifecycle</p>
        </Card>

        <Card className="p-4">
          <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
            Assigned Owner
          </span>
          <div className="mt-2 text-sm font-mono font-medium text-slate-200">
            {investigation.created_by?.username || 'System'}
          </div>
          <p className="text-[11px] text-slate-400 mt-2">Investigator ID #{investigation.created_by?.id}</p>
        </Card>

        <Card className="p-4">
          <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
            Collected Posts
          </span>
          <div className="mt-2 text-2xl font-bold font-mono text-slate-100">
            {investigation.counts?.posts?.toLocaleString() || 0}
          </div>
          <p className="text-[11px] text-slate-400 mt-2">Linked forum &amp; marketplace messages</p>
        </Card>

        <Card className="p-4">
          <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
            Extracted Indicators
          </span>
          <div className="mt-2 text-2xl font-bold font-mono text-slate-100">
            {investigation.counts?.indicators?.toLocaleString() || 0}
          </div>
          <p className="text-[11px] text-slate-400 mt-2">Cryptographic wallets, PGP, domains</p>
        </Card>
      </div>

      {/* Attached Datasets Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
            Attached Intelligence Datasets ({datasets.length})
          </h2>
          <Link to={`/investigations/${id}/collect`}>
            <span className="text-xs text-sky-400 hover:text-sky-300 font-medium">
              Manage / Add Datasets &rarr;
            </span>
          </Link>
        </div>

        {datasets.length === 0 ? (
          <Card className="p-6">
            <EmptyState
              title="No Datasets Attached"
              message="No datasets have been linked to this case yet. Click 'Add Data' to load synthetic benchmarks or ingest custom files."
              action={
                <Link to={`/investigations/${id}/collect`}>
                  <Button variant="secondary" size="sm">
                    Open Data Collection
                  </Button>
                </Link>
              }
            />
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {datasets.map((ds) => (
              <Card key={ds.id} className="p-4 flex flex-col justify-between border-slate-800">
                <div>
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium uppercase bg-slate-800 text-slate-300 border border-slate-700">
                      {ds.source_type}
                    </span>
                    <span className="text-[11px] font-mono text-slate-400">
                      {ds.post_count?.toLocaleString()} posts
                    </span>
                  </div>
                  <h3 className="text-sm font-medium text-slate-200 line-clamp-1">
                    {ds.name}
                  </h3>
                </div>
                <div className="mt-3 pt-2 border-t border-slate-800/80 text-[11px] text-slate-400 font-mono">
                  Attached: {ds.added_at ? new Date(ds.added_at).toLocaleDateString() : 'N/A'}
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Real Collected Posts Table */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
          Collected Case Communications
        </h2>
        <PostsTable investigationId={id} />
      </div>
    </div>
  );
}
