import React from 'react';

export default function Badge({ variant = 'neutral', children, className = '' }) {
  const variantStyles = {
    neutral: 'bg-slate-800 text-slate-300 border-slate-700',
    draft: 'bg-slate-800/80 text-slate-300 border-slate-700',
    processing: 'bg-amber-950/60 text-amber-300 border-amber-800/50',
    completed: 'bg-emerald-950/60 text-emerald-300 border-emerald-800/50',
    failed: 'bg-rose-950/60 text-rose-300 border-rose-800/50',
    admin: 'bg-indigo-950/70 text-indigo-300 border-indigo-800/50',
    investigator: 'bg-sky-950/70 text-sky-300 border-sky-800/50',
    active: 'bg-emerald-950/60 text-emerald-300 border-emerald-800/50',
    inactive: 'bg-slate-800 text-slate-400 border-slate-700',
  };

  const selected = variantStyles[variant.toLowerCase()] || variantStyles.neutral;

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border uppercase tracking-wider select-none ${selected} ${className}`}
    >
      {children}
    </span>
  );
}

