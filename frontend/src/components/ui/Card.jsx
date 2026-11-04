import React from 'react';

export default function Card({ children, className = '', ...props }) {
  return (
    <div
      className={`bg-slate-900 border border-slate-800 rounded-lg p-6 shadow-xs ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

