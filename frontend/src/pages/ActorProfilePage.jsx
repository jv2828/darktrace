import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import { fetchInvestigationActorProfile } from '../lib/api';

export default function ActorProfilePage() {
  const { id: investigationId, actorId } = useParams();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [copiedValue, setCopiedValue] = useState(null);

  const loadProfile = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetchInvestigationActorProfile(investigationId, actorId);
      setProfile(res);
    } catch (err) {
      setError(err.message || 'Failed to load actor profile.');
    } finally {
      setLoading(false);
    }
  }, [investigationId, actorId]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  const handleCopy = (val) => {
    navigator.clipboard?.writeText(val);
    setCopiedValue(val);
    setTimeout(() => setCopiedValue(null), 2000);
  };

  if (loading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center gap-3">
        <Spinner size="lg" />
        <span className="text-xs text-slate-400 font-mono">
          Compiling forensic persona profile #{actorId}...
        </span>
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="py-12 space-y-4">
        <Link
          to={`/investigations/${investigationId}?tab=overview`}
          className="text-xs text-sky-400 hover:text-sky-300 font-medium"
        >
          &larr; Back to Investigation #{investigationId}
        </Link>
        <Card className="p-8">
          <EmptyState
            title="Persona Profile Not Found"
            message={error || 'Threat actor profile could not be retrieved.'}
            action={
              <Link to={`/investigations/${investigationId}`}>
                <Button variant="secondary" size="sm">
                  Return to Case Workspace
                </Button>
              </Link>
            }
          />
        </Card>
      </div>
    );
  }

  const aliases = profile.aliases || [];
  const marketplaces = profile.marketplaces || [];
  const pgpKeys = profile.pgp_identifiers || [];
  const wallets = profile.wallet_identifiers || [];
  const infra = profile.infrastructure_indicators || [];
  const behaviour = profile.behaviour_summary || {};
  const stylometry = profile.stylometry_summary || {};
  const recentPosts = profile.recent_posts || [];
  const contradictions = profile.contradictions || [];
  const relatedPersonas = profile.possible_related_personas || [];

  return (
    <div className="space-y-6">
      {/* Breadcrumb Navigation */}
      <div className="flex items-center justify-between text-xs text-slate-400">
        <div className="flex items-center gap-2">
          <Link
            to={`/investigations/${investigationId}?tab=overview`}
            className="text-sky-400 hover:text-sky-300 font-medium"
          >
            &larr; Back to Investigation #{investigationId}
          </Link>
          <span>/</span>
          <span className="text-slate-200 font-mono">Actor: {profile.primary_username}</span>
        </div>
      </div>

      {/* Header Profile Card */}
      <Card className="p-5 border-slate-800">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <h1 className="text-xl font-bold text-slate-100 font-mono">
                {profile.primary_username}
              </h1>
              <span className="px-2 py-0.5 rounded text-[11px] font-mono uppercase bg-slate-800 text-slate-300 border border-slate-700">
                {profile.marketplace}
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Threat persona active across darknet illicit trade channels
            </p>
          </div>

          <div className="flex items-center gap-4 text-xs font-mono">
            <div className="text-right">
              <span className="text-slate-500 uppercase text-[10px] block">Observed Posts</span>
              <span className="text-slate-200 font-bold text-base">{profile.post_count}</span>
            </div>
            <div className="text-right border-l border-slate-800 pl-4">
              <span className="text-slate-500 uppercase text-[10px] block">First Seen</span>
              <span className="text-slate-300">
                {profile.first_seen ? profile.first_seen.substring(0, 10) : '—'}
              </span>
            </div>
            <div className="text-right border-l border-slate-800 pl-4">
              <span className="text-slate-500 uppercase text-[10px] block">Last Seen</span>
              <span className="text-slate-300">
                {profile.last_seen ? profile.last_seen.substring(0, 10) : '—'}
              </span>
            </div>
          </div>
        </div>

        {/* Aliases & Marketplaces tags */}
        <div className="mt-4 pt-4 border-t border-slate-800/80 flex flex-wrap items-center gap-6 text-xs">
          <div>
            <span className="text-[10px] uppercase font-semibold text-slate-500 mr-2">
              Known Aliases:
            </span>
            {aliases.length > 0 ? (
              <span className="space-x-1.5">
                {aliases.map((al, idx) => (
                  <span
                    key={idx}
                    className="px-2 py-0.5 rounded text-[11px] font-mono bg-slate-800/80 text-slate-300 border border-slate-700"
                  >
                    {al}
                  </span>
                ))}
              </span>
            ) : (
              <span className="text-slate-500">None identified</span>
            )}
          </div>

          <div>
            <span className="text-[10px] uppercase font-semibold text-slate-500 mr-2">
              Operating Platforms:
            </span>
            <span className="space-x-1.5">
              {marketplaces.map((m, idx) => (
                <span
                  key={idx}
                  className="px-2 py-0.5 rounded text-[11px] font-mono bg-slate-800/80 text-sky-300 border border-slate-700"
                >
                  {m}
                </span>
              ))}
            </span>
          </div>
        </div>
      </Card>

      {/* Forensic Intelligence Sections Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Cryptographic & Infrastructure Indicators */}
        <Card className="p-4 border-slate-800 space-y-4">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-200 border-b border-slate-800 pb-2">
            Cryptographic &amp; Network Fingerprints
          </h2>

          <div className="space-y-3 text-xs">
            {/* PGP Keys */}
            <div>
              <span className="text-[10px] uppercase font-semibold text-slate-400 block mb-1">
                PGP Key Fingerprints ({pgpKeys.length})
              </span>
              {pgpKeys.length > 0 ? (
                <div className="space-y-1">
                  {pgpKeys.map((k, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-2 rounded bg-slate-900 border border-slate-800 font-mono text-[11px]"
                    >
                      <span className="text-amber-400 break-all">{k}</span>
                      <button
                        type="button"
                        onClick={() => handleCopy(k)}
                        className="text-slate-500 hover:text-slate-300 ml-2"
                      >
                        {copiedValue === k ? '✓' : '⧉'}
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <span className="text-slate-500">No PGP keys extracted</span>
              )}
            </div>

            {/* Wallets */}
            <div>
              <span className="text-[10px] uppercase font-semibold text-slate-400 block mb-1">
                Cryptocurrency Addresses ({wallets.length})
              </span>
              {wallets.length > 0 ? (
                <div className="space-y-1">
                  {wallets.map((w, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-2 rounded bg-slate-900 border border-slate-800 font-mono text-[11px]"
                    >
                      <span className="text-emerald-400 break-all">{w}</span>
                      <button
                        type="button"
                        onClick={() => handleCopy(w)}
                        className="text-slate-500 hover:text-slate-300 ml-2"
                      >
                        {copiedValue === w ? '✓' : '⧉'}
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <span className="text-slate-500">No cryptocurrency wallets extracted</span>
              )}
            </div>

            {/* Infrastructure */}
            <div>
              <span className="text-[10px] uppercase font-semibold text-slate-400 block mb-1">
                Infrastructure &amp; Contact Endpoints ({infra.length})
              </span>
              {infra.length > 0 ? (
                <div className="space-y-1">
                  {infra.map((inf, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-2 rounded bg-slate-900 border border-slate-800 font-mono text-[11px]"
                    >
                      <span className="text-purple-400 break-all">{inf}</span>
                      <button
                        type="button"
                        onClick={() => handleCopy(inf)}
                        className="text-slate-500 hover:text-slate-300 ml-2"
                      >
                        {copiedValue === inf ? '✓' : '⧉'}
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <span className="text-slate-500">No infrastructure indicators found</span>
              )}
            </div>
          </div>
        </Card>

        {/* Behavioral & Stylometric Baseline */}
        <Card className="p-4 border-slate-800 space-y-4">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-200 border-b border-slate-800 pb-2">
            Behavioral &amp; Stylometric Characteristics
          </h2>

          <div className="space-y-4 text-xs">
            <div>
              <span className="text-[10px] uppercase font-semibold text-slate-400 block mb-2">
                Temporal Writeprint
              </span>
              <div className="grid grid-cols-2 gap-2">
                <div className="p-2.5 rounded bg-slate-900 border border-slate-800">
                  <span className="text-slate-500 text-[10px] uppercase block">Diurnal Window</span>
                  <span className="font-mono text-slate-200 font-semibold">
                    {behaviour.active_hour_window_str || 'N/A'}
                  </span>
                </div>
                <div className="p-2.5 rounded bg-slate-900 border border-slate-800">
                  <span className="text-slate-500 text-[10px] uppercase block">Peak Hour</span>
                  <span className="font-mono text-slate-200 font-semibold">
                    {behaviour.peak_hour !== undefined ? `${behaviour.peak_hour}:00 UTC` : 'N/A'}
                  </span>
                </div>
                <div className="p-2.5 rounded bg-slate-900 border border-slate-800">
                  <span className="text-slate-500 text-[10px] uppercase block">Frequency</span>
                  <span className="font-mono text-slate-200 font-semibold">
                    {behaviour.posts_per_week ? `${behaviour.posts_per_week.toFixed(1)} posts/wk` : '—'}
                  </span>
                </div>
                <div className="p-2.5 rounded bg-slate-900 border border-slate-800">
                  <span className="text-slate-500 text-[10px] uppercase block">Data Volume</span>
                  <span className="font-mono text-slate-200 font-semibold">
                    {behaviour.total_posts || profile.post_count} posts
                  </span>
                </div>
              </div>
            </div>

            <div>
              <span className="text-[10px] uppercase font-semibold text-slate-400 block mb-2">
                Linguistic Metrics
              </span>
              <div className="grid grid-cols-2 gap-2">
                <div className="p-2.5 rounded bg-slate-900 border border-slate-800">
                  <span className="text-slate-500 text-[10px] uppercase block">Avg Sentence Length</span>
                  <span className="font-mono text-slate-200 font-semibold">
                    {stylometry.avg_sentence_len ? `${stylometry.avg_sentence_len.toFixed(1)} words` : '—'}
                  </span>
                </div>
                <div className="p-2.5 rounded bg-slate-900 border border-slate-800">
                  <span className="text-slate-500 text-[10px] uppercase block">Avg Word Length</span>
                  <span className="font-mono text-slate-200 font-semibold">
                    {stylometry.avg_word_len ? `${stylometry.avg_word_len.toFixed(2)} chars` : '—'}
                  </span>
                </div>
                <div className="p-2.5 rounded bg-slate-900 border border-slate-800">
                  <span className="text-slate-500 text-[10px] uppercase block">Punctuation Rate</span>
                  <span className="font-mono text-slate-200 font-semibold">
                    {stylometry.punctuation_rate ? `${(stylometry.punctuation_rate * 100).toFixed(1)}%` : '—'}
                  </span>
                </div>
                <div className="p-2.5 rounded bg-slate-900 border border-slate-800">
                  <span className="text-slate-500 text-[10px] uppercase block">Uppercase Rate</span>
                  <span className="font-mono text-slate-200 font-semibold">
                    {stylometry.uppercase_rate ? `${(stylometry.uppercase_rate * 100).toFixed(1)}%` : '—'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* Possible Related Personas Section */}
      <div className="space-y-3">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
            Possible Related Personas ({relatedPersonas.length})
          </h2>
          <p className="text-xs text-slate-400">
            Personas exhibiting correlated cryptographic, infrastructure, or stylistic patterns.
          </p>
        </div>

        {/* Mandatory Disclaimer */}
        <div className="p-3.5 rounded-lg border border-slate-800 bg-slate-900/60 text-xs text-slate-300">
          <span className="font-semibold text-amber-400">Heuristic Correlation Notice: </span>
          Scores represent heuristic evidence strength across observed data. They do not constitute definitive identity confirmation. Personas may share indicators or infrastructure without being the same physical person.
        </div>

        {relatedPersonas.length === 0 ? (
          <Card className="p-6">
            <EmptyState
              title="No Related Personas Identified"
              message="No other personas meet the correlation threshold (>= 0.45) with this actor."
            />
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {relatedPersonas.map((rel) => (
              <Card key={rel.actor_id} className="p-4 border-slate-800 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <Link
                      to={`/investigations/${investigationId}/actors/${rel.actor_id}`}
                      className="font-mono font-bold text-sky-400 hover:text-sky-300 hover:underline flex items-center gap-1.5"
                    >
                      <span>{rel.username}</span>
                      <span className="text-[10px] font-sans px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700">
                        {rel.marketplace}
                      </span>
                    </Link>
                    <Badge variant={rel.level === 'strong' ? 'success' : 'warning'}>
                      {rel.level?.toUpperCase()}
                    </Badge>
                  </div>

                  <div className="flex items-center gap-3 my-2 text-xs">
                    <div className="flex items-center gap-1.5">
                      <span className="text-slate-400">Evidence Score:</span>
                      <span className="font-mono font-bold text-slate-100">
                        {rel.score.toFixed(2)}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-slate-400">Coverage:</span>
                      <span className="font-mono text-slate-300">
                        {Math.round(rel.coverage * 100)}%
                      </span>
                    </div>
                  </div>

                  <p className="text-slate-300 text-xs mt-2 bg-slate-900 p-2.5 rounded border border-slate-800">
                    {rel.top_explanation}
                  </p>
                </div>

                <div className="mt-3 pt-2 border-t border-slate-800 text-right">
                  <Link to={`/investigations/${investigationId}/actors/${rel.actor_id}`}>
                    <Button variant="ghost" size="sm">
                      Inspect Partner Profile &rarr;
                    </Button>
                  </Link>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Contradictory Evidence Identified */}
      {contradictions.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-rose-300">
            Contradictory Evidence Identified ({contradictions.length})
          </h2>

          <Card className="p-4 border-rose-900/60 bg-rose-950/20 text-xs">
            <div className="space-y-2">
              {contradictions.map((ct, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded bg-slate-900/80 border border-rose-900/50 flex items-start justify-between gap-4"
                >
                  <div>
                    <span className="font-bold text-rose-300 uppercase text-[10px] block">
                      Conflict with {ct.partner_username} ({ct.partner_marketplace})
                    </span>
                    <p className="text-slate-300 mt-1">{ct.short_text}</p>
                  </div>
                  <span className="font-mono text-rose-400 font-semibold">
                    Strength: {ct.strength}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* Recent Posts */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
          Recent Communications ({recentPosts.length})
        </h2>

        <Card className="overflow-hidden border-slate-800">
          {recentPosts.length === 0 ? (
            <div className="p-6 text-center text-xs text-slate-500">
              No recent posts indexed for this actor.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-900/80 text-[11px] font-semibold uppercase tracking-wider text-slate-400 border-b border-slate-800">
                  <tr>
                    <th scope="col" className="py-2.5 px-3">Post ID</th>
                    <th scope="col" className="py-2.5 px-3">Marketplace</th>
                    <th scope="col" className="py-2.5 px-3">Posted At</th>
                    <th scope="col" className="py-2.5 px-3">Content Excerpt</th>
                    <th scope="col" className="py-2.5 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/80 font-mono text-[11px]">
                  {recentPosts.map((post) => (
                    <tr key={post.id} className="hover:bg-slate-800/30">
                      <td className="py-2.5 px-3 text-slate-200">#{post.id}</td>
                      <td className="py-2.5 px-3 font-sans">
                        <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400 border border-slate-700">
                          {post.marketplace}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-slate-400">
                        {post.posted_at ? new Date(post.posted_at).toLocaleString() : '—'}
                      </td>
                      <td className="py-2.5 px-3 font-sans text-slate-300 max-w-md truncate">
                        {post.content_preview}
                      </td>
                      <td className="py-2.5 px-3 text-right font-sans">
                        <Link to={`/investigations/${investigationId}/posts/${post.id}`}>
                          <Button variant="ghost" size="sm">
                            View Post
                          </Button>
                        </Link>
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

