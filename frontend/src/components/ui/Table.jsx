import React from 'react';

export default function Table({
  headers = [],
  children,
  className = '',
}) {
  return (
    <div className={`w-full overflow-x-auto border border-slate-800 rounded-lg ${className}`}>
      <table className="w-full text-left text-xs border-collapse">
        <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 font-medium uppercase tracking-wider">
          <tr>
            {headers.map((h, idx) => (
              <th
                key={idx}
                scope="col"
                className={`py-3 px-4 ${typeof h === 'object' && h.className ? h.className : ''}`}
              >
                {typeof h === 'object' ? h.label : h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/60 bg-slate-900/40 text-slate-200">
          {children}
        </tbody>
      </table>
    </div>
  );
}

