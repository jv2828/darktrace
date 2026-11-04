import React from 'react';

/**
 * Visual strength indicator with numerical score and heuristic disclaimer tooltip.
 */
export default function StrengthBar({
  strength = 0,
  className = '',
  title = 'Evidence strength: how specific this shared indicator is. Not a probability of identity.',
}) {
  const numStrength = parseFloat(strength) || 0;
  const pct = Math.min(100, Math.max(0, Math.round(numStrength * 100)));

  let barColor = 'bg-zinc-400';
  let badgeColor = 'text-zinc-400 bg-zinc-800/60 border-zinc-700';

  if (numStrength >= 0.8) {
    barColor = 'bg-emerald-500';
    badgeColor = 'text-emerald-400 bg-emerald-950/40 border-emerald-800/60';
  } else if (numStrength >= 0.4) {
    barColor = 'bg-amber-500';
    badgeColor = 'text-amber-400 bg-amber-950/40 border-amber-800/60';
  }

  return (
    <div className={`flex items-center gap-2.5 ${className}`} title={title}>
      <span className={`px-1.5 py-0.5 rounded text-xs font-mono font-medium border ${badgeColor}`}>
        {numStrength.toFixed(4)}
      </span>
      <div className="w-24 h-1.5 bg-zinc-800 rounded-full overflow-hidden border border-zinc-700/60">
        <div
          className={`h-full rounded-full transition-all duration-300 ${barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

