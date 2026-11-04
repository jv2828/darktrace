import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import Card from '../../ui/Card';
import Badge from '../../ui/Badge';
import Button from '../../ui/Button';
import Spinner from '../../ui/Spinner';
import EmptyState from '../../ui/EmptyState';
import { fetchInvestigationInfrastructure } from '../../../lib/api';

export default function InfrastructureTab({ investigationId, runId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters
  const [typeFilter, setTypeFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [copiedValue, setCopiedValue] = useState(null);

  const loadInfrastructure = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetchInvestigationInfrastructure(investigationId, { run_id: runId });
      setData(res);
    } catch (err) {
      setError(err.message || 'Failed to fetch infrastructure indicators.');
    } finally {
      setLoading(false);
    }
  }, [investigationId, runId]);

  useEffect(() => {
    loadInfrastructure();
  }, [loadInfrastructure]);

  const handleCopy = (val) => {
    navigator.clipboard?.writeText(val);
    setCopiedValue(val);
    setTimeout(() => setCopiedValue(null), 2000);
  };

  if (loading) {
    return (
      <div className="py-20 flex flex-col items-center justify-center gap-3">
        <Spinner size="md" />
        <span className="text-xs text-slate-400 font-mono">Loading infrastructure & cryptographic assets...</span>
      </div>
    );
  }

  if (error) {
    return (
      <Card className="p-6">
        <EmptyState
          title="Infrastructure Data Unavailable"
          message={error}
          action={
            <Button variant="secondary" size="sm" onClick={loadInfrastructure}>
              Retry
            </Button>
          }
        />
      </Card>
    );
  }

  const rawIndicators = data?.indicators || [];
  const evidencePairs = data?.evidence_pairs || [];

  // Filter indicators
  const indicators = rawIndicators.filter((ind) => {
    if (typeFilter && ind.type !== typeFilter) return false;
    if (statusFilter !== 'all' && ind.status !== statusFilter) return false;
    return true;
  });

  const getStatusBadge = (status) => {
    switch (status) {
      case 'shared':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-950/60 text-emerald-400 border border-emerald-800/80">
            SHARED
          </span>
        );
      case 'common_suppressed':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-950/60 text-amber-400 border border-amber-800/80">
            COMMON SUPPRESSED
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-400 border border-slate-700">
            SINGLE
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Strict Network Isolation Disclaimer */}
      <div className="p-3.5 rounded-lg border border-slate-800 bg-slate-900/60 text-xs text-slate-300 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="text-amber-400 font-bold" aria-hidden="true">
            ⚠
          </span>
          <span className="font-medium text-slate-200">
            Indicators are compared as text only. DARKTRACE never connects to, scans, or probes them.
          </span>
        </div>
        <span className="text-[11px] font-mono text-slate-500 uppercase">Passive Air-Gapped Analysis</span>
      </div>

      {/* Grouped Indicators Catalog */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
              Technical & Cryptographic Indicators ({indicators.length})
            </h2>
            <p className="text-xs text-slate-400">
              Wallets, PGP keys, onion addresses, domains, and servers extracted from case data
            </p>
          </div>

          {/* Filters */}
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <div className="flex items-center gap-2">
              <label htmlFor="type-filter" className="text-slate-400 font-medium">
                Type:
              </label>
              <select
                id="type-filter"
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="bg-slate-800 border border-slate-700 text-slate-200 rounded px-2 py-1 text-xs focus:outline-none"
              >
                <option value="">All Types</option>
                <option value="pgp_fingerprint">PGP Fingerprint</option>
                <option value="btc_address">BTC Address</option>
                <option value="monero_address">Monero Address</option>
                <option value="onion_address">Tor Onion</option>
                <option value="domain">Domain</option>
                <option value="email">Email</option>
                <option value="ip_address">IP Address</option>
              </select>
            </div>

            <div className="flex items-center gap-2">
              <label htmlFor="status-filter" className="text-slate-400 font-medium">
                Status:
              </label>
              <select
                id="status-filter"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-slate-800 border border-slate-700 text-slate-200 rounded px-2 py-1 text-xs focus:outline-none"
              >
                <option value="all">All Statuses</option>
                <option value="shared">Shared (&ge;2 Personas)</option>
                <option value="single">Single Persona</option>
                <option value="common_suppressed">Common Suppressed</option>
              </select>
            </div>
          </div>
        </div>

        <Card className="overflow-hidden border-slate-800">
          {indicators.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-500">
              No indicators match the selected type and status filters.
            </div>
          ) : (
            <div className="overflow-x-auto max-h-[480px]">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-900/80 text-[11px] font-semibold uppercase tracking-wider text-slate-400 border-b border-slate-800 sticky top-0 backdrop-blur-xs">
                  <tr>
                    <th scope="col" className="py-2.5 px-3">Type</th>
                    <th scope="col" className="py-2.5 px-3">Normalised Value</th>
                    <th scope="col" className="py-2.5 px-3">Status</th>
                    <th scope="col" className="py-2.5 px-3">Personas Using Value</th>
                    <th scope="col" className="py-2.5 px-3 text-right">Posts</th>
                    <th scope="col" className="py-2.5 px-3">First Seen</th>
                    <th scope="col" className="py-2.5 px-3">Last Seen</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80 font-mono text-[11px]">
                  {indicators.map((ind, idx) => {
                    const isCopied = copiedValue === ind.normalised_value;
                    const valPreview =
                      ind.normalised_value.length > 36
                        ? `${ind.normalised_value.substring(0, 18)}…${ind.normalised_value.slice(-14)}`
                        : ind.normalised_value;

                    return (
                      <tr key={idx} className="hover:bg-slate-800/30">
                        <td className="py-2.5 px-3 font-sans">
                          <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300 border border-slate-700">
                            {ind.type}
                          </span>
                        </td>
                        <td className="py-2.5 px-3">
                          <div className="flex items-center gap-1.5">
                            <span className="text-slate-200">{valPreview}</span>
                            <button
                              type="button"
                              onClick={() => handleCopy(ind.normalised_value)}
                              className="text-slate-500 hover:text-slate-300 cursor-pointer"
                              title="Copy full indicator text"
                            >
                              {isCopied ? '✓' : '⧉'}
                            </button>
                          </div>
                        </td>
                        <td className="py-2.5 px-3 font-sans">
                          {getStatusBadge(ind.status)}
                        </td>
                        <td className="py-2.5 px-3 font-sans">
                          <div className="flex flex-wrap gap-1">
                            {ind.personas && ind.personas.length > 0 ? (
                              ind.personas.map((p) => (
                                <Link
                                  key={p.actor_id}
                                  to={`/investigations/${investigationId}/actors/${p.actor_id}`}
                                  className="text-sky-400 hover:text-sky-300 hover:underline"
                                >
                                  {p.username}
                                </Link>
                              ))
                            ) : (
                              <span className="text-slate-500">—</span>
                            )}
                          </div>
                        </td>
                        <td className="py-2.5 px-3 text-right text-slate-400">
                          {ind.total_posts}
                        </td>
                        <td className="py-2.5 px-3 text-slate-400">
                          {ind.first_seen ? ind.first_seen.substring(0, 10) : '—'}
                        </td>
                        <td className="py-2.5 px-3 text-slate-400">
                          {ind.last_seen ? ind.last_seen.substring(0, 10) : '—'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      {/* Infrastructure & Crypto Evidence Pairs */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
          Cryptographic & Infrastructure Evidence Pairs ({evidencePairs.length})
        </h2>

        <Card className="overflow-hidden border-slate-800">
          {evidencePairs.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-500">
              No cryptographic or infrastructure evidence pairs recorded in this run.
            </div>
          ) : (
            <div className="overflow-x-auto max-h-80">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-900/80 text-[11px] font-semibold uppercase tracking-wider text-slate-400 border-b border-slate-800 sticky top-0 backdrop-blur-xs">
                  <tr>
                    <th scope="col" className="py-2.5 px-3">Persona Pair</th>
                    <th scope="col" className="py-2.5 px-3">Dimension</th>
                    <th scope="col" className="py-2.5 px-3">Evidence Type</th>
                    <th scope="col" className="py-2.5 px-3">Strength</th>
                    <th scope="col" className="py-2.5 px-3">Evidence Explanation</th>
                    <th scope="col" className="py-2.5 px-3">Source Posts</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80">
                  {evidencePairs.map((ev, idx) => (
                    <tr key={idx} className="hover:bg-slate-800/30">
                      <td className="py-2.5 px-3 font-mono text-slate-200">
                        {ev.actor_a?.username} &harr; {ev.actor_b?.username}
                      </td>
                      <td className="py-2.5 px-3">
                        <Badge variant="outline">{ev.dimension}</Badge>
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[11px] text-slate-300">
                        {ev.evidence_type}
                      </td>
                      <td className="py-2.5 px-3 font-mono font-semibold text-sky-400">
                        {ev.strength.toFixed(2)}
                      </td>
                      <td className="py-2.5 px-3 text-slate-300 text-[11px]">
                        {ev.explanation}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[11px]">
                        {ev.source_post_ids && ev.source_post_ids.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {ev.source_post_ids.map((pid) => (
                              <Link
                                key={pid}
                                to={`/investigations/${investigationId}/posts/${pid}`}
                                className="text-sky-400 hover:text-sky-300 hover:underline"
                              >
                                #{pid}
                              </Link>
                            ))}
                          </div>
                        ) : (
                          <span className="text-slate-500">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

