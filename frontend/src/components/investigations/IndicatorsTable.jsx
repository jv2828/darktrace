import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import Card from '../ui/Card';
import Button from '../ui/Button';
import Spinner from '../ui/Spinner';
import EmptyState from '../ui/EmptyState';
import ErrorState from '../ui/ErrorState';
import {
  fetchInvestigationIndicators,
  fetchInvestigationIndicatorsSummary,
} from '../../lib/api';
import {
  getIndicatorConfig,
  formatIndicatorDetails,
  ALL_INDICATOR_TYPES,
} from '../../lib/indicatorTypes';

export default function IndicatorsTable({ investigationId }) {
  const [indicators, setIndicators] = useState([]);
  const [summary, setSummary] = useState(null);
  const [meta, setMeta] = useState({ page: 1, page_size: 25, total: 0, total_pages: 0 });
  const [loading, setLoading] = useState(true);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [error, setError] = useState(null);
  const [copiedId, setCopiedId] = useState(null);

  // Filters
  const [selectedType, setSelectedType] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(1);

  // Load summary metrics
  const loadSummary = useCallback(async () => {
    setSummaryLoading(true);
    try {
      const data = await fetchInvestigationIndicatorsSummary(investigationId);
      setSummary(data);
    } catch (err) {
      console.error('Failed to load indicators summary:', err);
    } finally {
      setSummaryLoading(false);
    }
  }, [investigationId]);

  // Load paginated list
  const loadIndicators = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchInvestigationIndicators(investigationId, {
        page,
        page_size: 25,
        type: selectedType || undefined,
        q: searchQuery || undefined,
      });
      setIndicators(res.data || []);
      setMeta(res.meta || { page: 1, page_size: 25, total: 0, total_pages: 0 });
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [investigationId, page, selectedType, searchQuery]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  useEffect(() => {
    loadIndicators();
  }, [loadIndicators]);

  function handleFilterSubmit(e) {
    e.preventDefault();
    setPage(1);
    loadIndicators();
  }

  function handleResetFilters() {
    setSelectedType('');
    setSearchQuery('');
    setPage(1);
  }

  function handleChipClick(typeKey) {
    if (selectedType === typeKey) {
      setSelectedType('');
    } else {
      setSelectedType(typeKey);
    }
    setPage(1);
  }

  async function handleCopy(text, id) {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch (err) {
      console.error('Copy failed:', err);
    }
  }

  return (
    <div className="space-y-4">
      {/* 1. Summary Chips Header */}
      <div className="bg-slate-900/40 p-3 rounded-lg border border-slate-800 space-y-2">
        <div className="flex items-center justify-between text-xs text-slate-400">
          <span className="font-semibold uppercase tracking-wider text-[11px] text-slate-300">
            Indicator Summary Filters
          </span>
          {summaryLoading ? (
            <span className="text-[11px] font-mono">Loading counts...</span>
          ) : (
            <span className="font-mono text-[11px]">
              Total:{' '}
              <span className="text-slate-100 font-bold">
                {summary?.total?.toLocaleString() || summary?.total_indicators?.toLocaleString() || 0}
              </span>{' '}
              ({summary?.distinct_indicators?.toLocaleString() || 0} distinct)
            </span>
          )}
        </div>

        <div className="flex flex-wrap gap-1.5 pt-1">
          {/* "All" chip */}
          <button
            type="button"
            onClick={() => handleChipClick('')}
            className={`px-2.5 py-1 rounded text-xs font-mono font-medium border transition-colors cursor-pointer ${
              selectedType === ''
                ? 'bg-sky-500/20 text-sky-300 border-sky-500/50'
                : 'bg-slate-900 text-slate-400 border-slate-800 hover:bg-slate-800 hover:text-slate-200'
            }`}
          >
            All ({summary?.total || summary?.total_indicators || 0})
          </button>

          {/* Individual type chips */}
          {ALL_INDICATOR_TYPES.map((typeKey) => {
            const config = getIndicatorConfig(typeKey);
            const count = summary?.by_type?.[typeKey]?.total || 0;
            const isSelected = selectedType === typeKey;

            return (
              <button
                key={typeKey}
                type="button"
                onClick={() => handleChipClick(typeKey)}
                className={`px-2.5 py-1 rounded text-xs font-mono font-medium border transition-colors cursor-pointer flex items-center gap-1.5 ${
                  isSelected
                    ? `${config.chipClass} ring-1 ring-current`
                    : 'bg-slate-900/60 text-slate-400 border-slate-800 hover:bg-slate-800/80 hover:text-slate-300'
                }`}
              >
                <span
                  className="w-1.5 h-1.5 rounded-full inline-block"
                  style={{ backgroundColor: config.dotColor }}
                />
                <span>{config.shortLabel}</span>
                <span className="text-[10px] opacity-80">({count})</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* 2. Search & Filter Bar */}
      <form
        onSubmit={handleFilterSubmit}
        className="grid grid-cols-1 sm:grid-cols-3 gap-3 bg-slate-900/60 p-3 rounded border border-slate-800"
      >
        <div>
          <label className="block text-[11px] font-medium text-slate-400 mb-1">
            Search Normalized Value
          </label>
          <input
            type="text"
            placeholder="e.g. 198.51., bc1q, nginx..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-2.5 py-1.5 text-xs bg-slate-950 border border-slate-800 rounded text-slate-100 placeholder:text-slate-500 focus:outline-hidden focus:border-sky-400 font-mono"
          />
        </div>

        <div>
          <label className="block text-[11px] font-medium text-slate-400 mb-1">
            Filter by Type
          </label>
          <select
            value={selectedType}
            onChange={(e) => {
              setSelectedType(e.target.value);
              setPage(1);
            }}
            className="w-full px-2.5 py-1.5 text-xs bg-slate-950 border border-slate-800 rounded text-slate-100 focus:outline-hidden focus:border-sky-400 cursor-pointer"
          >
            <option value="">All Indicator Types</option>
            {ALL_INDICATOR_TYPES.map((typeKey) => (
              <option key={typeKey} value={typeKey}>
                {getIndicatorConfig(typeKey).label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-end gap-2">
          <Button type="submit" variant="primary" size="sm" className="w-full">
            Apply Filters
          </Button>
          {(selectedType || searchQuery) && (
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

      {/* 3. Indicators Table */}
      {loading ? (
        <div className="py-16 flex flex-col items-center justify-center gap-2">
          <Spinner size="md" />
          <p className="text-xs text-slate-400 font-mono">Loading extracted indicators...</p>
        </div>
      ) : error ? (
        <ErrorState
          title="Failed to Load Indicators"
          message={error.message || 'Unable to retrieve extracted indicators for this investigation.'}
          onRetry={loadIndicators}
        />
      ) : indicators.length === 0 ? (
        <EmptyState
          title="No Indicators Found"
          message={
            selectedType || searchQuery
              ? 'No indicators match your current filter parameters.'
              : 'No indicators have been extracted from posts in this investigation yet. Click "Run extraction" above.'
          }
        />
      ) : (
        <Card className="overflow-hidden border border-slate-800">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/80 text-slate-400 uppercase tracking-wider border-b border-slate-800">
                <tr>
                  <th className="px-4 py-3 font-medium">Type</th>
                  <th className="px-4 py-3 font-medium">Normalized Value</th>
                  <th className="px-4 py-3 font-medium">Details</th>
                  <th className="px-4 py-3 font-medium">Author / Platform</th>
                  <th className="px-4 py-3 font-medium">Confidence</th>
                  <th className="px-4 py-3 font-medium">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {indicators.map((ind) => {
                  const config = getIndicatorConfig(ind.indicator_type);
                  const detailStr = formatIndicatorDetails(ind);
                  const isCopied = copiedId === ind.id;

                  return (
                    <tr key={ind.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-semibold border ${config.badgeClass}`}
                        >
                          <span
                            className="w-1.5 h-1.5 rounded-full inline-block"
                            style={{ backgroundColor: config.dotColor }}
                          />
                          {config.shortLabel}
                        </span>
                      </td>

                      <td className="px-4 py-3 text-slate-200 max-w-xs sm:max-w-md">
                        <div className="flex items-center gap-2 group">
                          <span className="truncate" title={ind.normalised_value}>
                            {ind.normalised_value}
                          </span>
                          <button
                            type="button"
                            onClick={() => handleCopy(ind.normalised_value, ind.id)}
                            className="text-slate-400 hover:text-slate-200 text-[10px] px-1 py-0.5 rounded bg-slate-800/60 opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer shrink-0"
                            title="Copy normalized value"
                          >
                            {isCopied ? 'Copied!' : 'Copy'}
                          </button>
                        </div>
                      </td>

                      <td className="px-4 py-3 text-slate-400 text-[11px] whitespace-nowrap">
                        {detailStr || (ind.details?.occurrences ? `${ind.details.occurrences}x` : '-')}
                      </td>

                      <td className="px-4 py-3 text-slate-300 whitespace-nowrap">
                        <div>
                          <span className="text-slate-200 font-medium">{ind.author_username || 'Unknown'}</span>
                          {ind.marketplace && (
                            <span className="ml-1 text-[11px] text-slate-400">
                              @{ind.marketplace}
                            </span>
                          )}
                        </div>
                      </td>

                      <td className="px-4 py-3 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${
                            ind.confidence === 'high'
                              ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                              : ind.confidence === 'medium'
                              ? 'bg-amber-950 text-amber-400 border border-amber-800'
                              : 'bg-rose-950 text-rose-400 border border-rose-800'
                          }`}
                        >
                          {ind.confidence || 'high'}
                        </span>
                      </td>

                      <td className="px-4 py-3 whitespace-nowrap">
                        <Link
                          to={`/investigations/${investigationId}/posts/${ind.post_id}`}
                          className="text-sky-400 hover:text-sky-300 font-medium text-[11px]"
                        >
                          View Post &rarr;
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination Controls */}
          {meta.total_pages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-slate-800 bg-slate-950/60 text-xs text-slate-400">
              <div>
                Showing page <span className="text-slate-200 font-mono">{meta.page}</span> of{' '}
                <span className="text-slate-200 font-mono">{meta.total_pages}</span> ({meta.total.toLocaleString()} total indicators)
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

