import React from 'react';

export default function PageHeader({
  title,
  description,
  action,
  children,
  className = '',
}) {
  return (
    <div
      className={`flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800 ${className}`}
    >
      <div>
        <h1 className="text-xl font-bold tracking-tight text-slate-100">{title}</h1>
        {description && <p className="text-sm text-slate-400 mt-1">{description}</p>}
      </div>
      {(action || children) && (
        <div className="flex items-center gap-3 shrink-0">
          {action}
          {children}
        </div>
      )}
    </div>
  );
}

