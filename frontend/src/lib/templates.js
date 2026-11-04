/**
 * Client-side template generator for DARKTRACE ingestion file formats.
 *
 * Provides ready-to-use CSV and JSON template data conforming to
 * the platform's required and optional column specifications using
 * strictly fictional sample indicators.
 */

export const INGESTION_COLUMNS = [
  'marketplace',
  'username',
  'content',
  'timestamp',
  'source_reference',
  'pgp_fingerprint',
  'wallet',
  'domain',
  'ip_address',
  'ssl_cert_fingerprint',
  'server_banner',
  'port',
];

export const FICTIONAL_SAMPLE_ROW = {
  marketplace: 'Velvet Bazaar',
  username: 'artisan_smith',
  content: 'Batch #402 of precision clockwork escapement gears restocked. Escrow verification required.',
  timestamp: '2026-02-14T15:30:00Z',
  source_reference: 'thread_9842',
  pgp_fingerprint: 'A1B2C3D4E5F60718293A4B5C6D7E8F9012345678',
  wallet: 'bc1q9d4k2t8x7m1w5p3z0s6y8v2c4b6n8m0k2j4h6f',
  domain: 'relay.clockwork-mesh.example',
  ip_address: '198.51.100.42',
  ssl_cert_fingerprint: 'E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855',
  server_banner: 'nginx/1.18.0 (Ubuntu)',
  port: 443,
};

/**
 * Trigger browser file download of CSV template.
 */
export function downloadCsvTemplate() {
  const header = INGESTION_COLUMNS.join(',');
  const rowValues = INGESTION_COLUMNS.map((col) => {
    const val = FICTIONAL_SAMPLE_ROW[col] !== undefined ? String(FICTIONAL_SAMPLE_ROW[col]) : '';
    // Quote cell if it contains comma or quotes
    if (val.includes(',') || val.includes('"') || val.includes('\n')) {
      return `"${val.replace(/"/g, '""')}"`;
    }
    return val;
  });

  const csvContent = `${header}\n${rowValues.join(',')}\n`;
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  triggerDownload(blob, 'darktrace_ingest_template.csv');
}

/**
 * Trigger browser file download of JSON template.
 */
export function downloadJsonTemplate() {
  const jsonContent = JSON.stringify([FICTIONAL_SAMPLE_ROW], null, 2) + '\n';
  const blob = new Blob([jsonContent], { type: 'application/json;charset=utf-8;' });
  triggerDownload(blob, 'darktrace_ingest_template.json');
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', filename);
  link.style.visibility = 'hidden';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

