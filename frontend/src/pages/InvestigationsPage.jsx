import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import PageHeader from '../components/ui/PageHeader';
import Button from '../components/ui/Button';
import Badge from '../components/ui/Badge';
import Table from '../components/ui/Table';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import ErrorState from '../components/ui/ErrorState';
import NewInvestigationModal from '../components/investigations/NewInvestigationModal';
import { fetchInvestigations } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../components/ui/Toast';

export default function InvestigationsPage() {
  const { isAdmin } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();

  const [investigations, setInvestigations] = useState([]);
  const [meta, setMeta] = useState({ page: 1, page_size: 10, total: 0, total_pages: 1 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [currentPage, setCurrentPage] = useState(1);

  // Modal
  const [isModalOpen, setIsModalOpen] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchInvestigations({
        page: currentPage,
        page_size: 10,
        q: searchQuery.trim() || undefined,
        status: statusFilter || undefined,
      });
      setInvestigations(res.data || []);
      setMeta(res.meta || { page: 1, page_size: 10, total: 0, total_pages: 1 });
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [currentPage, searchQuery, statusFilter]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  function handleSearchSubmit(e) {
    e.preventDefault();
    setCurrentPage(1);
    loadData();
  }

  function handleInvestigationCreated(created) {
    setIsModalOpen(false);
    toast.success(`Investigation "${created.title}" successfully created.`);
    navigate(`/investigations/${created.id}`);
  }

  const tableHeaders = [
    { label: 'Title / Reference' },
    { label: 'Status' },
    { label: 'Posts' },
    { label: 'Indicators' },
    ...(isAdmin ? [{ label: 'Created By' }] : []),
    { label: 'Created' },
    { label: 'Actions', className: 'text-right' },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <PageHeader
        title="Investigations"
        description="Active case workspaces and dark web actor correlation records."
        action={
          <Button variant="primary" onClick={() => setIsModalOpen(true)}>
            + New Investigation
          </Button>
        }
      />

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between bg-slate-900/60 p-3 rounded-lg border border-slate-800">
        <form onSubmit={handleSearchSubmit} className="flex-1 flex gap-2">
          <input
            type="text"
            placeholder="Search investigations by title..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="flex-1 px-3 py-1.5 text-xs bg-slate-950 border border-slate-800 rounded text-slate-100 placeholder:text-slate-500 focus:outline-hidden focus:border-sky-400"
          />
          <Button type="submit" variant="secondary" size="sm">
            Search
          </Button>
        </form>

        <div className="flex items-center gap-2">
          <label htmlFor="filter-status" className="text-xs text-slate-400 shrink-0">
            Status:
          </label>
          <select
            id="filter-status"
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setCurrentPage(1);
            }}
            className="px-3 py-1.5 text-xs bg-slate-950 border border-slate-800 rounded text-slate-100 focus:outline-hidden focus:border-sky-400 cursor-pointer"
          >
            <option value="">All Statuses</option>
            <option value="draft">Draft</option>
            <option value="processing">Processing</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="py-20 flex flex-col items-center justify-center gap-3">
          <Spinner size="lg" />
          <p className="text-xs text-slate-400 font-mono">Loading investigations...</p>
        </div>
      )}

      {/* Error State */}
      {!loading && error && (
        <ErrorState
          title="Failed to Load Investigations"
          message={error.message || 'Unable to retrieve case listings.'}
          details={error.details}
          onRetry={loadData}
        />
      )}

      {/* Table Content */}
      {!loading && !error && (
        <>
          {investigations.length === 0 ? (
            <EmptyState
              title="No investigations found"
              message={
                searchQuery || statusFilter
                  ? 'No investigations match your active search and filter criteria.'
                  : 'No investigations have been initiated yet.'
              }
              action={
                searchQuery || statusFilter ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      setSearchQuery('');
                      setStatusFilter('');
                      setCurrentPage(1);
                    }}
                  >
                    Clear Filters
                  </Button>
                ) : (
                  <Button variant="primary" size="sm" onClick={() => setIsModalOpen(true)}>
                    Start Investigation
                  </Button>
                )
              }
            />
          ) : (
            <div className="space-y-4">
              <Table headers={tableHeaders}>
                {investigations.map((inv) => (
                  <tr key={inv.id} className="hover:bg-slate-850/50 transition-colors">
                    <td className="py-3 px-4 font-medium">
                      <Link
                        to={`/investigations/${inv.id}`}
                        className="text-slate-100 hover:text-sky-400 block"
                      >
                        {inv.title}
                      </Link>
                      {inv.description && (
                        <p className="text-[11px] text-slate-400 line-clamp-1 mt-0.5">
                          {inv.description}
                        </p>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <Badge variant={inv.status}>{inv.status}</Badge>
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-300">
                      {inv.counts?.posts?.toLocaleString() || 0}
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-300">
                      {inv.counts?.indicators?.toLocaleString() || 0}
                    </td>
                    {isAdmin && (
                      <td className="py-3 px-4 text-slate-400 font-mono text-[11px]">
                        {inv.created_by?.username || 'Unknown'}
                      </td>
                    )}
                    <td className="py-3 px-4 font-mono text-[11px] text-slate-400">
                      {inv.created_at ? new Date(inv.created_at).toLocaleDateString() : 'N/A'}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Link to={`/investigations/${inv.id}`}>
                        <Button variant="ghost" size="sm">
                          Inspect &rarr;
                        </Button>
                      </Link>
                    </td>
                  </tr>
                ))}
              </Table>

              {/* Pagination Controls */}
              <div className="flex items-center justify-between text-xs text-slate-400 pt-2 px-1">
                <div>
                  Showing {investigations.length} of {meta.total} investigations
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={currentPage <= 1 || loading}
                    onClick={() => setCurrentPage((p) => Math.max(p - 1, 1))}
                  >
                    Previous
                  </Button>
                  <span className="font-mono text-slate-300 px-2">
                    Page {meta.page} of {Math.max(meta.total_pages, 1)}
                  </span>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={currentPage >= meta.total_pages || loading}
                    onClick={() => setCurrentPage((p) => p + 1)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* Modal */}
      <NewInvestigationModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={handleInvestigationCreated}
      />
    </div>
  );
}

