import React from 'react';
import Button from './Button';

export default function ErrorState({
  title = 'An error occurred',
  message = 'Failed to load requested resources.',
  details = null,
  onRetry,
  className = '',
}) {
  return (
    <div
      className={`p-6 rounded border border-rose-900/50 bg-rose-950/20 text-rose-200 ${className}`}
    >
      <h3 className="text-sm font-semibold text-rose-300">{title}</h3>
      <p className="text-xs text-rose-200 mt-1">{message}</p>
      {details && (
        <pre className="mt-2 p-2 bg-slate-950 rounded text-[11px] font-mono text-rose-400 overflow-x-auto whitespace-pre-wrap break-all">
          {typeof details === 'object' ? JSON.stringify(details, null, 2) : String(details)}
        </pre>
      )}
      {onRetry && (
        <div className="mt-4">
          <Button variant="secondary" size="sm" onClick={onRetry}>
            Retry
          </Button>
        </div>
      )}
    </div>
  );
}

