import React, { useState, useEffect, useCallback } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from 'recharts';
import Card from '../../ui/Card';
import Badge from '../../ui/Badge';
import Button from '../../ui/Button';
import Spinner from '../../ui/Spinner';
import EmptyState from '../../ui/EmptyState';
import { fetchAnalysisActors } from '../../../lib/api';

const ACTOR_COLORS = ['#0284c7', '#10b981', '#f59e0b', '#ec4899'];
const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export default function BehaviourTab({ investigationId, runId }) {
  const [actors, setActors] = useState([]);
  const [selectedActorIds, setSelectedActorIds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetchAnalysisActors(investigationId, runId);
      const list = Array.isArray(res) ? res : [];
      setActors(list);

      // Pre-select first 2-3 actors by default
      if (list.length > 0 && selectedActorIds.length === 0) {
        setSelectedActorIds(list.slice(0, Math.min(3, list.length)).map((a) => a.actor_id));
      }
    } catch (err) {
      setError(err.message || 'Failed to load behavioral profiles.');
    } finally {
      setLoading(false);
    }
  }, [investigationId, runId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const toggleSelectActor = (aid) => {
    if (selectedActorIds.includes(aid)) {
      if (selectedActorIds.length > 1) {
        setSelectedActorIds(selectedActorIds.filter((id) => id !== aid));
      }
    } else {
      if (selectedActorIds.length < 4) {
        setSelectedActorIds([...selectedActorIds, aid]);
      }
    }
  };

  if (loading) {
    return (
      <div className="py-20 flex flex-col items-center justify-center gap-3">
        <Spinner size="md" />
        <span className="text-xs text-slate-400 font-mono">Analyzing behavioral writeprints...</span>
      </div>
    );
  }

  if (error) {
    return (
      <Card className="p-6">
        <EmptyState
          title="Behavioral Data Unavailable"
          message={error}
          action={
            <Button variant="secondary" size="sm" onClick={loadData}>
              Retry
            </Button>
          }
        />
      </Card>
    );
  }

  if (actors.length === 0) {
    return (
      <Card className="p-8">
        <EmptyState
          title="No Behavioral Profiles"
          message="No threat personas available for behavioral profiling. Run the correlation pipeline to generate temporal distributions."
        />
      </Card>
    );
  }

  const selectedActors = actors.filter((a) => selectedActorIds.includes(a.actor_id));

  // Build 24-hour chart data
  const hourlyChartData = [];
  for (let h = 0; h < 24; h++) {
    const entry = { hour: `${h.toString().padStart(2, '0')}:00` };
    selectedActors.forEach((a) => {
      const dist = a.behaviour?.hourly_distribution || [];
      const val = dist[h] !== undefined ? dist[h] * 100 : 0;
      entry[a.username] = parseFloat(val.toFixed(1));
    });
    hourlyChartData.push(entry);
  }

  // Build 7-day chart data
  const dailyChartData = [];
  for (let d = 0; d < 7; d++) {
    const entry = { day: DAY_LABELS[d] };
    selectedActors.forEach((a) => {
      const dist = a.behaviour?.daily_distribution || [];
      const val = dist[d] !== undefined ? dist[d] * 100 : 0;
      entry[a.username] = parseFloat(val.toFixed(1));
    });
    dailyChartData.push(entry);
  }

  return (
    <div className="space-y-6">
      {/* Persona Selector (up to 4) */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-xs font-semibold uppercase tracking-wider text-slate-200">
            Compare Personas (Select up to 4)
          </label>
          <span className="text-xs text-slate-400">
            {selectedActorIds.length} / 4 selected
          </span>
        </div>

        <div className="flex flex-wrap gap-2">
          {actors.map((actor) => {
            const isSelected = selectedActorIds.includes(actor.actor_id);
            const colorIdx = isSelected
              ? selectedActorIds.indexOf(actor.actor_id) % ACTOR_COLORS.length
              : -1;
            const badgeColor = isSelected ? ACTOR_COLORS[colorIdx] : null;

            return (
              <button
                key={actor.actor_id}
                type="button"
                onClick={() => toggleSelectActor(actor.actor_id)}
                className={`px-3 py-1.5 rounded text-xs font-medium transition-all cursor-pointer flex items-center gap-1.5 border ${
                  isSelected
                    ? 'bg-slate-800 text-slate-100 border-slate-600 shadow-xs'
                    : 'bg-slate-900/60 text-slate-400 border-slate-800 hover:border-slate-700 hover:text-slate-200'
                }`}
              >
                {isSelected && (
                  <span
                    className="w-2.5 h-2.5 rounded-full inline-block"
                    style={{ backgroundColor: badgeColor }}
                  />
                )}
                <span>{actor.username}</span>
                <span className="text-[10px] font-mono text-slate-500">
                  ({actor.marketplace})
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Persona Stats Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {selectedActors.map((actor, idx) => {
          const b = actor.behaviour || {};
          const isLowData = b.sufficiency === 'insufficient' || (b.total_posts || 0) < 5;
          const color = ACTOR_COLORS[idx % ACTOR_COLORS.length];

          return (
            <Card key={actor.actor_id} className="p-4 border-slate-800 relative">
              <div
                className="absolute top-0 left-0 w-full h-1 rounded-t-lg"
                style={{ backgroundColor: color }}
              />
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-xs font-semibold text-slate-200 truncate">{actor.username}</h4>
                <Badge variant={b.sufficiency === 'sufficient' ? 'success' : isLowData ? 'danger' : 'warning'}>
                  {b.sufficiency ? b.sufficiency.toUpperCase() : 'UNKNOWN'}
                </Badge>
              </div>

              {isLowData && (
                <div className="mb-2 px-2 py-1 rounded bg-rose-950/40 border border-rose-900/50 text-[10px] text-rose-300">
                  ⚠ Low post volume ({b.total_posts || 0} posts). Statistical patterns may be unreliable.
                </div>
              )}

              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between text-slate-400">
                  <span>Peak Active Window:</span>
                  <span className="font-mono text-slate-200">
                    {b.active_hour_window_str || 'N/A'}
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Peak Hour (UTC):</span>
                  <span className="font-mono text-slate-200">
                    {b.peak_hour !== undefined ? `${b.peak_hour}:00` : 'N/A'}
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Posts per Active Day:</span>
                  <span className="font-mono text-slate-200">
                    {b.posts_per_active_day ? b.posts_per_active_day.toFixed(1) : '—'}
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Posts per Week:</span>
                  <span className="font-mono text-slate-200">
                    {b.posts_per_week ? b.posts_per_week.toFixed(1) : '—'}
                  </span>
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {/* 24-Hour Hourly Activity Chart */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
            24-Hour Diurnal Activity Distribution (% of posts)
          </h3>
          <span className="text-xs text-slate-400 font-mono">UTC Timezone</span>
        </div>

        <Card className="p-4 border-slate-800">
          <div className="w-full h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={hourlyChartData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} />
                <XAxis
                  dataKey="hour"
                  stroke="#94a3b8"
                  tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'monospace' }}
                />
                <YAxis
                  stroke="#94a3b8"
                  tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'monospace' }}
                  unit="%"
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    borderColor: '#334155',
                    fontSize: '12px',
                    color: '#f8fafc',
                  }}
                />
                <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
                {selectedActors.map((actor, idx) => (
                  <Bar
                    key={actor.actor_id}
                    dataKey={actor.username}
                    fill={ACTOR_COLORS[idx % ACTOR_COLORS.length]}
                    radius={[2, 2, 0, 0]}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      {/* 7-Day Day-of-Week Activity Chart */}
      <div className="space-y-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
          Day of Week Activity Distribution (% of posts)
        </h3>

        <Card className="p-4 border-slate-800">
          <div className="w-full h-60">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={dailyChartData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} />
                <XAxis
                  dataKey="day"
                  stroke="#94a3b8"
                  tick={{ fill: '#94a3b8', fontSize: 11 }}
                />
                <YAxis
                  stroke="#94a3b8"
                  tick={{ fill: '#94a3b8', fontSize: 10, fontFamily: 'monospace' }}
                  unit="%"
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    borderColor: '#334155',
                    fontSize: '12px',
                    color: '#f8fafc',
                  }}
                />
                <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }} />
                {selectedActors.map((actor, idx) => (
                  <Bar
                    key={actor.actor_id}
                    dataKey={actor.username}
                    fill={ACTOR_COLORS[idx % ACTOR_COLORS.length]}
                    radius={[2, 2, 0, 0]}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
    </div>
  );
}

