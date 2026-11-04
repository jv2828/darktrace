import React, { useState, useEffect, useCallback } from 'react';
import Card from '../../ui/Card';
import Badge from '../../ui/Badge';
import Button from '../../ui/Button';
import Spinner from '../../ui/Spinner';
import EmptyState from '../../ui/EmptyState';
import { useToast } from '../../ui/Toast';
import {
  fetchInvestigationReports,
  generateDossierReportApi,
  downloadReportFileApi,
} from '../../../lib/api';

export default function DossierTab({ investigationId, runId }) {
  const toast = useToast();
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Export parameters
  const [format, setFormat] = useState('pdf'); // 'pdf' | 'csv' | 'json'
  const [csvKind, setCsvKind] = useState('pairs'); // 'pairs' | 'evidence' | 'indicators'
  const [generating, setGenerating] = useState(false);
  const [downloadingId, setDownloadingId] = useState(null);

  const loadReports = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetchInvestigationReports(investigationId);
      setReports(Array.isArray(res) ? res : []);
    } catch (err) {
      setError(err.message || 'Failed to load report history.');
    } finally {
      setLoading(false);
    }
  }, [investigationId]);

  useEffect(() => {
    loadReports();
  }, [loadReports]);

  const handleGenerateDossier = async (e) => {
    e.preventDefault();
    setGenerating(true);
    try {
      const payload = {
        format,
        run_id: runId || undefined,
      };
      if (format === 'csv') {
        payload.csv_kind = csvKind;
      }

      const res = await generateDossierReportApi(investigationId, payload);
      toast.success(
        `Dossier generated successfully: ${res.file_name} (${(res.file_size_bytes / 1024).toFixed(1)} KB)`
      );
      loadReports();
    } catch (err) {
      toast.error(err.message || 'Failed to generate investigation report.');
    } finally {
      setGenerating(false);
    }
  };

  const handleDownload = async (report) => {
    setDownloadingId(report.id);
    try {
      await downloadReportFileApi(investigationId, report.id, report.file_name);
      toast.success(`Download started: ${report.file_name}`);
    } catch (err) {
      toast.error(err.message || 'Failed to download report file.');
    } finally {
      setDownloadingId(null);
    }
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return '0 B';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  if (loading) {
    return (
      <div className="py-20 flex flex-col items-center justify-center gap-3">
        <Spinner size="md" />
        <span className="text-xs text-slate-400 font-mono">Loading dossier archive...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Export Generation Form */}
      <Card className="p-5 border-slate-800 space-y-4">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
            Generate Forensic Dossier Export
          </h2>
          <p className="text-xs text-slate-400">
            Compile formal investigative reports, cryptographic indicators, and mathematical correlation matrices.
          </p>
        </div>

        <form onSubmit={handleGenerateDossier} className="flex flex-wrap items-end gap-4 text-xs">
          <div className="space-y-1.5">
            <label htmlFor="dossier-format" className="font-medium text-slate-300">
              Export Format
            </label>
            <select
              id="dossier-format"
              value={format}
              onChange={(e) => setFormat(e.target.value)}
              className="bg-slate-900 border border-slate-700 text-slate-200 rounded px-3 py-2 text-xs focus:outline-none focus:border-slate-500"
            >
              <option value="pdf">PDF Forensic Dossier (ReportLab)</option>
              <option value="csv">CSV Spreadsheet Export</option>
              <option value="json">JSON Complete Machine Data</option>
            </select>
          </div>

          {format === 'csv' && (
            <div className="space-y-1.5">
              <label htmlFor="csv-dataset" className="font-medium text-slate-300">
                CSV Dataset
              </label>
              <select
                id="csv-dataset"
                value={csvKind}
                onChange={(e) => setCsvKind(e.target.value)}
                className="bg-slate-900 border border-slate-700 text-slate-200 rounded px-3 py-2 text-xs focus:outline-none focus:border-slate-500"
              >
                <option value="pairs">Correlated Persona Pairs</option>
                <option value="evidence">Supporting & Contradicting Evidence</option>
                <option value="indicators">Technical Threat Indicators</option>
              </select>
            </div>
          )}

          <Button variant="primary" size="sm" type="submit" loading={generating}>
            Generate Dossier
          </Button>
        </form>

        <div className="text-[11px] text-slate-500 space-y-1">
          <p>
            * All generated reports embed academic ethics disclosures and methodological limitations. CSV exports sanitize formulas against injection attacks.
          </p>
        </div>
      </Card>

      {/* Generated Reports History */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
            Dossier Archive & Export History ({reports.length})
          </h2>
          <Button variant="ghost" size="sm" onClick={loadReports}>
            Refresh
          </Button>
        </div>

        {error && (
          <div className="p-3 rounded bg-rose-950/40 border border-rose-900/60 text-xs text-rose-300">
            {error}
          </div>
        )}

        <Card className="overflow-hidden border-slate-800">
          {reports.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-500">
              No exported dossiers exist for this investigation yet. Use the controls above to generate one.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-900/80 text-[11px] font-semibold uppercase tracking-wider text-slate-400 border-b border-slate-800">
                  <tr>
                    <th scope="col" className="py-2.5 px-3">Report ID</th>
                    <th scope="col" className="py-2.5 px-3">Format</th>
                    <th scope="col" className="py-2.5 px-3">File Name</th>
                    <th scope="col" className="py-2.5 px-3">Size</th>
                    <th scope="col" className="py-2.5 px-3">Generated</th>
                    <th scope="col" className="py-2.5 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80 font-mono text-[11px]">
                  {reports.map((rpt) => (
                    <tr key={rpt.id} className="hover:bg-slate-800/30">
                      <td className="py-2.5 px-3 text-slate-200">#{rpt.id}</td>
                      <td className="py-2.5 px-3 font-sans">
                        <Badge
                          variant={
                            rpt.format === 'pdf'
                              ? 'danger'
                              : rpt.format === 'csv'
                              ? 'success'
                              : 'primary'
                          }
                        >
                          {rpt.format?.toUpperCase()}
                        </Badge>
                      </td>
                      <td className="py-2.5 px-3 text-slate-200 font-sans">{rpt.file_name}</td>
                      <td className="py-2.5 px-3 text-slate-400">
                        {formatFileSize(rpt.file_size_bytes)}
                      </td>
                      <td className="py-2.5 px-3 text-slate-400">
                        {rpt.created_at ? new Date(rpt.created_at).toLocaleString() : '—'}
                      </td>
                      <td className="py-2.5 px-3 text-right font-sans">
                        <Button
                          variant="secondary"
                          size="sm"
                          loading={downloadingId === rpt.id}
                          onClick={() => handleDownload(rpt)}
                        >
                          Download
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

