import React, { useState, useEffect, useCallback } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import Card from '../../ui/Card';
import Badge from '../../ui/Badge';
import Button from '../../ui/Button';
import Spinner from '../../ui/Spinner';
import EmptyState from '../../ui/EmptyState';
import PostsTable from '../PostsTable';
import IndicatorsTable from '../IndicatorsTable';
import {
  fetchInvestigationCorrelations,
  fetchCorrelationDetail,
  fetchInvestigationActors,
} from '../../../lib/api';

export default function OverviewTab({ investigationId, runId, onTriggerRun, setTab }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [correlations, setCorrelations] = useState([]);
  const [actors, setActors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedPairId, setExpandedPairId] = useState(null);
  const [pairDetails, setPairDetails] = useState({});
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [showSourceData, setShowSourceData] = useState(false);
  const [sourceDataSubTab, setSourceDataSubTab] = useState('posts'); // 'posts' | 'indicators'

  const switchTab = (tabId) => {
    if (setTab) {
      setTab(tabId);
    } else {
      setSearchParams((prev) => {
        const p = new URLSearchParams(prev);
        p.set('tab', tabId);
        return p;
      });
    }
  };

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [corrRes, actorsRes] = await Promise.all([
        fetchInvestigationCorrelations(investigationId, { run_id: runId, page_size: 100 }),
        fetchInvestigationActors(investigationId, { run_id: runId }).catch(() => []),
      ]);

      const corrItems = corrRes?.data?.items || corrRes?.items || (Array.isArray(corrRes) ? corrRes : []);
      // Sort persona pairs by combined score descending
      corrItems.sort((a, b) => (b.combined_score || 0) - (a.combined_score || 0));
      setCorrelations(corrItems);
      setActors(Array.isArray(actorsRes) ? actorsRes : []);

      // Auto-expand the first (top) pair by default on first load
      if (corrItems.length > 0) {
        const topPair = corrItems[0];
        const topPairKey = `${topPair.actors.actor_a.id}_${topPair.actors.actor_b.id}`;
        setExpandedPairId(topPairKey);
        fetchCorrelationDetail(
          investigationId,
          topPair.actors.actor_a.id,
          topPair.actors.actor_b.id,
          runId
        ).then((detail) => {
          setPairDetails((prev) => ({ ...prev, [topPairKey]: detail }));
        }).catch((err) => {
          console.error('Failed to pre-fetch top pair detail:', err);
        });
      }
    } catch (err) {
      setError(err.message || 'Failed to load correlation overview data.');
    } finally {
      setLoading(false);
    }
  }, [investigationId, runId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const toggleExpandPair = async (pair) => {
    const pairKey = `${pair.actors.actor_a.id}_${pair.actors.actor_b.id}`;
    if (expandedPairId === pairKey) {
      setExpandedPairId(null);
      return;
    }

    setExpandedPairId(pairKey);
    if (!pairDetails[pairKey]) {
      setLoadingDetail(true);
      try {
        const detail = await fetchCorrelationDetail(
          investigationId,
          pair.actors.actor_a.id,
          pair.actors.actor_b.id,
          runId
        );
        setPairDetails((prev) => ({ ...prev, [pairKey]: detail }));
      } catch (err) {
        console.error('Failed to load correlation pair detail:', err);
      } finally {
        setLoadingDetail(false);
      }
    }
  };

  const getLevelBadgeVariant = (lvl) => {
    switch (lvl?.toLowerCase()) {
      case 'strong':
        return 'success';
      case 'moderate':
        return 'warning';
      case 'weak':
        return 'neutral';
      default:
        return 'outline';
    }
  };

  if (loading) {
    return (
      <div className="py-16 flex flex-col items-center justify-center gap-3">
        <Spinner size="md" />
        <span className="text-xs text-slate-400 font-mono">Loading case correlation overview...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 rounded-lg bg-rose-950/40 border border-rose-900/60 text-xs text-rose-300 flex items-center justify-between">
        <span>{error}</span>
        <Button variant="secondary" size="sm" onClick={loadData}>
          Retry
        </Button>
      </div>
    );
  }

  // If no run exists, show only the existing "Run Correlation Pipeline" empty state
  if (!runId && correlations.length === 0) {
    return (
      <Card className="p-8">
        <EmptyState
          title="No Correlated Persona Pairs"
          message="No persona links have been established yet. Execute the correlation pipeline to calculate multi-dimensional similarity."
          action={
            onTriggerRun ? (
              <Button variant="primary" size="sm" onClick={onTriggerRun}>
                Run Correlation Pipeline
              </Button>
            ) : null
          }
        />
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Prominent Explore the Evidence Card */}
      <Card className="p-4 bg-slate-900/90 border-slate-700/80 shadow-md">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
              <span className="text-sky-400">⚡</span> Explore the evidence
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Jump directly into topological graph, behavioral charts, stylometry, or chronological timeline.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => switchTab('graph')}
              className="text-xs font-medium"
            >
              Evidence Graph
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => switchTab('behaviour')}
              className="text-xs font-medium"
            >
              Behaviour Charts
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => switchTab('stylometry')}
              className="text-xs font-medium"
            >
              Stylometry Charts
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => switchTab('chronology')}
              className="text-xs font-medium"
            >
              Timeline
            </Button>
          </div>
        </div>
      </Card>

      {/* Persistent Non-Probability Notice */}
      <div className="p-3.5 rounded-lg border border-slate-800 bg-slate-900/60 text-xs text-slate-300 flex items-start gap-3">
        <span className="text-amber-400 text-sm leading-none mt-0.5 font-bold" aria-hidden="true">
          ℹ
        </span>
        <div className="space-y-1">
          <p className="font-medium text-slate-200">
            Heuristic Evidence Strengths — Not Identity Probabilities
          </p>
          <p className="text-slate-400 text-[11px] leading-relaxed">
            Scores reflect heuristic evidence strength across shared cryptographic keys, infrastructure, stylometric features, and temporal activities. They do not constitute conclusive real-world identification or legal attribution.
          </p>
        </div>
      </div>

      {/* Linked Personas Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
              Linked Personas ({correlations.length})
            </h2>
            <p className="text-xs text-slate-400">
              Persona pairs correlated across observed threat data.
            </p>
          </div>
        </div>

        {correlations.length === 0 ? (
          <Card className="p-8">
            <EmptyState
              title="No Correlated Persona Pairs"
              message="No persona links have been established yet. Execute the correlation pipeline to calculate multi-dimensional similarity."
              action={
                onTriggerRun ? (
                  <Button variant="primary" size="sm" onClick={onTriggerRun}>
                    Run Correlation Pipeline
                  </Button>
                ) : null
              }
            />
          </Card>
        ) : (
          <Card className="overflow-hidden border-slate-800">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-900/80 text-[11px] font-semibold uppercase tracking-wider text-slate-400 border-b border-slate-800">
                  <tr>
                    <th scope="col" className="py-3 px-4">Persona A</th>
                    <th scope="col" className="py-3 px-4">Persona B</th>
                    <th scope="col" className="py-3 px-4">Evidence Score</th>
                    <th scope="col" className="py-3 px-4">Confidence</th>
                    <th scope="col" className="py-3 px-4">Coverage</th>
                    <th scope="col" className="py-3 px-4">Contradictions</th>
                    <th scope="col" className="py-3 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80">
                  {correlations.map((c) => {
                    const pairKey = `${c.actors.actor_a.id}_${c.actors.actor_b.id}`;
                    const isExpanded = expandedPairId === pairKey;
                    const detail = pairDetails[pairKey];
                    const scorePct = Math.round((c.combined_score || 0) * 100);
                    const covPct = Math.round((c.coverage || 0) * 100);

                    return (
                      <React.Fragment key={c.id || pairKey}>
                        <tr className="hover:bg-slate-800/40 transition-colors">
                          <td className="py-3 px-4">
                            <Link
                              to={`/investigations/${investigationId}/actors/${c.actors.actor_a.id}`}
                              className="font-medium text-sky-400 hover:text-sky-300 hover:underline flex items-center gap-1.5"
                            >
                              <span>{c.actors.actor_a.username}</span>
                              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700">
                                {c.actors.actor_a.marketplace}
                              </span>
                            </Link>
                          </td>
                          <td className="py-3 px-4">
                            <Link
                              to={`/investigations/${investigationId}/actors/${c.actors.actor_b.id}`}
                              className="font-medium text-sky-400 hover:text-sky-300 hover:underline flex items-center gap-1.5"
                            >
                              <span>{c.actors.actor_b.username}</span>
                              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700">
                                {c.actors.actor_b.marketplace}
                              </span>
                            </Link>
                          </td>
                          <td className="py-3 px-4">
                            <div className="flex items-center gap-2">
                              <div className="w-16 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                                <div
                                  className={`h-full rounded-full ${
                                    c.combined_score >= 0.7
                                      ? 'bg-emerald-500'
                                      : c.combined_score >= 0.45
                                      ? 'bg-amber-500'
                                      : 'bg-slate-500'
                                  }`}
                                  style={{ width: `${scorePct}%` }}
                                />
                              </div>
                              <span className="font-mono text-slate-200 font-semibold">
                                {c.combined_score.toFixed(2)}
                              </span>
                            </div>
                          </td>
                          <td className="py-3 px-4">
                            <Badge variant={getLevelBadgeVariant(c.level)}>
                              {c.level ? c.level.toUpperCase() : 'NONE'}
                            </Badge>
                          </td>
                          <td className="py-3 px-4 font-mono text-slate-400">
                            {covPct}%
                          </td>
                          <td className="py-3 px-4">
                            {c.contradiction_count > 0 ? (
                              <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-950/60 text-rose-400 border border-rose-800/80">
                                {c.contradiction_count} conflict{c.contradiction_count > 1 ? 's' : ''}
                              </span>
                            ) : (
                              <span className="text-slate-500 text-[11px]">None</span>
                            )}
                          </td>
                          <td className="py-3 px-4 text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => toggleExpandPair(c)}
                            >
                              {isExpanded ? 'Hide' : 'Details'}
                            </Button>
                          </td>
                        </tr>

                        {isExpanded && (
                          <tr className="bg-slate-900/40">
                            <td colSpan={7} className="p-4 border-b border-slate-800">
                              {loadingDetail && !detail ? (
                                <div className="py-6 flex justify-center items-center gap-2 text-xs text-slate-400">
                                  <Spinner size="sm" />
                                  <span>Loading evidence breakdown...</span>
                                </div>
                              ) : detail ? (
                                <div className="space-y-4">
                                  {/* Dimension Contributions */}
                                  <div>
                                    <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2">
                                      Dimension Contributions
                                    </h4>
                                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
                                      {Object.entries(detail.dimension_scores || {}).map(([dim, info]) => (
                                        <div
                                          key={dim}
                                          className="p-2.5 rounded bg-slate-800/60 border border-slate-700/60 text-xs"
                                        >
                                          <div className="flex items-center justify-between text-slate-400 mb-1">
                                            <span className="capitalize">{dim}</span>
                                            <span className="font-mono text-slate-200">
                                              {(info.score || 0).toFixed(2)}
                                            </span>
                                          </div>
                                          <div className="w-full bg-slate-700 rounded-full h-1 overflow-hidden">
                                            <div
                                              className="bg-sky-400 h-full rounded-full"
                                              style={{ width: `${Math.round((info.score || 0) * 100)}%` }}
                                            />
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>

                                  {/* Contradictions if any */}
                                  {detail.contradictions && detail.contradictions.length > 0 && (
                                    <div className="p-3 rounded bg-rose-950/20 border border-rose-900/60 text-xs text-rose-300">
                                      <h5 className="font-semibold mb-1 text-rose-200">
                                        Contradictory Evidence Identified
                                      </h5>
                                      <ul className="list-disc list-inside space-y-1 text-[11px] text-rose-300">
                                        {detail.contradictions.map((ct, idx) => (
                                          <li key={idx}>
                                            <strong className="capitalize">{ct.dimension}:</strong> {ct.short_text} (strength: {ct.strength})
                                          </li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}

                                  {/* Evidence Items */}
                                  <div>
                                    <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2">
                                      Supporting Evidence ({detail.evidence?.length || 0})
                                    </h4>
                                    <div className="space-y-2">
                                      {detail.evidence && detail.evidence.length > 0 ? (
                                        detail.evidence.map((ev) => (
                                          <div
                                            key={ev.id}
                                            className="p-3 rounded bg-slate-800/40 border border-slate-700/60 text-xs space-y-1.5"
                                          >
                                            <div className="flex items-center justify-between gap-2">
                                              <span className="font-semibold text-slate-200">
                                                {ev.evidence_type}
                                              </span>
                                              <Badge variant={ev.direction === 'supporting' ? 'success' : 'danger'}>
                                                {ev.direction} ({ev.strength})
                                              </Badge>
                                            </div>
                                            <p className="text-slate-300 text-[11px]">
                                              {ev.explanation}
                                            </p>
                                          </div>
                                        ))
                                      ) : (
                                        <p className="text-slate-500 text-xs">No explicit evidence records attached.</p>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              ) : null}
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>

      {/* Threat Personas Directory */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
            Observed Personas ({actors.length})
          </h2>
          <span className="text-xs text-slate-400">Click any persona to inspect deep profile</span>
        </div>

        {actors.length === 0 ? (
          <p className="text-xs text-slate-500">No threat personas observed in this investigation.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
            {actors.map((actor) => (
              <Link
                key={actor.id}
                to={`/investigations/${investigationId}/actors/${actor.id}`}
                className="p-3.5 rounded-lg border border-slate-800 bg-slate-900/50 hover:bg-slate-800/70 hover:border-slate-700 transition-all flex flex-col justify-between group"
              >
                <div>
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="text-xs font-semibold text-slate-200 group-hover:text-sky-300 truncate">
                      {actor.username}
                    </span>
                    <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700">
                      {actor.marketplace}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400 font-mono">
                    {actor.post_count} posts
                  </div>
                </div>

                <div className="mt-3 pt-2 border-t border-slate-800 flex items-center justify-between text-[10px]">
                  <span className="text-slate-500">Top Match</span>
                  <span className="font-mono text-slate-300 font-medium">
                    {actor.best_correlated_partner_score !== null && actor.best_correlated_partner_score !== undefined
                      ? (actor.best_correlated_partner_score).toFixed(2)
                      : '—'}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Collapsible Raw Source Data */}
      <div className="space-y-3 pt-4 border-t border-slate-800">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Source Data View
            </h3>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setShowSourceData(!showSourceData)}
            >
              {showSourceData ? 'Hide Source Data' : 'Show Source Data (Posts & Indicators)'}
            </Button>
          </div>

          {showSourceData && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setSourceDataSubTab('posts')}
                className={`px-3 py-1 rounded text-xs font-medium cursor-pointer ${
                  sourceDataSubTab === 'posts'
                    ? 'bg-slate-700 text-slate-200'
                    : 'text-slate-400 hover:text-slate-300'
                }`}
              >
                Posts
              </button>
              <button
                type="button"
                onClick={() => setSourceDataSubTab('indicators')}
                className={`px-3 py-1 rounded text-xs font-medium cursor-pointer ${
                  sourceDataSubTab === 'indicators'
                    ? 'bg-slate-700 text-slate-200'
                    : 'text-slate-400 hover:text-slate-300'
                }`}
              >
                Indicators
              </button>
            </div>
          )}
        </div>

        {showSourceData && (
          <div className="mt-3">
            {sourceDataSubTab === 'posts' ? (
              <PostsTable investigationId={investigationId} />
            ) : (
              <IndicatorsTable investigationId={investigationId} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
