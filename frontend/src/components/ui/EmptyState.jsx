import React from 'react';

export default function EmptyState({
  title = 'No items found',
  message,
  action,
  className = '',
}) {
  return (
    <div
      className={`text-center py-12 px-4 rounded border border-dashed border-slate-800 bg-slate-950/40 ${className}`}
    >
      <h3 className="text-sm font-medium text-slate-200">{title}</h3>
      {message && <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">{message}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

