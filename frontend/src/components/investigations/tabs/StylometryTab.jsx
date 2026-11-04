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
import { fetchAnalysisActors, compareStylometryTextApi } from '../../../lib/api';

const ACTOR_COLORS = ['#0284c7', '#10b981', '#f59e0b', '#ec4899'];

export default function StylometryTab({ investigationId, runId }) {
  const [actors, setActors] = useState([]);
  const [selectedActorIds, setSelectedActorIds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Custom text comparison state
  const [sampleTextA, setSampleTextA] = useState('');
  const [sampleTextB, setSampleTextB] = useState('');
  const [comparing, setComparing] = useState(false);
  const [compareResult, setCompareResult] = useState(null);
  const [compareError, setCompareError] = useState(null);

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
      setError(err.message || 'Failed to load stylometry analyses.');
    } finally {
      setLoading(false);
    }
  }, [investigationId, runId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const toggleSelectActor = (aid) => {
    if (selectedActorIds.includes(aid)) {
      if (selectedActorIds.length > 2) {
        setSelectedActorIds(selectedActorIds.filter((id) => id !== aid));
      }
    } else {
      if (selectedActorIds.length < 4) {
        setSelectedActorIds([...selectedActorIds, aid]);
      }
    }
  };

  const handleRunCustomCompare = async (e) => {
    e.preventDefault();
    if (!sampleTextA.trim() || !sampleTextB.trim()) {
      setCompareError('Please enter text for both Sample A and Sample B.');
      return;
    }

    setComparing(true);
    setCompareError(null);
    try {
      const res = await compareStylometryTextApi(
        sampleTextA.trim(),
        sampleTextB.trim(),
        'Submitted Sample A',
        'Submitted Sample B'
      );
      setCompareResult(res);
    } catch (err) {
      setCompareError(err.message || 'Custom stylometry comparison failed.');
    } finally {
      setComparing(false);
    }
  };

  if (loading) {
    return (
      <div className="py-20 flex flex-col items-center justify-center gap-3">
        <Spinner size="md" />
        <span className="text-xs text-slate-400 font-mono">Analyzing linguistic feature vectors...</span>
      </div>
    );
  }

  if (error) {
    return (
      <Card className="p-6">
        <EmptyState
          title="Stylometry Data Unavailable"
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
          title="No Stylometric Writeprints"
          message="No threat personas available for stylometric analysis. Run the correlation pipeline to extract n-grams and linguistic features."
        />
      </Card>
    );
  }

  const selectedActors = actors.filter((a) => selectedActorIds.includes(a.actor_id));

  // Feature Comparison Chart Data
  const featureChartData = [
    {
      feature: 'Avg Sentence Len',
      unit: 'words',
    },
    {
      feature: 'Avg Word Len',
      unit: 'chars',
    },
    {
      feature: 'Punctuation Rate',
      unit: 'per 100w',
    },
    {
      feature: 'Digit Rate',
      unit: 'per 100w',
    },
    {
      feature: 'Uppercase Rate',
      unit: 'per 100w',
    },
  ];

  featureChartData.forEach((row) => {
    selectedActors.forEach((a) => {
      const feats = a.stylometry || {};
      let val = 0;
      if (row.feature === 'Avg Sentence Len') val = feats.avg_sentence_len || 0;
      else if (row.feature === 'Avg Word Len') val = (feats.avg_word_len || 0) * 4; // scale for visibility
      else if (row.feature === 'Punctuation Rate') val = (feats.punctuation_rate || 0) * 100;
      else if (row.feature === 'Digit Rate') val = (feats.digit_rate || 0) * 100;
      else if (row.feature === 'Uppercase Rate') val = (feats.uppercase_rate || 0) * 100;
      row[a.username] = parseFloat(val.toFixed(2));
    });
  });

  return (
    <div className="space-y-6">
      {/* Persona Selector (2 to 4) */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-xs font-semibold uppercase tracking-wider text-slate-200">
            Compare Personas (Select 2 to 4)
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

      {/* Feature Comparison Chart */}
      <div className="space-y-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
          Linguistic Feature Comparison
        </h3>

        <Card className="p-4 border-slate-800">
          <div className="w-full h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={featureChartData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} />
                <XAxis
                  dataKey="feature"
                  stroke="#94a3b8"
                  tick={{ fill: '#94a3b8', fontSize: 11 }}
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

      {/* Top Distinctive Vocabulary & Phrases */}
      <div className="space-y-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
          Distinctive Vocabulary & TF-IDF Terms
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {selectedActors.map((actor, idx) => {
            const terms = actor.tfidf_summary || [];
            const color = ACTOR_COLORS[idx % ACTOR_COLORS.length];

            return (
              <Card key={actor.actor_id} className="p-4 border-slate-800 relative">
                <div
                  className="absolute top-0 left-0 w-full h-1 rounded-t-lg"
                  style={{ backgroundColor: color }}
                />
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-xs font-semibold text-slate-200">{actor.username}</h4>
                  <span className="text-[10px] font-mono text-slate-500">
                    {actor.marketplace}
                  </span>
                </div>

                <div className="space-y-1.5">
                  <span className="text-[10px] uppercase font-semibold text-slate-400">
                    Top Characteristic Terms
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {terms.length > 0 ? (
                      terms.slice(0, 10).map((t, tIdx) => (
                        <span
                          key={tIdx}
                          className="px-2 py-0.5 rounded text-[11px] font-mono bg-slate-800 text-slate-300 border border-slate-700"
                        >
                          {t}
                        </span>
                      ))
                    ) : (
                      <span className="text-xs text-slate-500">No distinctive terms indexed.</span>
                    )}
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Interactive Custom Text Comparison Card */}
      <Card className="p-5 border-slate-800 space-y-4">
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
            Interactive Stylometric Sample Comparator
          </h3>
          <p className="text-xs text-slate-400">
            Submit custom communication samples to compare stylistic writeprints and function-word habits.
          </p>
        </div>

        <form onSubmit={handleRunCustomCompare} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label htmlFor="sample-a" className="text-xs font-medium text-slate-300">
                Sample A Text
              </label>
              <textarea
                id="sample-a"
                rows={5}
                value={sampleTextA}
                onChange={(e) => setSampleTextA(e.target.value)}
                placeholder="Paste forum message, listing description, or intercepted note A..."
                className="w-full bg-slate-900 border border-slate-800 text-xs text-slate-200 rounded p-2.5 font-mono focus:outline-none focus:border-slate-600"
              />
              <span className="text-[10px] text-slate-500 font-mono">
                {sampleTextA.trim() ? sampleTextA.trim().split(/\s+/).length : 0} words
              </span>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="sample-b" className="text-xs font-medium text-slate-300">
                Sample B Text
              </label>
              <textarea
                id="sample-b"
                rows={5}
                value={sampleTextB}
                onChange={(e) => setSampleTextB(e.target.value)}
                placeholder="Paste forum message, listing description, or intercepted note B..."
                className="w-full bg-slate-900 border border-slate-800 text-xs text-slate-200 rounded p-2.5 font-mono focus:outline-none focus:border-slate-600"
              />
              <span className="text-[10px] text-slate-500 font-mono">
                {sampleTextB.trim() ? sampleTextB.trim().split(/\s+/).length : 0} words
              </span>
            </div>
          </div>

          {compareError && (
            <div className="p-3 rounded bg-rose-950/40 border border-rose-900/60 text-xs text-rose-300">
              {compareError}
            </div>
          )}

          <div className="flex items-center justify-between">
            <span className="text-[11px] text-slate-500">
              * Recommended minimum sample length is 200+ words per text for statistical validity.
            </span>
            <Button variant="primary" size="sm" type="submit" loading={comparing}>
              Compare Samples
            </Button>
          </div>
        </form>

        {/* Custom Compare Results */}
        {compareResult && (
          <div className="mt-4 pt-4 border-t border-slate-800 space-y-3">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
              Comparison Assessment
            </h4>

            {compareResult.pairwise_similarities && compareResult.pairwise_similarities.length > 0 && (
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                {(() => {
                  const p = compareResult.pairwise_similarities[0];
                  return (
                    <>
                      <div className="p-2.5 rounded bg-slate-900 border border-slate-800 text-xs">
                        <span className="text-slate-400 text-[10px] uppercase">Overall Match</span>
                        <div className="font-mono text-base font-bold text-sky-400 mt-1">
                          {(p.overall || 0).toFixed(2)}
                        </div>
                      </div>
                      <div className="p-2.5 rounded bg-slate-900 border border-slate-800 text-xs">
                        <span className="text-slate-400 text-[10px] uppercase">Function Words</span>
                        <div className="font-mono text-base font-bold text-slate-200 mt-1">
                          {(p.function_words || 0).toFixed(2)}
                        </div>
                      </div>
                      <div className="p-2.5 rounded bg-slate-900 border border-slate-800 text-xs">
                        <span className="text-slate-400 text-[10px] uppercase">Word N-grams</span>
                        <div className="font-mono text-base font-bold text-slate-200 mt-1">
                          {(p.word_ngram || 0).toFixed(2)}
                        </div>
                      </div>
                      <div className="p-2.5 rounded bg-slate-900 border border-slate-800 text-xs">
                        <span className="text-slate-400 text-[10px] uppercase">Char N-grams</span>
                        <div className="font-mono text-base font-bold text-slate-200 mt-1">
                          {(p.char_ngram || 0).toFixed(2)}
                        </div>
                      </div>
                      <div className="p-2.5 rounded bg-slate-900 border border-slate-800 text-xs">
                        <span className="text-slate-400 text-[10px] uppercase">Feature Vector</span>
                        <div className="font-mono text-base font-bold text-slate-200 mt-1">
                          {(p.feature_vector || 0).toFixed(2)}
                        </div>
                      </div>
                    </>
                  );
                })()}
              </div>
            )}

            {compareResult.caveats && (
              <div className="p-3 rounded bg-slate-900/80 border border-slate-800 text-[11px] text-slate-400 space-y-1">
                <span className="font-semibold text-slate-300">Methodological Caveats:</span>
                <ul className="list-disc list-inside space-y-0.5">
                  {compareResult.caveats.map((c, cIdx) => (
                    <li key={cIdx}>{c}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}

