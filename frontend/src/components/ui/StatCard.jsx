import React from 'react';
import Card from './Card';

export default function StatCard({
  title,
  value,
  subtitle,
  className = '',
  loading = false,
}) {
  return (
    <Card className={`p-5 flex flex-col justify-between ${className}`}>
      <span className="text-xs font-medium uppercase tracking-wider text-slate-400">
        {title}
      </span>
      <div className="mt-3 flex items-baseline gap-2">
        {loading ? (
          <span className="text-2xl font-bold font-mono text-slate-500 animate-pulse">
            ...
          </span>
        ) : (
          <span className="text-2xl sm:text-3xl font-bold font-mono text-slate-100">
            {typeof value === 'number' ? value.toLocaleString() : value}
          </span>
        )}
      </div>
      {subtitle && <p className="text-xs text-slate-400 mt-2">{subtitle}</p>}
    </Card>
  );
}

