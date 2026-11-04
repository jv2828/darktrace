/**
 * Unified indicator type palette and configuration for DARKTRACE.
 *
 * Meets WCAG 2.1 AA contrast requirements against dark interfaces (#0B0F17)
 * and light interfaces (#FFFFFF).
 *
 * Palette mapping:
 * - pgp_fingerprint: purple / violet
 * - wallet_btc, wallet_eth, wallet_xmr, wallet_other: amber / gold
 * - ip_address: cyan / sky
 * - port: slate / zinc
 * - domain: emerald / green
 * - ssl_cert_fingerprint: rose / pink
 * - cert_metadata: fuchsia / magenta
 * - server_banner: indigo / blue
 */

export const INDICATOR_CONFIG = {
  pgp_fingerprint: {
    label: 'PGP Fingerprint',
    shortLabel: 'PGP',
    category: 'cryptographic',
    colorName: 'purple',
    badgeClass: 'bg-purple-500/15 text-purple-300 border-purple-500/30',
    highlightClass: 'bg-purple-500/25 text-purple-200 border-b-2 border-purple-400 hover:bg-purple-500/40',
    chipClass: 'border-purple-500/40 text-purple-300 bg-purple-950/40 hover:bg-purple-900/50',
    dotColor: '#a855f7',
  },
  wallet_btc: {
    label: 'Bitcoin Wallet',
    shortLabel: 'BTC',
    category: 'cryptographic',
    colorName: 'amber',
    badgeClass: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    highlightClass: 'bg-amber-500/25 text-amber-200 border-b-2 border-amber-400 hover:bg-amber-500/40',
    chipClass: 'border-amber-500/40 text-amber-300 bg-amber-950/40 hover:bg-amber-900/50',
    dotColor: '#f59e0b',
  },
  wallet_eth: {
    label: 'Ethereum Wallet',
    shortLabel: 'ETH',
    category: 'cryptographic',
    colorName: 'amber',
    badgeClass: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    highlightClass: 'bg-amber-500/25 text-amber-200 border-b-2 border-amber-400 hover:bg-amber-500/40',
    chipClass: 'border-amber-500/40 text-amber-300 bg-amber-950/40 hover:bg-amber-900/50',
    dotColor: '#f59e0b',
  },
  wallet_xmr: {
    label: 'Monero Wallet',
    shortLabel: 'XMR',
    category: 'cryptographic',
    colorName: 'amber',
    badgeClass: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    highlightClass: 'bg-amber-500/25 text-amber-200 border-b-2 border-amber-400 hover:bg-amber-500/40',
    chipClass: 'border-amber-500/40 text-amber-300 bg-amber-950/40 hover:bg-amber-900/50',
    dotColor: '#f59e0b',
  },
  wallet_other: {
    label: 'Crypto Wallet',
    shortLabel: 'Wallet',
    category: 'cryptographic',
    colorName: 'amber',
    badgeClass: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    highlightClass: 'bg-amber-500/25 text-amber-200 border-b-2 border-amber-400 hover:bg-amber-500/40',
    chipClass: 'border-amber-500/40 text-amber-300 bg-amber-950/40 hover:bg-amber-900/50',
    dotColor: '#f59e0b',
  },
  ip_address: {
    label: 'IP Address',
    shortLabel: 'IP',
    category: 'network',
    colorName: 'cyan',
    badgeClass: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
    highlightClass: 'bg-cyan-500/25 text-cyan-200 border-b-2 border-cyan-400 hover:bg-cyan-500/40',
    chipClass: 'border-cyan-500/40 text-cyan-300 bg-cyan-950/40 hover:bg-cyan-900/50',
    dotColor: '#06b6d4',
  },
  port: {
    label: 'Port',
    shortLabel: 'Port',
    category: 'network',
    colorName: 'zinc',
    badgeClass: 'bg-zinc-500/15 text-zinc-300 border-zinc-500/30',
    highlightClass: 'bg-zinc-500/25 text-zinc-200 border-b-2 border-zinc-400 hover:bg-zinc-500/40',
    chipClass: 'border-zinc-500/40 text-zinc-300 bg-zinc-900/60 hover:bg-zinc-800/60',
    dotColor: '#71717a',
  },
  domain: {
    label: 'Domain / Onion',
    shortLabel: 'Domain',
    category: 'network',
    colorName: 'emerald',
    badgeClass: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    highlightClass: 'bg-emerald-500/25 text-emerald-200 border-b-2 border-emerald-400 hover:bg-emerald-500/40',
    chipClass: 'border-emerald-500/40 text-emerald-300 bg-emerald-950/40 hover:bg-emerald-900/50',
    dotColor: '#10b981',
  },
  ssl_cert_fingerprint: {
    label: 'SSL Cert Fingerprint',
    shortLabel: 'SSL Cert',
    category: 'infrastructure',
    colorName: 'rose',
    badgeClass: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
    highlightClass: 'bg-rose-500/25 text-rose-200 border-b-2 border-rose-400 hover:bg-rose-500/40',
    chipClass: 'border-rose-500/40 text-rose-300 bg-rose-950/40 hover:bg-rose-900/50',
    dotColor: '#f43f5e',
  },
  cert_metadata: {
    label: 'Cert Metadata',
    shortLabel: 'Cert Meta',
    category: 'infrastructure',
    colorName: 'fuchsia',
    badgeClass: 'bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/30',
    highlightClass: 'bg-fuchsia-500/25 text-fuchsia-200 border-b-2 border-fuchsia-400 hover:bg-fuchsia-500/40',
    chipClass: 'border-fuchsia-500/40 text-fuchsia-300 bg-fuchsia-950/40 hover:bg-fuchsia-900/50',
    dotColor: '#d946ef',
  },
  server_banner: {
    label: 'Server Banner',
    shortLabel: 'Banner',
    category: 'infrastructure',
    colorName: 'indigo',
    badgeClass: 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30',
    highlightClass: 'bg-indigo-500/25 text-indigo-200 border-b-2 border-indigo-400 hover:bg-indigo-500/40',
    chipClass: 'border-indigo-500/40 text-indigo-300 bg-indigo-950/40 hover:bg-indigo-900/50',
    dotColor: '#6366f1',
  },
};

