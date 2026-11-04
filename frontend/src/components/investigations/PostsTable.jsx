import React, { useState, useEffect, useCallback } from 'react';
import Card from '../ui/Card';
import Button from '../ui/Button';
import Badge from '../ui/Badge';
import Spinner from '../ui/Spinner';
import EmptyState from '../ui/EmptyState';
import ErrorState from '../ui/ErrorState';
import { fetchInvestigationPosts } from '../../lib/api';

export default function PostsTable({ investigationId }) {
  const [posts, setPosts] = useState([]);
  const [meta, setMeta] = useState({ page: 1, page_size: 15, total: 0, total_pages: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filter state
  const [marketplaceFilter, setMarketplaceFilter] = useState('');
  const [usernameFilter, setUsernameFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);

  const loadPosts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchInvestigationPosts(investigationId, {
        page,
        page_size: 15,
        marketplace: marketplaceFilter || undefined,
        username: usernameFilter || undefined,
        q: searchQuery || undefined,
      });
      setPosts(res.data || []);
      setMeta(res.meta || { page: 1, page_size: 15, total: 0, total_pages: 0 });
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [investigationId, page, marketplaceFilter, usernameFilter, searchQuery]);

  useEffect(() => {
    loadPosts();
  }, [loadPosts]);

  function handleFilterSubmit(e) {
    e.preventDefault();
    setPage(1);
    loadPosts();
  }

  function handleResetFilters() {
    setMarketplaceFilter('');
    setUsernameFilter('');
    setSearchQuery('');
    setPage(1);
  }

  return (
    <div className="space-y-4">
      {/* Search & Filter Bar */}
      <form
        onSubmit={handleFilterSubmit}
        className="grid grid-cols-1 sm:grid-cols-4 gap-3 bg-slate-900/60 p-3 rounded border border-slate-800"
      >
        <div>
          <label className="block text-[11px] font-medium text-slate-400 mb-1">
            Search Content
          </label>
          <input
            type="text"
            placeholder="e.g. escrow, clockwork..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-2.5 py-1.5 text-xs bg-slate-950 border border-slate-800 rounded text-slate-100 placeholder:text-slate-500 focus:outline-hidden focus:border-sky-400"
          />
        </div>

        <div>
          <label className="block text-[11px] font-medium text-slate-400 mb-1">
            Marketplace
          </label>
          <input
            type="text"
            placeholder="e.g. Velvet Bazaar"
            value={marketplaceFilter}
            onChange={(e) => setMarketplaceFilter(e.target.value)}
            className="w-full px-2.5 py-1.5 text-xs bg-slate-950 border border-slate-800 rounded text-slate-100 placeholder:text-slate-500 focus:outline-hidden focus:border-sky-400"
          />
        </div>

        <div>
          <label className="block text-[11px] font-medium text-slate-400 mb-1">
            Author Username
          </label>
          <input
            type="text"
            placeholder="e.g. iron_weaver"
            value={usernameFilter}
            onChange={(e) => setUsernameFilter(e.target.value)}
            className="w-full px-2.5 py-1.5 text-xs bg-slate-950 border border-slate-800 rounded text-slate-100 placeholder:text-slate-500 focus:outline-hidden focus:border-sky-400"
          />
        </div>

        <div className="flex items-end gap-2">
          <Button type="submit" variant="primary" size="sm" className="w-full">
            Filter
          </Button>
          {(marketplaceFilter || usernameFilter || searchQuery) && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleResetFilters}
            >
              Reset
            </Button>
          )}
        </div>
      </form>

      {/* Table Content */}
      {loading ? (
        <div className="py-16 flex flex-col items-center justify-center gap-2">
          <Spinner size="md" />
          <p className="text-xs text-slate-400 font-mono">Loading investigation posts...</p>
        </div>
      ) : error ? (
        <ErrorState
          title="Failed to Load Posts"
          message={error.message || 'Unable to retrieve collected darknet communications.'}
          onRetry={loadPosts}
        />
      ) : posts.length === 0 ? (
        <EmptyState
          title="No Posts Found"
          message={
            marketplaceFilter || usernameFilter || searchQuery
              ? 'No posts matched your current search filters.'
              : 'No posts collected for this investigation yet. Click "Add data" to ingest sample or custom records.'
          }
        />
      ) : (
        <Card className="overflow-hidden border border-slate-800">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/80 text-slate-400 uppercase tracking-wider border-b border-slate-800">
                <tr>
                  <th className="px-4 py-3 font-medium">Author</th>
                  <th className="px-4 py-3 font-medium">Platform</th>
                  <th className="px-4 py-3 font-medium">Posted At (UTC)</th>
                  <th className="px-4 py-3 font-medium">Content Excerpt</th>
                  <th className="px-4 py-3 font-medium">Dataset</th>
                  <th className="px-4 py-3 font-medium">Indicators</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {posts.map((post) => (
                  <tr key={post.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="px-4 py-3 font-medium text-slate-200">
                      {post.author_username}
                    </td>
                    <td className="px-4 py-3 text-slate-300">
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-[11px]">
                        {post.marketplace}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-400 whitespace-nowrap">
                      {post.posted_at ? new Date(post.posted_at).toLocaleString() : 'N/A'}
                    </td>
                    <td className="px-4 py-3 font-sans text-slate-300 max-w-md">
                      <p className="line-clamp-2 leading-relaxed">{post.content_excerpt}</p>
                    </td>
                    <td className="px-4 py-3 text-slate-400 whitespace-nowrap text-[11px]">
                      {post.dataset_name}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      {post.has_structured_indicators ? (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-950 text-emerald-300 border border-emerald-800">
                          Structured
                        </span>
                      ) : (
                        <span className="text-slate-400 text-[11px]">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination Controls */}
          {meta.total_pages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-slate-800 bg-slate-950/60 text-xs text-slate-400">
              <div>
                Showing page <span className="text-slate-200 font-mono">{meta.page}</span> of{' '}
                <span className="text-slate-200 font-mono">{meta.total_pages}</span> ({meta.total.toLocaleString()} total posts)
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Previous
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page >= meta.total_pages}
                  onClick={() => setPage((p) => Math.min(meta.total_pages, p + 1))}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

