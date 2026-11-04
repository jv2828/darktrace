import React, { useState } from 'react';
import EvidenceCard from './EvidenceCard';
import StrengthBar from './StrengthBar';

export default function PairsTable({
  pairs = [],
  evidenceList = [],
  investigationId,
  onFilterChange,
}) {
  const [expandedPairs, setExpandedPairs] = useState(new Set());
  const [dimensionFilter, setDimensionFilter] = useState('');
  const [minStrengthFilter, setMinStrengthFilter] = useState('0.0');

  const toggleExpand = (pairKey) => {
    setExpandedPairs((prev) => {
      const next = new Set(prev);
      if (next.has(pairKey)) {
        next.delete(pairKey);
      } else {
        next.add(pairKey);
      }
      return next;
    });
  };

  // Filter pairs
  const filteredPairs = pairs.filter((p) => {
    if (minStrengthFilter) {
      const minVal = parseFloat(minStrengthFilter);
      if (p.max_strength < minVal) return false;
    }
    if (dimensionFilter) {
      if (!p.per_dimension || !p.per_dimension[dimensionFilter]) return false;
    }
    return true;
  });

  return (
    <div className="space-y-4">
      {/* Filtering Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-lg bg-zinc-900/60 border border-zinc-800 text-xs">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-zinc-400 font-medium">Dimension:</span>
            <select
              value={dimensionFilter}
              onChange={(e) => setDimensionFilter(e.target.value)}
              className="bg-zinc-800 border border-zinc-700 text-zinc-200 rounded px-2 py-1 text-xs focus:outline-none focus:border-zinc-500"
            >
              <option value="">All Dimensions</option>
              <option value="cryptographic">Cryptographic</option>
              <option value="infrastructure">Infrastructure</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-zinc-400 font-medium">Min Strength:</span>
            <select
              value={minStrengthFilter}
              onChange={(e) => setMinStrengthFilter(e.target.value)}
              className="bg-zinc-800 border border-zinc-700 text-zinc-200 rounded px-2 py-1 text-xs focus:outline-none focus:border-zinc-500"
            >
              <option value="0.0">0.0 (All)</option>
              <option value="0.30">0.30 (Meaningful)</option>
              <option value="0.50">0.50 (Moderate)</option>
              <option value="0.80">0.80 (Strong)</option>
            </select>
          </div>
        </div>

        <div className="text-zinc-400">
          Showing <span className="font-semibold text-zinc-200">{filteredPairs.length}</span> of{' '}
          <span className="font-semibold text-zinc-200">{pairs.length}</span> persona pairs
        </div>
      </div>

      {/* Pairs List */}
      {filteredPairs.length === 0 ? (
        <div className="p-8 text-center rounded-lg border border-dashed border-zinc-800 text-zinc-500 text-sm">
          No shared indicators match the selected filters.
        </div>
      ) : (
        <div className="space-y-3">
          {filteredPairs.map((pair, pIdx) => {
            const a = pair.actors.actor_a;
            const b = pair.actors.actor_b;
            const pairKey = `${a.id}-${b.id}`;
            const isExpanded = expandedPairs.has(pairKey);

            // Find all evidence records for this pair
            const pairEvidence = evidenceList.filter((ev) => {
              const matchesPair =
                (ev.actor_a.id === a.id && ev.actor_b.id === b.id) ||
                (ev.actor_a.id === b.id && ev.actor_b.id === a.id);
              if (!matchesPair) return false;
              if (dimensionFilter && ev.dimension !== dimensionFilter) return false;
              if (minStrengthFilter && ev.strength < parseFloat(minStrengthFilter)) return false;
              return true;
            });

            return (
              <div
                key={pairKey}
                className="rounded-lg border border-zinc-800 bg-zinc-900/40 overflow-hidden transition-all"
              >
                {/* Header row */}
                <div
                  onClick={() => toggleExpand(pairKey)}
                  className="p-4 flex flex-wrap items-center justify-between gap-4 cursor-pointer hover:bg-zinc-800/30 transition-colors select-none"
                >
                  <div className="flex items-center gap-3">
                    {/* Persona A */}
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-medium text-sm text-zinc-200">
                        @{a.username}
                      </span>
                      <span className="px-1.5 py-0.5 rounded text-[11px] bg-zinc-800 text-zinc-400 border border-zinc-700">
                        {a.marketplace}
                      </span>
                    </div>

                    <span className="text-zinc-600 font-bold">↔</span>

                    {/* Persona B */}
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-medium text-sm text-zinc-200">
                        @{b.username}
                      </span>
                      <span className="px-1.5 py-0.5 rounded text-[11px] bg-zinc-800 text-zinc-400 border border-zinc-700">
                        {b.marketplace}
                      </span>
                    </div>
                  </div>

                  {/* Badges and max strength */}
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                      {pair.per_dimension &&
                        Object.entries(pair.per_dimension).map(([dim, data]) => (
                          <span
                            key={dim}
                            className={`px-2 py-0.5 rounded text-xs border font-mono ${
                              dim === 'cryptographic'
                                ? 'bg-purple-950/40 text-purple-300 border-purple-800/60'
                                : 'bg-blue-950/40 text-blue-300 border-blue-800/60'
                            }`}
                          >
                            {dim.slice(0, 6)}: {data.max_strength.toFixed(2)} ({data.count})
                          </span>
                        ))}
                    </div>

                    <StrengthBar strength={pair.max_strength} />

                    <button
                      type="button"
                      className="p-1 rounded text-zinc-400 hover:text-zinc-200 focus:outline-none"
                    >
                      <svg
                        className={`w-4 h-4 transition-transform duration-200 ${
                          isExpanded ? 'rotate-180' : ''
                        }`}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>
                  </div>
                </div>

                {/* Expanded evidence list */}
                {isExpanded && (
                  <div className="p-4 border-t border-zinc-800/80 bg-zinc-950/40">
                    <div className="text-xs font-semibold text-zinc-400 mb-3 flex items-center justify-between">
                      <span>Supporting Evidence ({pairEvidence.length} items):</span>
                      <span className="text-[11px] text-zinc-500 font-normal">
                        Individual heuristic matching items linking this pair
                      </span>
                    </div>

                    {pairEvidence.length === 0 ? (
                      <div className="text-xs text-zinc-500 italic p-3">
                        No individual evidence items match the current filters.
                      </div>
                    ) : (
                      pairEvidence.map((ev) => (
                        <EvidenceCard
                          key={ev.id}
                          evidence={ev}
                          investigationId={investigationId}
                        />
                      ))
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