const DEFAULT_CONFIG = {
  label: 'Unknown Indicator',
  shortLabel: 'Indicator',
  category: 'other',
  colorName: 'slate',
  badgeClass: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
  highlightClass: 'bg-slate-500/25 text-slate-200 border-b-2 border-slate-400',
  chipClass: 'border-slate-500/40 text-slate-300 bg-slate-900/60',
  dotColor: '#64748b',
};

/**
 * Get configuration object for an indicator type with safe fallback.
 * @param {string} type
 */
export function getIndicatorConfig(type) {
  if (!type) return DEFAULT_CONFIG;
  const key = String(type).toLowerCase();
  return INDICATOR_CONFIG[key] || DEFAULT_CONFIG;
}

/**
 * Format human-readable details string from indicator details dict.
 * @param {object} indicator
 */
export function formatIndicatorDetails(indicator) {
  if (!indicator) return '';
  const { indicator_type, details } = indicator;
  if (!details || typeof details !== 'object') return '';

  const parts = [];
  if (details.subtype) parts.push(details.subtype.toUpperCase());
  if (details.scope) parts.push(`Scope: ${details.scope}`);
  if (details.protocol) parts.push(`Proto: ${details.protocol.toUpperCase()}`);
  if (details.onion_version) parts.push(`v${details.onion_version} Onion`);
  if (details.algorithm) parts.push(details.algorithm.toUpperCase());
  if (details.field) parts.push(details.field);
  if (details.occurrences && details.occurrences > 1) {
    parts.push(`${details.occurrences}x in text`);
  }
  if (details.also_in_structured_field) {
    parts.push('Structured');
  }

  return parts.join(' • ');
}

export const ALL_INDICATOR_TYPES = Object.keys(INDICATOR_CONFIG);

