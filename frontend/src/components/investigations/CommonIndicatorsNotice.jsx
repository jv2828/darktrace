import React from 'react';

/**
 * Notice banner listing suppressed high-prevalence decoy/common indicators.
 */
export default function CommonIndicatorsNotice({ suppressedList = [] }) {
  if (!suppressedList || suppressedList.length === 0) {
    return null;
  }

  return (
    <div className="mb-6 p-4 rounded-lg bg-zinc-900/80 border border-zinc-800 text-zinc-300">
      <div className="flex items-start gap-3">
        <div className="p-1.5 rounded bg-zinc-800 text-zinc-400 mt-0.5">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <div className="flex-1">
          <h4 className="text-sm font-medium text-zinc-200">
            Suppressed Common Indicators ({suppressedList.length})
          </h4>
          <p className="text-xs text-zinc-400 mt-0.5 mb-3">
            The following technical artifacts appear across 5 or more distinct personas. They have been suppressed to prevent false-positive linkages caused by shared market infrastructure (such as multi-signature escrow wallets or shared PGP support keys).
          </p>

          <div className="divide-y divide-zinc-800/80 border border-zinc-800 rounded bg-zinc-950/60 overflow-hidden max-h-48 overflow-y-auto">
            {suppressedList.map((item, idx) => (
              <div key={idx} className="p-2.5 flex items-center justify-between text-xs gap-3">
                <div className="flex items-center gap-2 truncate">
                  <span className="px-1.5 py-0.5 rounded text-[11px] font-mono bg-zinc-800 text-zinc-300 border border-zinc-700">
                    {item.type}
                  </span>
                  <span className="font-mono text-zinc-400 truncate" title={item.normalised_value}>
                    {item.normalised_value}
                  </span>
                </div>
                <div className="text-zinc-500 whitespace-nowrap text-[11px] flex items-center gap-2">
                  <span>{item.actor_count} personas</span>
                  <span>•</span>
                  <span>{item.marketplace_count} marketplaces</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

