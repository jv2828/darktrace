import React from 'react';

export default function Spinner({ size = 'md', className = '' }) {
  const sizeMap = {
    sm: 'w-3.5 h-3.5 border-2',
    md: 'w-5 h-5 border-2',
    lg: 'w-8 h-8 border-3',
  };

  return (
    <span
      role="status"
      aria-label="Loading"
      className={`inline-block rounded-full border-slate-600 border-t-blue-400 animate-spin ${
        sizeMap[size] || sizeMap.md
      } ${className}`}
    />
  );
}

