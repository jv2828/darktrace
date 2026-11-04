import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import Input from '../components/ui/Input';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import ErrorState from '../components/ui/ErrorState';
import { useToast } from '../components/ui/Toast';
import {
  fetchInvestigationById,
  fetchSampleDatasets,
  loadSampleDatasetApi,
  previewManualPostApi,
  commitManualPostApi,
  previewFileUploadApi,
  commitFileUploadApi,
  previewExtractionApi,
} from '../lib/api';
import HighlightedText from '../components/common/HighlightedText';
import {
  getIndicatorConfig,
  formatIndicatorDetails,
  ALL_INDICATOR_TYPES,
} from '../lib/indicatorTypes';
import { downloadCsvTemplate, downloadJsonTemplate } from '../lib/templates';

export default function CollectPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();

  const [investigation, setInvestigation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Active tab: 'samples' | 'manual' | 'file'
  const [activeTab, setActiveTab] = useState('samples');

  // Load investigation details
  const loadInvestigation = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchInvestigationById(id);
      setInvestigation(data);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadInvestigation();
  }, [loadInvestigation]);

  if (loading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center gap-3">
        <Spinner size="lg" />
        <p className="text-xs text-slate-400 font-mono">Loading case #{id} for collection...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-12 space-y-4">
        <Link to={`/investigations/${id}`} className="text-xs text-sky-400 hover:text-sky-300 font-medium">
          &larr; Back to Investigation
        </Link>
        <ErrorState
          title="Investigation Access Error"
          message={error.message || 'Unable to access case workspace.'}
          onRetry={loadInvestigation}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb Navigation */}
      <div className="flex items-center justify-between">
        <Link
          to={`/investigations/${id}`}
          className="text-xs text-sky-400 hover:text-sky-300 font-medium inline-flex items-center gap-1"
        >
          &larr; Back to Investigation #{id}
        </Link>
      </div>

      <PageHeader
        title={`Data Collection: ${investigation.title}`}
        description="Ingest synthetic benchmark intelligence collections, single manual posts, or custom CSV/JSON batch files."
      />

      {/* Collection Navigation Tabs */}
      <div className="flex border-b border-slate-800 space-x-1">
        <button
          type="button"
          onClick={() => setActiveTab('samples')}
          className={`px-4 py-2.5 text-xs font-medium border-b-2 transition-colors cursor-pointer ${
            activeTab === 'samples'
              ? 'border-sky-400 text-sky-400 bg-slate-900/40'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          1. Sample Benchmark Datasets
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('manual')}
          className={`px-4 py-2.5 text-xs font-medium border-b-2 transition-colors cursor-pointer ${
            activeTab === 'manual'
              ? 'border-sky-400 text-sky-400 bg-slate-900/40'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          2. Manual Record Entry
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('file')}
          className={`px-4 py-2.5 text-xs font-medium border-b-2 transition-colors cursor-pointer ${
            activeTab === 'file'
              ? 'border-sky-400 text-sky-400 bg-slate-900/40'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          3. Batch File Upload (.csv / .json)
        </button>
      </div>

      {/* Tab Panels */}
      {activeTab === 'samples' && <SamplesPanel investigationId={id} />}
      {activeTab === 'manual' && <ManualEntryPanel investigationId={id} onBack={() => navigate(`/investigations/${id}`)} />}
      {activeTab === 'file' && <FileUploadPanel investigationId={id} onBack={() => navigate(`/investigations/${id}`)} />}
    </div>
  );
}

// =====================================================================
// Tab 1: Sample Datasets Panel
// =====================================================================

function SamplesPanel({ investigationId }) {
  const [samples, setSamples] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [loadingKey, setLoadingKey] = useState(null);
  const [successInfo, setSuccessInfo] = useState(null);
  const toast = useToast();

  const loadSamples = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSampleDatasets();
      setSamples(data || []);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSamples();
  }, [loadSamples]);

  async function handleLoadSample(key) {
    setLoadingKey(key);
    setSuccessInfo(null);
    try {
      const result = await loadSampleDatasetApi(investigationId, key);
      toast.success(`Successfully loaded ${result.dataset_name}!`);
      setSuccessInfo(result);
      loadSamples();
    } catch (err) {
      toast.error(err.message || `Failed to load sample dataset '${key}'.`);
    } finally {
      setLoadingKey(null);
    }
  }

  if (loading) {
    return (
      <div className="py-16 flex flex-col items-center justify-center gap-2">
        <Spinner size="md" />
        <p className="text-xs text-slate-400 font-mono">Loading available synthetic benchmarks...</p>
      </div>
    );
  }

  if (error) {
    return (
      <ErrorState
        title="Failed to Load Sample Catalog"
        message={error.message || 'Unable to scan sample datasets.'}
        onRetry={loadSamples}
      />
    );
  }

  return (
    <div className="space-y-6">
      {successInfo && (
        <div className="p-4 rounded bg-emerald-950/60 border border-emerald-800 text-xs text-emerald-200 flex items-center justify-between">
          <div>
            <span className="font-semibold">{successInfo.dataset_name}</span> attached to investigation:{' '}
            <span className="font-mono">{successInfo.imported}</span> posts imported ({successInfo.new_actors} actors, {successInfo.new_marketplaces} marketplaces).
          </div>
          <Link to={`/investigations/${investigationId}`}>
            <Button variant="secondary" size="sm">
              View Posts Table &rarr;
            </Button>
          </Link>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {samples.map((sample) => (
          <Card key={sample.key} className="p-5 flex flex-col justify-between border-slate-800">
            <div>
              <div className="flex items-center justify-between gap-2 mb-2">
                <h3 className="text-base font-semibold text-slate-100">{sample.name}</h3>
                {sample.loaded ? (
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium uppercase bg-emerald-950 text-emerald-300 border border-emerald-800">
                    Loaded in System
                  </span>
                ) : (
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium uppercase bg-slate-800 text-slate-400 border border-slate-700">
                    Available
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">{sample.description}</p>

              <div className="grid grid-cols-3 gap-2 mt-4 p-2.5 rounded bg-slate-950/60 border border-slate-800/80 font-mono text-[11px] text-center">
                <div>
                  <div className="text-slate-400 text-[10px] uppercase">Posts</div>
                  <div className="font-bold text-slate-200 mt-0.5">{sample.post_count}</div>
                </div>
                <div>
                  <div className="text-slate-400 text-[10px] uppercase">Marketplaces</div>
                  <div className="font-bold text-slate-200 mt-0.5">{sample.marketplace_count}</div>
                </div>
                <div>
                  <div className="text-slate-400 text-[10px] uppercase">Personas</div>
                  <div className="font-bold text-slate-200 mt-0.5">{sample.persona_count}</div>
                </div>
              </div>
            </div>

            <div className="mt-5 pt-3 border-t border-slate-800/80 flex items-center justify-between">
              <span className="text-[11px] font-mono text-slate-400">Version: v{sample.version}</span>
              <Button
                variant="primary"
                size="sm"
                loading={loadingKey === sample.key}
                disabled={loadingKey !== null}
                onClick={() => handleLoadSample(sample.key)}
              >
                {sample.loaded ? 'Attach to Case' : 'Load into Case'}
              </Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

// =====================================================================
// Tab 2: Manual Record Entry Panel
// =====================================================================

function ManualEntryPanel({ investigationId, onBack }) {
  const [marketplace, setMarketplace] = useState('');
  const [username, setUsername] = useState('');
  const [timestamp, setTimestamp] = useState('');
  const [content, setContent] = useState('');
  const [sourceRef, setSourceRef] = useState('');

  // Structured indicators
  const [showStructured, setShowStructured] = useState(false);
  const [pgp, setPgp] = useState('');
  const [wallet, setWallet] = useState('');
  const [domain, setDomain] = useState('');
  const [ip, setIp] = useState('');
  const [cert, setCert] = useState('');
  const [banner, setBanner] = useState('');
  const [port, setPort] = useState('');

  // Preview & submission state
  const [previewResult, setPreviewResult] = useState(null);
  const [extractionPreview, setExtractionPreview] = useState(null);
  const [extracting, setExtracting] = useState(false);
  const [validating, setValidating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [committed, setCommitted] = useState(false);
  const toast = useToast();

  const runExtractionPreview = useCallback(async () => {
    if (!content.trim()) {
      setExtractionPreview(null);
      return;
    }
    setExtracting(true);
    try {
      const payload = buildPayload();
      const res = await previewExtractionApi(content, payload.structured_indicators);
      setExtractionPreview(res);
    } catch (err) {
      console.error('Failed to preview extraction:', err);
    } finally {
      setExtracting(false);
    }
  }, [content, pgp, wallet, domain, ip, cert, banner, port]);

  // Debounced 300ms live extraction preview
  useEffect(() => {
    const timer = setTimeout(() => {
      runExtractionPreview();
    }, 300);
    return () => clearTimeout(timer);
  }, [runExtractionPreview]);

  function buildPayload() {
    const indicators = {};
    if (pgp.trim()) indicators.pgp_fingerprint = pgp.trim();
    if (wallet.trim()) indicators.wallet = wallet.trim();
    if (domain.trim()) indicators.domain = domain.trim();
    if (ip.trim()) indicators.ip_address = ip.trim();
    if (cert.trim()) indicators.ssl_cert_fingerprint = cert.trim();
    if (banner.trim()) indicators.server_banner = banner.trim();
    if (port.trim()) indicators.port = port.trim();

    return {
      marketplace: marketplace.trim(),
      username: username.trim(),
      timestamp: timestamp.trim() || undefined,
      content,
      source_reference: sourceRef.trim() || undefined,
      structured_indicators: Object.keys(indicators).length > 0 ? indicators : undefined,
    };
  }

  async function handleValidate(e) {
    if (e) e.preventDefault();
    setValidating(true);
    setPreviewResult(null);
    try {
      const res = await previewManualPostApi(investigationId, buildPayload());
      setPreviewResult(res);
      const row = res.rows?.[0];
      if (row?.status === 'valid') {
        toast.success('Record validation passed with 0 errors.');
      } else if (row?.status === 'valid_with_warnings') {
        toast.info('Record is valid with warnings.');
      } else if (row?.status === 'duplicate') {
        toast.error('Record is a duplicate of an existing post.');
      } else {
        toast.error('Validation failed. Please correct form errors.');
      }
    } catch (err) {
      toast.error(err.message || 'Validation request failed.');
    } finally {
      setValidating(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await commitManualPostApi(investigationId, buildPayload());
      toast.success('Manual record successfully imported!');
      setCommitted(true);
    } catch (err) {
      toast.error(err.message || 'Failed to import manual record.');
    } finally {
      setSubmitting(false);
    }
  }

  function handleReset() {
    setMarketplace('');
    setUsername('');
    setTimestamp('');
    setContent('');
    setSourceRef('');
    setPgp('');
    setWallet('');
    setDomain('');
    setIp('');
    setCert('');
    setBanner('');
    setPort('');
    setPreviewResult(null);
    setCommitted(false);
  }

  if (committed) {
    return (
      <Card className="p-8 text-center space-y-4 max-w-lg mx-auto">
        <div className="w-12 h-12 rounded-full bg-emerald-950/80 border border-emerald-800 text-emerald-400 mx-auto flex items-center justify-center text-xl font-bold">
          ✓
        </div>
        <h3 className="text-base font-semibold text-slate-100">Manual Record Ingested</h3>
        <p className="text-xs text-slate-400 leading-relaxed">
          The darknet post was validated, deduplicated, and committed to a new manual intelligence dataset attached to this case.
        </p>
        <div className="flex items-center justify-center gap-3 pt-3">
          <Button variant="secondary" size="sm" onClick={handleReset}>
            + Add Another Post
          </Button>
          <Button variant="primary" size="sm" onClick={onBack}>
            Back to Investigation
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-6 max-w-2xl border-slate-800">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label="Marketplace / Platform"
            placeholder="e.g. Velvet Bazaar"
            value={marketplace}
            onChange={(e) => setMarketplace(e.target.value)}
            required
            helperText="2 to 100 characters."
          />
          <Input
            label="Author Username / Handle"
            placeholder="e.g. iron_artisan"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            helperText="2 to 64 characters."
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label="Timestamp (UTC)"
            type="datetime-local"
            value={timestamp}
            onChange={(e) => setTimestamp(e.target.value)}
            helperText="Optional. If omitted or without tz, UTC is assumed."
          />
          <Input
            label="Source Reference"
            placeholder="e.g. thread_4091 or URL"
            value={sourceRef}
            onChange={(e) => setSourceRef(e.target.value)}
            helperText="Optional identifier."
          />
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label className="block text-xs font-medium text-slate-300">
              Post Content <span className="text-rose-400">*</span>
            </label>
            <span className="text-[11px] font-mono text-slate-400">
              {content.length.toLocaleString()} / 20,000 chars
            </span>
          </div>
          <textarea
            rows={5}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Paste raw dark web listing, message, or forum communication text..."
            required
            className="w-full px-3 py-2 text-xs bg-slate-950 border border-slate-800 rounded text-slate-100 placeholder:text-slate-500 focus:outline-hidden focus:border-sky-400 font-mono leading-relaxed"
          />

          {/* Live Extraction Preview Panel */}
          {content.trim() && (
            <div className="mt-3 p-3 rounded-lg bg-slate-950/80 border border-slate-800 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                    Indicator Extraction Preview
                  </span>
                  {extracting && <Spinner size="sm" />}
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={runExtractionPreview}
                  loading={extracting}
                  className="text-[11px] h-6 py-0 px-2"
                >
                  Refresh Preview
                </Button>
              </div>

              {/* Text Stats Strip */}
              {extractionPreview?.text_stats && (
                <div className="flex items-center gap-4 text-[11px] font-mono text-slate-400 bg-slate-900/60 px-2.5 py-1 rounded border border-slate-800/80">
                  <span>Chars: <strong className="text-slate-200">{extractionPreview.text_stats.char_count}</strong></span>
                  <span>Words: <strong className="text-slate-200">{extractionPreview.text_stats.word_count}</strong></span>
                  <span>Sentences: <strong className="text-slate-200">{extractionPreview.text_stats.sentence_count}</strong></span>
                  <span className="ml-auto text-[10px] text-slate-400 font-sans">v{extractionPreview.extractor_version || '1.0.0'}</span>
                </div>
              )}

              {/* Highlighted text preview */}
              <div>
                <span className="block text-[11px] font-medium text-slate-400 mb-1">
                  Annotated Text Spans:
                </span>
                <HighlightedText
                  text={content}
                  indicators={extractionPreview?.indicators || []}
                  className="max-h-48 overflow-y-auto"
                />
              </div>

              {/* Extracted Indicators Table / Chips */}
              {extractionPreview?.indicators?.length > 0 ? (
                <div>
                  <span className="block text-[11px] font-medium text-slate-400 mb-1.5">
                    Detected Indicators ({extractionPreview.indicators.length}):
                  </span>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs font-mono">
                      <thead className="bg-slate-900 text-slate-400 text-[10px] uppercase border-b border-slate-800">
                        <tr>
                          <th className="px-2 py-1.5">Type</th>
                          <th className="px-2 py-1.5">Normalized Value</th>
                          <th className="px-2 py-1.5">Confidence</th>
                          <th className="px-2 py-1.5">Method</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {extractionPreview.indicators.map((ind, idx) => {
                          const cfg = getIndicatorConfig(ind.indicator_type);
                          return (
                            <tr key={idx} className="hover:bg-slate-900/40">
                              <td className="px-2 py-1 whitespace-nowrap">
                                <span className={`inline-flex items-center gap-1 px-1.5 py-0.2 rounded text-[10px] font-semibold border ${cfg.badgeClass}`}>
                                  <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: cfg.dotColor }} />
                                  {cfg.shortLabel}
                                </span>
                              </td>
                              <td className="px-2 py-1 text-slate-200 max-w-xs truncate" title={ind.normalised_value}>
                                {ind.normalised_value}
                              </td>
                              <td className="px-2 py-1 uppercase text-[10px] text-emerald-400 font-bold">
                                {ind.confidence || 'high'}
                              </td>
                              <td className="px-2 py-1 text-slate-400 text-[10px]">
                                {ind.extraction_method}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <div className="p-2.5 rounded bg-slate-900/40 border border-slate-800/80 text-xs text-slate-400 font-mono text-center">
                  No technical threat indicators detected in text.
                </div>
              )}
            </div>
          )}
        </div>

        {/* Collapsible Structured Indicators Section */}
        <div className="pt-2">
          <button
            type="button"
            onClick={() => setShowStructured(!showStructured)}
            className="text-xs font-medium text-sky-400 hover:text-sky-300 flex items-center gap-1 cursor-pointer"
          >
            {showStructured ? '▾ Hide' : '▸ Show'} Optional Structured Indicators
          </button>

          {showStructured && (
            <div className="mt-3 p-4 rounded bg-slate-950/60 border border-slate-800 space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Input
                  label="PGP Fingerprint"
                  placeholder="40 or 64 hex chars"
                  value={pgp}
                  onChange={(e) => setPgp(e.target.value)}
                />
                <Input
                  label="Cryptocurrency Wallet"
                  placeholder="e.g. bc1q... or 0x..."
                  value={wallet}
                  onChange={(e) => setWallet(e.target.value)}
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Input
                  label="Domain Name / Onion"
                  placeholder="e.g. relay.example or .onion"
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                />
                <Input
                  label="IP Address"
                  placeholder="e.g. 198.51.100.42"
                  value={ip}
                  onChange={(e) => setIp(e.target.value)}
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <Input
                  label="TLS / SSL Cert SHA-256"
                  placeholder="64 hex chars"
                  value={cert}
                  onChange={(e) => setCert(e.target.value)}
                />
                <Input
                  label="Server Banner"
                  placeholder="e.g. nginx/1.18.0"
                  value={banner}
                  onChange={(e) => setBanner(e.target.value)}
                />
                <Input
                  label="Network Port"
                  placeholder="e.g. 443"
                  value={port}
                  onChange={(e) => setPort(e.target.value)}
                />
              </div>
            </div>
          )}
        </div>

        {/* Live Validation Result Box */}
        {previewResult && (
          <div className="mt-3 p-3 rounded border text-xs font-mono space-y-1.5 bg-slate-950">
            {previewResult.rows?.[0] && (
              <>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-slate-300">Status:</span>
                  <StatusBadge status={previewResult.rows[0].status} />
                </div>
                {previewResult.rows[0].errors?.length > 0 && (
                  <div className="text-rose-400">
                    Errors: {previewResult.rows[0].errors.join('; ')}
                  </div>
                )}
                {previewResult.rows[0].warnings?.length > 0 && (
                  <div className="text-amber-400">
                    Warnings: {previewResult.rows[0].warnings.join('; ')}
                  </div>
                )}
              </>
            )}
          </div>
        )}

        <div className="pt-3 border-t border-slate-800 flex items-center justify-between">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            loading={validating}
            onClick={handleValidate}
          >
            Validate
          </Button>

          <Button
            type="submit"
            variant="primary"
            size="sm"
            loading={submitting}
            disabled={!marketplace || !username || !content}
          >
            Import Post
          </Button>
        </div>
      </form>
    </Card>
  );
}

// =====================================================================
// Tab 3: File Upload Panel (CSV / JSON)
// =====================================================================

function FileUploadPanel({ investigationId, onBack }) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [onErrorStrategy, setOnErrorStrategy] = useState('skip_invalid');
  const [validating, setValidating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [previewData, setPreviewData] = useState(null);
  const [committedResult, setCommittedResult] = useState(null);
  const [expandedRows, setExpandedRows] = useState(new Set());
  const toast = useToast();

  function toggleRowExpanded(rowNum) {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(rowNum)) {
        next.delete(rowNum);
      } else {
        next.add(rowNum);
      }
      return next;
    });
  }

  function handleFileSelect(e) {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setPreviewData(null);
      setCommittedResult(null);
    }
  }

  async function handleValidateFile() {
    if (!selectedFile) return;
    setValidating(true);
    setPreviewData(null);
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      const res = await previewFileUploadApi(investigationId, formData);
      setPreviewData(res);
      toast.success(`Validated ${res.summary?.total || 0} rows.`);
    } catch (err) {
      toast.error(err.message || 'File validation failed.');
    } finally {
      setValidating(false);
    }
  }

  async function handleCommitFile() {
    if (!selectedFile) return;
    setSubmitting(true);
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('on_error', onErrorStrategy);
      const res = await commitFileUploadApi(investigationId, formData);
      toast.success(`Successfully imported ${res.imported} posts!`);
      setCommittedResult(res);
    } catch (err) {
      toast.error(err.message || 'File commit failed.');
    } finally {
      setSubmitting(false);
    }
  }

  if (committedResult) {
    return (
      <Card className="p-8 text-center space-y-4 max-w-lg mx-auto">
        <div className="w-12 h-12 rounded-full bg-emerald-950/80 border border-emerald-800 text-emerald-400 mx-auto flex items-center justify-center text-xl font-bold">
          ✓
        </div>
        <h3 className="text-base font-semibold text-slate-100">Dataset Ingested Successfully</h3>
        <p className="text-xs text-slate-400 leading-relaxed font-mono">
          Imported {committedResult.imported} posts into dataset "{committedResult.dataset_name}".
          <br />
          Skipped {committedResult.skipped_duplicates} duplicates, {committedResult.skipped_invalid} invalid rows.
        </p>
        <div className="flex items-center justify-center gap-3 pt-3">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              setSelectedFile(null);
              setPreviewData(null);
              setCommittedResult(null);
            }}
          >
            Upload Another File
          </Button>
          <Button variant="primary" size="sm" onClick={onBack}>
            Back to Investigation
          </Button>
        </div>
      </Card>
    );
  }

  const importableCount =
    (previewData?.summary?.valid || 0) + (previewData?.summary?.valid_with_warnings || 0);

  return (
    <div className="space-y-6">
      {/* Templates & File Selection Header */}
      <Card className="p-5 border-slate-800">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-sm font-semibold text-slate-200">Upload Data File</h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Select or drop a CSV or JSON file (up to 5 MB, max 5,000 rows).
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={downloadCsvTemplate}>
              Download CSV template
            </Button>
            <Button variant="secondary" size="sm" onClick={downloadJsonTemplate}>
              Download JSON template
            </Button>
          </div>
        </div>

        {/* Drag & Drop File Picker */}
        <div className="mt-4 p-6 border-2 border-dashed border-slate-800 rounded bg-slate-950/40 text-center space-y-3">
          <input
            type="file"
            id="file-upload-input"
            accept=".csv,.json"
            onChange={handleFileSelect}
            className="hidden"
          />
          <label
            htmlFor="file-upload-input"
            className="inline-flex items-center gap-2 px-4 py-2 rounded bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 cursor-pointer transition-colors"
          >
            Choose File
          </label>
          <p className="text-xs text-slate-400">
            {selectedFile ? (
              <span className="font-mono text-slate-200">
                Selected: {selectedFile.name} ({(selectedFile.size / 1024).toFixed(1)} KB)
              </span>
            ) : (
              'Drag and drop .csv or .json file here, or click to browse.'
            )}
          </p>
        </div>

        {/* Validation Trigger Button */}
        {selectedFile && !previewData && (
          <div className="mt-4 flex justify-end">
            <Button
              variant="primary"
              size="sm"
              loading={validating}
              onClick={handleValidateFile}
            >
              Validate File
            </Button>
          </div>
        )}
      </Card>

      {/* Validation Summary and Preview Table */}
      {previewData && (
        <div className="space-y-4">
          <Card className="p-4 border-slate-800">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                  Validation Summary
                </h4>
                <div className="flex flex-wrap gap-2 text-xs font-mono">
                  <span className="px-2.5 py-1 rounded bg-slate-800 text-slate-300 border border-slate-700">
                    Total: {previewData.summary?.total}
                  </span>
                  <span className="px-2.5 py-1 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
                    Valid: {previewData.summary?.valid}
                  </span>
                  <span className="px-2.5 py-1 rounded bg-amber-950 text-amber-300 border border-amber-800">
                    Warnings: {previewData.summary?.valid_with_warnings}
                  </span>
                  <span className="px-2.5 py-1 rounded bg-indigo-950 text-indigo-300 border border-indigo-800">
                    Duplicates: {previewData.summary?.duplicates}
                  </span>
                  <span className="px-2.5 py-1 rounded bg-rose-950 text-rose-300 border border-rose-800">
                    Invalid: {previewData.summary?.invalid}
                  </span>
                </div>

                {/* Total indicators breakdown */}
                {previewData.summary?.indicators_found !== undefined && (
                  <div className="mt-3 pt-3 border-t border-slate-800/80">
                    <span className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                      Extracted Technical Indicators ({previewData.summary.indicators_found} Found across preview):
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {Object.entries(previewData.summary.indicators_by_type || {}).map(([typeKey, count]) => {
                        const cfg = getIndicatorConfig(typeKey);
                        return (
                          <span
                            key={typeKey}
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-medium border ${cfg.badgeClass}`}
                          >
                            <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: cfg.dotColor }} />
                            <span>{cfg.shortLabel}:</span>
                            <span className="font-bold">{count}</span>
                          </span>
                        );
                      })}
                      {previewData.summary.indicators_found === 0 && (
                        <span className="text-[11px] text-slate-400 font-mono">
                          No indicators detected in preview rows.
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Error Strategy Selection */}
              <div className="flex items-center gap-3">
                <label className="text-xs text-slate-400 font-medium">On invalid rows:</label>
                <select
                  value={onErrorStrategy}
                  onChange={(e) => setOnErrorStrategy(e.target.value)}
                  className="px-2.5 py-1.5 text-xs bg-slate-950 border border-slate-800 rounded text-slate-200 cursor-pointer"
                >
                  <option value="skip_invalid">Skip invalid rows</option>
                  <option value="reject_all">Reject entire file if any invalid</option>
                </select>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between">
              <span className="text-xs text-slate-400">
                Duplicates and invalid rows are automatically skipped unless 'Reject entire file' is selected.
              </span>
              <Button
                variant="primary"
                size="sm"
                loading={submitting}
                disabled={importableCount === 0 || (onErrorStrategy === 'reject_all' && (previewData.summary?.invalid || 0) > 0)}
                onClick={handleCommitFile}
              >
                Import {importableCount} valid rows
              </Button>
            </div>
          </Card>

          {/* First 200 Rows Preview Table */}
          <Card className="overflow-hidden border border-slate-800">
            <div className="px-4 py-3 bg-slate-950/80 border-b border-slate-800 flex items-center justify-between">
              <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                File Rows Preview
              </h4>
              {previewData.truncated && (
                <span className="text-[11px] font-mono text-amber-400">
                  Showing first 200 rows of {previewData.summary?.total}
                </span>
              )}
            </div>

            <div className="overflow-x-auto max-h-96">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-slate-950 text-slate-400 uppercase tracking-wider sticky top-0 border-b border-slate-800">
                  <tr>
                    <th className="px-3 py-2.5 w-16">Row</th>
                    <th className="px-3 py-2.5 w-28">Status</th>
                    <th className="px-3 py-2.5">Platform</th>
                    <th className="px-3 py-2.5">Author</th>
                    <th className="px-3 py-2.5">Timestamp</th>
                    <th className="px-3 py-2.5">Excerpt</th>
                    <th className="px-3 py-2.5 text-center">Indicators</th>
                    <th className="px-3 py-2.5">Validation Notes</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {previewData.rows?.map((r) => {
                    const isExpanded = expandedRows.has(r.row_number);
                    const indCount = r.extracted?.length || 0;

                    return (
                      <React.Fragment key={r.row_number}>
                        <tr className="hover:bg-slate-800/30">
                          <td className="px-3 py-2 text-slate-400">#{r.row_number}</td>
                          <td className="px-3 py-2 whitespace-nowrap">
                            <StatusBadge status={r.status} />
                          </td>
                          <td className="px-3 py-2 text-slate-200">{r.marketplace || '-'}</td>
                          <td className="px-3 py-2 text-slate-200">{r.username || '-'}</td>
                          <td className="px-3 py-2 text-slate-400 whitespace-nowrap text-[11px]">
                            {r.timestamp ? new Date(r.timestamp).toLocaleString() : 'N/A'}
                          </td>
                          <td className="px-3 py-2 font-sans text-slate-300 max-w-xs truncate">
                            {r.content_excerpt || '-'}
                          </td>
                          <td className="px-3 py-2 whitespace-nowrap text-center">
                            <button
                              type="button"
                              onClick={() => toggleRowExpanded(r.row_number)}
                              className={`px-2 py-0.5 rounded text-[11px] font-mono font-medium border transition-colors cursor-pointer inline-flex items-center gap-1 ${
                                indCount > 0
                                  ? 'bg-purple-950/60 text-purple-300 border-purple-800/80 hover:bg-purple-900/60'
                                  : 'bg-slate-900 text-slate-500 border-slate-800 hover:text-slate-400'
                              }`}
                            >
                              <span>{isExpanded ? '▾' : '▸'}</span>
                              <span>Indicators ({indCount})</span>
                            </button>
                          </td>
                          <td className="px-3 py-2 text-[11px] max-w-sm">
                            {r.errors?.length > 0 && (
                              <div className="text-rose-400 font-sans">{r.errors.join('; ')}</div>
                            )}
                            {r.warnings?.length > 0 && (
                              <div className="text-amber-400 font-sans">{r.warnings.join('; ')}</div>
                            )}
                            {r.errors?.length === 0 && r.warnings?.length === 0 && (
                              <span className="text-slate-400 font-sans">Passed</span>
                            )}
                          </td>
                        </tr>

                        {/* Expandable Extracted Indicators Row */}
                        {isExpanded && (
                          <tr className="bg-slate-950/90 border-b border-slate-800">
                            <td colSpan={8} className="px-4 py-3 space-y-2">
                              <div className="flex items-center justify-between text-xs text-slate-300">
                                <span className="font-semibold uppercase tracking-wider text-[11px]">
                                  Extracted Indicators for Row #{r.row_number} ({indCount})
                                </span>
                                {r.text_stats && (
                                  <span className="font-mono text-[11px] text-slate-400">
                                    Chars: {r.text_stats.char_count} • Words: {r.text_stats.word_count}
                                  </span>
                                )}
                              </div>

                              {r.content && (
                                <div>
                                  <span className="block text-[11px] font-medium text-slate-400 mb-1">
                                    Annotated Post Content:
                                  </span>
                                  <HighlightedText
                                    text={r.content}
                                    indicators={r.extracted || []}
                                    className="max-h-36 overflow-y-auto text-xs"
                                  />
                                </div>
                              )}

                              {indCount > 0 ? (
                                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2 pt-1">
                                  {r.extracted.map((ind, iIdx) => {
                                    const cfg = getIndicatorConfig(ind.indicator_type);
                                    return (
                                      <div
                                        key={iIdx}
                                        className="p-2 rounded bg-slate-900 border border-slate-800 flex flex-col gap-1 text-[11px]"
                                      >
                                        <div className="flex items-center justify-between">
                                          <span className={`inline-flex items-center gap-1 px-1.5 py-0.2 rounded text-[10px] font-semibold border ${cfg.badgeClass}`}>
                                            <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: cfg.dotColor }} />
                                            {cfg.shortLabel}
                                          </span>
                                          <span className="text-[10px] uppercase font-bold text-emerald-400">
                                            {ind.confidence}
                                          </span>
                                        </div>
                                        <div className="font-mono text-slate-200 truncate" title={ind.normalised_value}>
                                          {ind.normalised_value}
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                              ) : (
                                <p className="text-xs text-slate-500 font-mono italic">
                                  No indicators detected in this post text.
                                </p>
                              )}
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

// Color-and-text status badges
function StatusBadge({ status }) {
  if (status === 'valid') {
    return (
      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-950 text-emerald-300 border border-emerald-800">
        VALID
      </span>
    );
  }
  if (status === 'valid_with_warnings') {
    return (
      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-950 text-amber-300 border border-amber-800">
        WARNING
      </span>
    );
  }
  if (status === 'duplicate') {
    return (
      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-indigo-950 text-indigo-300 border border-indigo-800">
        DUPLICATE
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-rose-950 text-rose-300 border border-rose-800">
      INVALID
    </span>
  );
}

