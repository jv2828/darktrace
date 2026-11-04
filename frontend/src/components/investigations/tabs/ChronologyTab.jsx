import React, { useState, useEffect, useCallback } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import Card from '../../ui/Card';
import Badge from '../../ui/Badge';
import Button from '../../ui/Button';
import Spinner from '../../ui/Spinner';
import EmptyState from '../../ui/EmptyState';
import { fetchInvestigationChronology } from '../../../lib/api';

export default function ChronologyTab({ investigationId, runId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters
  const [sharedOnly, setSharedOnly] = useState(true);
  const [copiedValue, setCopiedValue] = useState(null);

  const loadChronology = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetchInvestigationChronology(investigationId, { run_id: runId });
      setData(res);
    } catch (err) {
      setError(err.message || 'Failed to fetch case chronology.');
    } finally {
      setLoading(false);
    }
  }, [investigationId, runId]);

  useEffect(() => {
    loadChronology();
  }, [loadChronology]);

  const handleCopy = (val) => {
    navigator.clipboard?.writeText(val);
    setCopiedValue(val);
    setTimeout(() => setCopiedValue(null), 2000);
  };

  if (loading) {
    return (
      <div className="py-20 flex flex-col items-center justify-center gap-3">
        <Spinner size="md" />
        <span className="text-xs text-slate-400 font-mono">Aggregating temporal case activity...</span>
      </div>
    );
  }

  if (error) {
    return (
      <Card className="p-6">
        <EmptyState
          title="Chronology Error"
          message={error}
          action={
            <Button variant="secondary" size="sm" onClick={loadChronology}>
              Retry
            </Button>
          }
        />
      </Card>
    );
  }

  const postsByDay = data?.posts_by_day || [];
  const rawIndicators = data?.indicator_first_seen || [];
  const runs = data?.runs || [];
  const evidenceEvents = data?.evidence_events || [];

  // Filter indicators
  const indicators = sharedOnly
    ? rawIndicators.filter((ind) => ind.is_shared)
    : rawIndicators;

  // Aggregate posts by day for chart
  const dayAggMap = {};
  postsByDay.forEach((p) => {
    const dayStr = p.date ? p.date.substring(0, 10) : 'Unknown';
    if (!dayAggMap[dayStr]) {
      dayAggMap[dayStr] = { date: dayStr, total_posts: 0 };
    }
    dayAggMap[dayStr].total_posts += p.count;
  });
  const chartData = Object.values(dayAggMap).sort((a, b) => a.date.localeCompare(b.date));

  return (
    <div className="space-y-6">
      {/* 1. Activity Over Time Chart */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
            Temporal Activity Volume
          </h2>
          <span className="text-xs text-slate-400">Total daily darknet communications</span>
        </div>

        <Card className="p-4 border-slate-800">
          {chartData.length === 0 ? (
            <div className="py-12 text-center text-xs text-slate-500">
              No dated post timestamps available for this case.
            </div>
          ) : (
            <div className="w-full h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} />
                  <XAxis
                    dataKey="date"
                    stroke="#94a3b8"
                    tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'monospace' }}
                  />
                  <YAxis
                    stroke="#94a3b8"
                    tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'monospace' }}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderColor: '#334155',
                      fontSize: '12px',
                      color: '#f8fafc',
                    }}
                  />
                  <Bar dataKey="total_posts" fill="#0284c7" radius={[4, 4, 0, 0]} name="Post Count" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
      </div>

      {/* 2. Indicator First-Seen Chronology */}
      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
              Indicator Emergence Chronology ({indicators.length})
            </h2>
            <p className="text-xs text-slate-400">Earliest observed emergence of threat indicators</p>
          </div>

          <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-300 select-none">
            <input
              type="checkbox"
              checked={sharedOnly}
              onChange={() => setSharedOnly(!sharedOnly)}
              className="rounded border-slate-700 bg-slate-800 text-sky-500 focus:ring-0"
            />
            <span>Shared indicators only (used by &ge; 2 personas)</span>
          </label>
        </div>

        <Card className="overflow-hidden border-slate-800">
          {indicators.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-500">
              No matching indicators found for current filter.
            </div>
          ) : (
            <div className="overflow-x-auto max-h-96">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-900/80 text-[11px] font-semibold uppercase tracking-wider text-slate-400 border-b border-slate-800 sticky top-0 backdrop-blur-xs">
                  <tr>
                    <th scope="col" className="py-2.5 px-3">Type</th>
                    <th scope="col" className="py-2.5 px-3">Normalised Value</th>
                    <th scope="col" className="py-2.5 px-3">First Seen</th>
                    <th scope="col" className="py-2.5 px-3">Last Seen</th>
                    <th scope="col" className="py-2.5 px-3">Personas</th>
                    <th scope="col" className="py-2.5 px-3 text-right">Posts</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80 font-mono text-[11px]">
                  {indicators.map((ind, idx) => {
                    const isCopied = copiedValue === ind.normalised_value;
                    const valPreview =
                      ind.normalised_value.length > 32
                        ? `${ind.normalised_value.substring(0, 16)}…${ind.normalised_value.slice(-12)}`
                        : ind.normalised_value;

                    return (
                      <tr key={idx} className="hover:bg-slate-800/30">
                        <td className="py-2.5 px-3">
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
                              title="Copy full value"
                            >
                              {isCopied ? '✓' : '⧉'}
                            </button>
                          </div>
                        </td>
                        <td className="py-2.5 px-3 text-slate-400">
                          {ind.first_seen ? ind.first_seen.substring(0, 10) : '—'}
                        </td>
                        <td className="py-2.5 px-3 text-slate-400">
                          {ind.last_seen ? ind.last_seen.substring(0, 10) : '—'}
                        </td>
                        <td className="py-2.5 px-3 font-sans">
                          {ind.persona_count > 1 ? (
                            <span className="px-1.5 py-0.2 rounded text-[10px] bg-emerald-950/60 text-emerald-400 border border-emerald-800/80">
                              {ind.persona_count} personas
                            </span>
                          ) : (
                            <span className="text-slate-500">1 persona</span>
                          )}
                        </td>
                        <td className="py-2.5 px-3 text-right text-slate-400">
                          {ind.post_count}
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

      {/* 3. Evidence Events Log */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
            Top Evidence Events ({evidenceEvents.length})
          </h2>
          <span className="text-xs text-slate-400">Ranked by heuristic evidence strength</span>
        </div>

        <Card className="overflow-hidden border-slate-800">
          {evidenceEvents.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-500">
              No correlation evidence records available yet.
            </div>
          ) : (
            <div className="overflow-x-auto max-h-80">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-900/80 text-[11px] font-semibold uppercase tracking-wider text-slate-400 border-b border-slate-800 sticky top-0 backdrop-blur-xs">
                  <tr>
                    <th scope="col" className="py-2.5 px-3">Persona Pair</th>
                    <th scope="col" className="py-2.5 px-3">Dimension</th>
                    <th scope="col" className="py-2.5 px-3">Strength</th>
                    <th scope="col" className="py-2.5 px-3">Evidence Explanation</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80">
                  {evidenceEvents.map((ev, idx) => (
                    <tr key={idx} className="hover:bg-slate-800/30">
                      <td className="py-2.5 px-3 font-mono text-slate-200">
                        {ev.actor_a?.username} &harr; {ev.actor_b?.username}
                      </td>
                      <td className="py-2.5 px-3">
                        <Badge variant="outline">{ev.dimension}</Badge>
                      </td>
                      <td className="py-2.5 px-3 font-mono font-semibold text-sky-400">
                        {ev.strength.toFixed(2)}
                      </td>
                      <td className="py-2.5 px-3 text-slate-300 text-[11px]">
                        {ev.explanation}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>

      {/* 4. Pipeline Execution History */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
          Correlation Pipeline Runs ({runs.length})
        </h2>

        <Card className="overflow-hidden border-slate-800">
          {runs.length === 0 ? (
            <div className="p-6 text-center text-xs text-slate-500">
              No pipeline runs recorded.
            </div>
          ) : (
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-900/80 text-[11px] font-semibold uppercase tracking-wider text-slate-400 border-b border-slate-800">
                <tr>
                  <th scope="col" className="py-2.5 px-3">Run ID</th>
                  <th scope="col" className="py-2.5 px-3">Status</th>
                  <th scope="col" className="py-2.5 px-3">Started</th>
                  <th scope="col" className="py-2.5 px-3">Completed</th>
                  <th scope="col" className="py-2.5 px-3 text-right">Pairs Scored</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80 font-mono text-[11px]">
                {runs.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-800/30">
                    <td className="py-2.5 px-3 text-slate-200">#{r.id}</td>
                    <td className="py-2.5 px-3 font-sans">
                      <Badge variant={r.status === 'completed' ? 'success' : 'neutral'}>
                        {r.status?.toUpperCase()}
                      </Badge>
                    </td>
                    <td className="py-2.5 px-3 text-slate-400">
                      {r.started_at ? new Date(r.started_at).toLocaleString() : '—'}
                    </td>
                    <td className="py-2.5 px-3 text-slate-400">
                      {r.finished_at ? new Date(r.finished_at).toLocaleString() : '—'}
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-200">
                      {r.pairs_scored ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </div>
  );
}

