import React from 'react';

/**
 * DARKTRACE Official Cyber Shield & Threat Correlation Vector Logo.
 * Represents interconnected persona nodes inside a tactical cyber intelligence shield.
 */
export default function Logo({ size = 'md', className = '', glow = true }) {
  const sizeMap = {
    xs: 'w-5 h-5',
    sm: 'w-6 h-6',
    md: 'w-8 h-8',
    lg: 'w-10 h-10',
    xl: 'w-14 h-14',
    '2xl': 'w-18 h-18',
  };

  const dimension = sizeMap[size] || sizeMap.md;

  return (
    <svg
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`${dimension} shrink-0 ${className}`}
      aria-label="DARKTRACE Logo"
      role="img"
    >
      <defs>
        <linearGradient id="dt-grad-primary" x1="6" y1="6" x2="42" y2="42" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#38bdf8" />
          <stop offset="50%" stopColor="#0284c7" />
          <stop offset="100%" stopColor="#6366f1" />
        </linearGradient>

        <linearGradient id="dt-grad-accent" x1="12" y1="12" x2="36" y2="36" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#7dd3fc" />
          <stop offset="100%" stopColor="#38bdf8" />
        </linearGradient>

        <radialGradient id="dt-core-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.8" />
          <stop offset="100%" stopColor="#0284c7" stopOpacity="0" />
        </radialGradient>

        {glow && (
          <filter id="dt-glow-filter" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="1.5" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        )}
      </defs>

      {/* Hexagonal Threat Boundary Shield */}
      <polygon
        points="24,3.5 43,14 43,34 24,44.5 5,34 5,14"
        stroke="url(#dt-grad-primary)"
        strokeWidth="2"
        strokeLinejoin="round"
        fill="#0f172a"
        fillOpacity="0.85"
      />

      {/* Inner Tactical Facet */}
      <polygon
        points="24,8.5 38,16.5 38,31.5 24,39.5 10,31.5 10,16.5"
        stroke="#1e293b"
        strokeWidth="1.2"
        strokeLinejoin="round"
        fill="#020617"
        fillOpacity="0.75"
      />

      {/* Soft central ambient glow */}
      <circle cx="24" cy="24" r="10" fill="url(#dt-core-glow)" opacity="0.4" />

      {/* Multi-Node Correlation Web (Edges) */}
      <line x1="24" y1="12" x2="15" y2="24" stroke="url(#dt-grad-accent)" strokeWidth="1.5" strokeOpacity="0.85" />
      <line x1="24" y1="12" x2="33" y2="24" stroke="url(#dt-grad-accent)" strokeWidth="1.5" strokeOpacity="0.85" />
      <line x1="15" y1="24" x2="33" y2="24" stroke="url(#dt-grad-accent)" strokeWidth="1.5" strokeOpacity="0.85" />
      <line x1="15" y1="24" x2="24" y2="36" stroke="url(#dt-grad-accent)" strokeWidth="1.5" strokeOpacity="0.85" />
      <line x1="33" y1="24" x2="24" y2="36" stroke="url(#dt-grad-accent)" strokeWidth="1.5" strokeOpacity="0.85" />
      <line x1="24" y1="12" x2="24" y2="36" stroke="#38bdf8" strokeWidth="1" strokeDasharray="2 2" strokeOpacity="0.5" />

      {/* Central Threat Correlation Core */}
      <circle cx="24" cy="24" r="4.5" fill="#0f172a" stroke="url(#dt-grad-primary)" strokeWidth="1.5" />
      <circle cx="24" cy="24" r="2" fill="#38bdf8" filter={glow ? 'url(#dt-glow-filter)' : undefined} />

      {/* Observed Persona Nodes */}
      <circle cx="24" cy="12" r="2.4" fill="#38bdf8" />
      <circle cx="15" cy="24" r="2.4" fill="#0284c7" />
      <circle cx="33" cy="24" r="2.4" fill="#0284c7" />
      <circle cx="24" cy="36" r="2.4" fill="#6366f1" />

      {/* Tactical Sensor Crosshairs */}
      <line x1="24" y1="3" x2="24" y2="6.5" stroke="#38bdf8" strokeWidth="2" strokeLinecap="round" />
      <line x1="24" y1="41.5" x2="24" y2="45" stroke="#6366f1" strokeWidth="2" strokeLinecap="round" />
      <line x1="5" y1="14" x2="8" y2="15.5" stroke="#38bdf8" strokeWidth="1.8" strokeLinecap="round" />
      <line x1="43" y1="14" x2="40" y2="15.5" stroke="#38bdf8" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
