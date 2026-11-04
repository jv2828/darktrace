import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import ErrorState from '../components/ui/ErrorState';
import HighlightedText from '../components/common/HighlightedText';
import { fetchInvestigationPostDetail } from '../lib/api';
import {
  getIndicatorConfig,
  formatIndicatorDetails,
} from '../lib/indicatorTypes';

export default function PostDetailPage() {
  const { id: investigationId, postId } = useParams();
  const [post, setPost] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [copiedText, setCopiedText] = useState(false);
  const [copiedNormId, setCopiedNormId] = useState(null);

  const loadPost = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchInvestigationPostDetail(investigationId, postId);
      setPost(data);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [investigationId, postId]);

  useEffect(() => {
    loadPost();
  }, [loadPost]);

  async function handleCopyContent() {
    if (!post?.content) return;
    try {
      await navigator.clipboard.writeText(post.content);
      setCopiedText(true);
      setTimeout(() => setCopiedText(false), 2000);
    } catch (err) {
      console.error('Copy content failed:', err);
    }
  }

  async function handleCopyNormalized(value, id) {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedNormId(id);
      setTimeout(() => setCopiedNormId(null), 2000);
    } catch (err) {
      console.error('Copy failed:', err);
    }
  }

  if (loading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center gap-3">
        <Spinner size="lg" />
        <p className="text-xs text-slate-400 font-mono">Loading post #{postId} detail...</p>
      </div>
    );
  }

  if (error) {
    if (error.status === 404 || error.code === 'NOT_FOUND') {
      return (
        <div className="py-12 space-y-4">
          <Link
            to={`/investigations/${investigationId}`}
            className="text-xs text-sky-400 hover:text-sky-300 font-medium inline-flex items-center gap-1"
          >
            &larr; Back to Investigation #{investigationId}
          </Link>
          <EmptyState
            title="Post Not Found"
            message={`Post #${postId} does not exist in investigation #${investigationId} or you do not have permission to view it.`}
            action={
              <Link to={`/investigations/${investigationId}`}>
                <Button variant="secondary" size="sm">
                  Return to Investigation
                </Button>
              </Link>
            }
          />
        </div>
      );
    }

    return (
      <div className="py-12 space-y-4">
        <Link
          to={`/investigations/${investigationId}`}
          className="text-xs text-sky-400 hover:text-sky-300 font-medium inline-flex items-center gap-1"
        >
          &larr; Back to Investigation #{investigationId}
        </Link>
        <ErrorState
          title="Failed to Load Post"
          message={error.message || 'Unable to retrieve post data.'}
          onRetry={loadPost}
        />
      </div>
    );
  }

  if (!post) return null;

  const structuredFields = post.structured_indicators || {};
  const hasStructured = Object.keys(structuredFields).length > 0;
  const indicators = post.indicators || [];

  return (
    <div className="space-y-6">
      {/* Navigation Breadcrumb */}
      <div className="flex items-center justify-between">
        <Link
          to={`/investigations/${investigationId}`}
          className="text-xs text-sky-400 hover:text-sky-300 font-medium inline-flex items-center gap-1"
        >
          &larr; Back to Investigation #{investigationId}
        </Link>
        <span className="text-xs font-mono text-slate-400">
          Post ID #{post.id}
        </span>
      </div>

      <PageHeader
        title={`Darknet Post Detail: @${post.author_username}`}
        description={`Published on ${post.marketplace || 'Unknown Marketplace'} • Dataset: ${post.dataset_name || 'N/A'}`}
        action={
          <Button variant="secondary" size="sm" onClick={handleCopyContent}>
            {copiedText ? 'Copied Raw Text!' : 'Copy Raw Text'}
          </Button>
        }
      />

      {/* Provenance Metadata Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs">
        <Card className="p-3">
          <span className="text-[10px] uppercase text-slate-400 font-sans block mb-1">
            Platform / Market
          </span>
          <span className="text-slate-200 font-semibold">{post.marketplace || 'N/A'}</span>
        </Card>

        <Card className="p-3">
          <span className="text-[10px] uppercase text-slate-400 font-sans block mb-1">
            Author Handle
          </span>
          <span className="text-slate-200 font-semibold">{`@${post.author_username}`}</span>
        </Card>

        <Card className="p-3">
          <span className="text-[10px] uppercase text-slate-400 font-sans block mb-1">
            Posted Timestamp
          </span>
          <span className="text-slate-200">
            {post.posted_at ? new Date(post.posted_at).toUTCString() : 'N/A'}
          </span>
        </Card>

        <Card className="p-3">
          <span className="text-[10px] uppercase text-slate-400 font-sans block mb-1">
            Extractor Status
          </span>
          <span className="text-slate-200">
            v{post.extractor_version || '1.0.0'} (
            {post.extracted_at ? new Date(post.extracted_at).toLocaleTimeString() : 'N/A'})
          </span>
        </Card>
      </div>

      {post.source_reference && (
        <div className="p-2.5 rounded bg-slate-900/60 border border-slate-800 text-xs font-mono text-slate-400 flex items-center gap-2">
          <span className="font-sans uppercase text-[10px] text-slate-400 font-semibold">
            Source Reference:
          </span>
          <span className="text-slate-200 truncate">{post.source_reference}</span>
        </div>
      )}

      {/* Main Content Layout: Annotated Text on Left, Indicators on Right / Below */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Original Text View with Highlighted Indicators */}
        <div className="lg:col-span-7 space-y-4">
          <Card className="p-4 border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                Original Post Text ({post.content?.length || 0} characters)
              </h3>
              <span className="text-[11px] font-mono text-slate-400">
                {indicators.length} indicators annotated
              </span>
            </div>

            <HighlightedText
              text={post.content || ''}
              indicators={indicators}
              className="min-h-48 text-sm"
            />
          </Card>

          {/* Optional Structured Fields Card */}
          {hasStructured && (
            <Card className="p-4 border-slate-800 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                  Structured Metadata Indicators
                </h3>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-emerald-950 text-emerald-300 border border-emerald-800 uppercase">
                  Explicit Fields
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 font-mono text-xs">
                {Object.entries(structuredFields).map(([key, val]) => (
                  <div
                    key={key}
                    className="p-2.5 rounded bg-slate-950/80 border border-slate-800 flex flex-col gap-1"
                  >
                    <span className="text-[10px] uppercase font-sans text-slate-400 font-semibold">
                      {key.replace('_', ' ')}
                    </span>
                    <span className="text-slate-200 truncate font-mono" title={String(val)}>
                      {String(val)}
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>

        {/* Right Column: Extracted Indicators Table */}
        <div className="lg:col-span-5 space-y-4">
          <Card className="p-4 border-slate-800 space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                Extracted Indicators ({indicators.length})
              </h3>
              <span className="text-[11px] font-mono text-slate-400">
                Sorted by appearance
              </span>
            </div>

            {indicators.length === 0 ? (
              <p className="text-xs text-slate-400 font-mono py-8 text-center italic">
                No technical indicators found in this communication.
              </p>
            ) : (
              <div className="space-y-2.5 max-h-[600px] overflow-y-auto pr-1">
                {indicators.map((ind, idx) => {
                  const cfg = getIndicatorConfig(ind.indicator_type);
                  const detailStr = formatIndicatorDetails(ind);
                  const isCopied = copiedNormId === (ind.id || idx);

                  return (
                    <div
                      key={ind.id || idx}
                      className="p-3 rounded-lg bg-slate-950/80 border border-slate-800 hover:border-slate-700 transition-colors space-y-2"
                    >
                      {/* Header: Type and Confidence */}
                      <div className="flex items-center justify-between">
                        <span
                          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-semibold border ${cfg.badgeClass}`}
                        >
                          <span
                            className="w-1.5 h-1.5 rounded-full inline-block"
                            style={{ backgroundColor: cfg.dotColor }}
                          />
                          {cfg.label}
                        </span>

                        <div className="flex items-center gap-1.5">
                          {ind.details?.also_in_structured_field && (
                            <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-sky-950 text-sky-300 border border-sky-800">
                              Also Structured
                            </span>
                          )}
                          <span
                            className={`px-1.5 py-0.2 rounded text-[10px] font-bold uppercase font-mono ${
                              ind.confidence === 'high'
                                ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                                : ind.confidence === 'medium'
                                ? 'bg-amber-950 text-amber-400 border border-amber-800'
                                : 'bg-rose-950 text-rose-400 border border-rose-800'
                            }`}
                          >
                            {ind.confidence || 'high'}
                          </span>
                        </div>
                      </div>

                      {/* Normalized Value with copy */}
                      <div className="space-y-0.5">
                        <div className="text-[10px] uppercase font-sans text-slate-400 font-semibold">
                          Normalized Value
                        </div>
                        <div className="flex items-center justify-between gap-2 p-1.5 rounded bg-slate-900 border border-slate-800/80 font-mono text-xs text-slate-200">
                          <span className="truncate" title={ind.normalised_value}>
                            {ind.normalised_value}
                          </span>
                          <button
                            type="button"
                            onClick={() => handleCopyNormalized(ind.normalised_value, ind.id || idx)}
                            className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors cursor-pointer shrink-0"
                          >
                            {isCopied ? 'Copied' : 'Copy'}
                          </button>
                        </div>
                      </div>

                      {/* Raw Value and Method */}
                      <div className="grid grid-cols-2 gap-2 text-[11px] font-mono text-slate-400">
                        <div>
                          <span className="text-[10px] uppercase font-sans text-slate-400 block">
                            Raw In Text
                          </span>
                          <span className="text-slate-300 truncate block" title={ind.raw_value}>
                            {ind.raw_value}
                          </span>
                        </div>
                        <div>
                          <span className="text-[10px] uppercase font-sans text-slate-400 block">
                            Method / Spans
                          </span>
                          <span className="text-slate-300 truncate block">
                            {ind.extraction_method}
                            {ind.span_start !== null && ind.span_start !== undefined
                              ? ` [${ind.span_start}:${ind.span_end}]`
                              : ''}
                          </span>
                        </div>
                      </div>

                      {/* Additional Details */}
                      {detailStr && (
                        <div className="pt-1 border-t border-slate-900 text-[11px] font-mono text-slate-400">
                          {detailStr}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
