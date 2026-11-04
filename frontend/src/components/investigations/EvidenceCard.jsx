import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import StrengthBar from './StrengthBar';

export default function EvidenceCard({ evidence, investigationId }) {
  const [expandedDetails, setExpandedDetails] = useState(false);

  const getDimensionBadgeClass = (dim) => {
    if (dim === 'cryptographic') {
      return 'bg-purple-950/60 text-purple-300 border-purple-800/60';
    }
    if (dim === 'infrastructure') {
      return 'bg-blue-950/60 text-blue-300 border-blue-800/60';
    }
    return 'bg-zinc-800 text-zinc-300 border-zinc-700';
  };

  return (
    <div className="p-4 rounded-lg bg-zinc-950/70 border border-zinc-800/80 mb-3 hover:border-zinc-700/80 transition-all">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-2.5">
        <div className="flex items-center gap-2">
          <span
            className={`px-2 py-0.5 rounded text-xs font-semibold border ${getDimensionBadgeClass(
              evidence.dimension
            )}`}
          >
            {evidence.dimension.toUpperCase()}
          </span>
          <span className="px-2 py-0.5 rounded text-xs font-mono bg-zinc-800/80 text-zinc-300 border border-zinc-700">
            {evidence.evidence_type}
          </span>
        </div>

        <StrengthBar strength={evidence.strength} />
      </div>

      <p className="text-sm text-zinc-300 leading-relaxed mb-3">{evidence.explanation}</p>

      {/* Sources list */}
      {evidence.sources && evidence.sources.length > 0 && (
        <div className="mt-3 pt-3 border-t border-zinc-900 space-y-2">
          <div className="text-xs font-medium text-zinc-400">
            Traceable Evidence Sources ({evidence.sources.length}):
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {evidence.sources.map((src, sIdx) => {
              const p = src.post;
              const ind = src.indicator;
              if (!p && !ind) return null;

              return (
                <div
                  key={sIdx}
                  className="p-2.5 rounded bg-zinc-900/50 border border-zinc-800/60 text-xs space-y-1.5"
                >
                  <div className="flex items-center justify-between gap-2">
                    {p ? (
                      <Link
                        to={`/investigations/${investigationId}/posts/${p.id}`}
                        className="text-cyan-400 hover:text-cyan-300 font-mono font-medium underline underline-offset-2 flex items-center gap-1"
                      >
                        <span>Post #{p.id}</span>
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                        </svg>
                      </Link>
                    ) : (
                      <span className="text-zinc-500 font-mono">Direct artifact</span>
                    )}

                    {p && (
                      <span className="text-[11px] text-zinc-400">
                        {p.marketplace} • @{p.author}
                      </span>
                    )}
                  </div>

                  {p?.excerpt && (
                    <p className="text-zinc-400 italic text-[11px] line-clamp-2 bg-zinc-950/40 p-1.5 rounded border border-zinc-900">
                      "{p.excerpt}"
                    </p>
                  )}

                  {ind && (
                    <div className="flex items-center gap-1.5 font-mono text-[11px] text-zinc-500 pt-0.5">
                      <span className="text-zinc-400">{ind.type}:</span>
                      <span className="truncate text-zinc-300">{ind.normalised_value}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Technical details toggle */}
      {evidence.details && Object.keys(evidence.details).length > 0 && (
        <div className="mt-3 pt-2 text-right">
          <button
            type="button"
            onClick={() => setExpandedDetails(!expandedDetails)}
            className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors inline-flex items-center gap-1"
          >
            <span>{expandedDetails ? 'Hide technical parameters' : 'View technical parameters'}</span>
            <svg
              className={`w-3 h-3 transition-transform ${expandedDetails ? 'rotate-180' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          {expandedDetails && (
            <pre className="text-left mt-2 p-2.5 rounded bg-zinc-950 border border-zinc-800 text-[11px] text-zinc-400 overflow-x-auto font-mono">
              {JSON.stringify(evidence.details, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

