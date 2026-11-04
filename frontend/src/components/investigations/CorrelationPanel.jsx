import React, { useEffect, useRef, useState } from 'react';
import {
  fetchInvestigationEvidence,
  fetchInvestigationEvidenceDetail,
  fetchInvestigationPairs,
  fetchPipelineRunDetail,
  fetchPipelineRuns,
  fetchPipelineStages,
  triggerPipelineRun,
} from '../../lib/api';
import CommonIndicatorsNotice from './CommonIndicatorsNotice';
import PairsTable from './PairsTable';
import StageStatusCards from './StageStatusCards';

export default function CorrelationPanel({ investigationId, hasData = true }) {
  const [stages, setStages] = useState([]);
  const [runs, setRuns] = useState([]);
  const [activeRun, setActiveRun] = useState(null);
  const [pairs, setPairs] = useState([]);
  const [evidenceList, setEvidenceList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState(null);

  const pollIntervalRef = useRef(null);

  // Load stages and runs initially
  const loadInitialData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [stagesData, runsData] = await Promise.all([
        fetchPipelineStages(),
        fetchPipelineRuns(investigationId),
      ]);

      setStages(stagesData || []);
      setRuns(runsData || []);

      if (runsData && runsData.length > 0) {
        const latestRun = runsData[0];
        setActiveRun(latestRun);

        if (latestRun.status === 'completed') {
          await loadRunResults(latestRun.id);
        }
      }
    } catch (err) {
      setError(err.message || 'Failed to initialize correlation panel');
    } finally {
      setLoading(false);
    }
  };

  // Load pairs and evidence for a specific run
  const loadRunResults = async (runId) => {
    try {
      const [pairsRes, evRes] = await Promise.all([
        fetchInvestigationPairs(investigationId, { run_id: runId }),
        fetchInvestigationEvidence(investigationId, { run_id: runId, page_size: 100 }),
      ]);

      let pairItems = [];
      if (Array.isArray(pairsRes)) {
        pairItems = pairsRes;
      } else if (Array.isArray(pairsRes?.data)) {
        pairItems = pairsRes.data;
      } else if (Array.isArray(pairsRes?.items)) {
        pairItems = pairsRes.items;
      } else if (Array.isArray(pairsRes?.data?.items)) {
        pairItems = pairsRes.data.items;
      }

      let evItems = [];
      if (Array.isArray(evRes)) {
        evItems = evRes;
      } else if (Array.isArray(evRes?.data)) {
        evItems = evRes.data;
      } else if (Array.isArray(evRes?.items)) {
        evItems = evRes.items;
      } else if (Array.isArray(evRes?.data?.items)) {
        evItems = evRes.data.items;
      }

      // Fetch full evidence details (including source snippets) in parallel
      const detailedEvidence = await Promise.all(
        evItems.map(async (ev) => {
          try {
            return await fetchInvestigationEvidenceDetail(investigationId, ev.id);
          } catch {
            return ev;
          }
        })
      );

      setPairs(pairItems);
      setEvidenceList(detailedEvidence);
    } catch (err) {
      console.error('Failed to load correlation results:', err);
    }
  };

  useEffect(() => {
    loadInitialData();
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [investigationId]);

  // Polling mechanism while run is active (queued or running)
  useEffect(() => {
    if (activeRun && (activeRun.status === 'queued' || activeRun.status === 'running')) {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

      pollIntervalRef.current = setInterval(async () => {
        try {
          const updatedRun = await fetchPipelineRunDetail(investigationId, activeRun.id);
          setActiveRun(updatedRun);

          if (updatedRun.status === 'completed') {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
            await loadRunResults(updatedRun.id);
            // Refresh runs list
            const runsData = await fetchPipelineRuns(investigationId);
            setRuns(runsData || []);
          } else if (updatedRun.status === 'failed') {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
        } catch (err) {
          console.error('Polling error:', err);
        }
      }, 1500);
    } else {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    }

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [activeRun?.status, activeRun?.id, investigationId]);

  const handleRunCorrelation = async () => {
    try {
      setTriggering(true);
      setError(null);
      const newRun = await triggerPipelineRun(investigationId);
      setActiveRun(newRun);
      setRuns((prev) => [newRun, ...prev]);
    } catch (err) {
      setError(err.message || 'Failed to start correlation run');
    } finally {
      setTriggering(false);
    }
  };

  const isRunActive = activeRun && (activeRun.status === 'queued' || activeRun.status === 'running');

  // Collect suppressed common indicators from stage summaries
  let suppressedIndicators = [];
  if (activeRun && activeRun.stages) {
    activeRun.stages.forEach((stg) => {
      const supp = stg.summary?.suppressed_common_indicators;
      if (supp && Array.isArray(supp)) {
        suppressedIndicators.push(...supp);
      }
    });
  }

  if (loading) {
    return (
      <div className="p-12 text-center text-zinc-500 flex flex-col items-center justify-center gap-3">
        <div className="w-6 h-6 border-2 border-zinc-700 border-t-zinc-400 rounded-full animate-spin"></div>
        <span className="text-xs">Loading correlation environment...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header action bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-lg bg-zinc-900/60 border border-zinc-800">
        <div>
          <h3 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
            <span>Threat Correlation Engine</span>
            {activeRun && (
              <span
                className={`px-2 py-0.5 rounded text-xs font-mono font-medium ${
                  activeRun.status === 'completed'
                    ? 'bg-emerald-950/60 text-emerald-400 border border-emerald-800/60'
                    : activeRun.status === 'running'
                    ? 'bg-cyan-950/60 text-cyan-400 border border-cyan-800/60 animate-pulse'
                    : activeRun.status === 'failed'
                    ? 'bg-rose-950/60 text-rose-400 border border-rose-800/60'
                    : 'bg-zinc-800 text-zinc-400 border border-zinc-700'
                }`}
              >
                Run #{activeRun.id} • {activeRun.status.toUpperCase()}
              </span>
            )}
          </h3>
          <p className="text-xs text-zinc-400 mt-1">
            Correlate personas across darknet platforms using cryptographic artifacts and network infrastructure.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleRunCorrelation}
            disabled={!hasData || isRunActive || triggering}
            className={`px-4 py-2 rounded text-xs font-semibold shadow-sm transition-all flex items-center gap-2 ${
              !hasData || isRunActive || triggering
                ? 'bg-zinc-800 text-zinc-500 border border-zinc-700/60 cursor-not-allowed'
                : 'bg-cyan-600 hover:bg-cyan-500 text-white shadow-cyan-950/50 cursor-pointer'
            }`}
            title={
              !hasData
                ? 'Investigation has no posts or indicators to analyze'
                : isRunActive
                ? 'A correlation run is currently in progress'
                : 'Execute registered correlation stages'
            }
          >
            {isRunActive ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin"></div>
                <span>Correlating...</span>
              </>
            ) : (
              <>
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>Run correlation</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* No Data Warning */}
      {!hasData && (
        <div className="p-3.5 rounded-lg bg-zinc-900 border border-zinc-800 text-xs text-zinc-400 flex items-center gap-2">
          <svg className="w-4 h-4 text-amber-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <span>This investigation has no collected posts or indicators. Ingest or load sample data before running correlation.</span>
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div className="p-3.5 rounded-lg bg-rose-950/40 border border-rose-800/80 text-xs text-rose-300">
          <span className="font-semibold">Error:</span> {error}
        </div>
      )}

      {/* Stale Warning Banner */}
      {activeRun?.is_stale && (
        <div className="p-3.5 rounded-lg bg-amber-950/40 border border-amber-800/70 text-xs text-amber-300 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 shrink-0 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>New data was added after this run. Run again to include it.</span>
          </div>
          <button
            type="button"
            onClick={handleRunCorrelation}
            disabled={isRunActive || triggering}
            className="px-2.5 py-1 rounded bg-amber-900/60 hover:bg-amber-800/80 text-amber-200 border border-amber-700/60 font-medium transition-colors"
          >
            Re-run now
          </button>
        </div>
      )}

      {/* Stage status cards */}
      <StageStatusCards registryStages={stages} currentRun={activeRun} />

      {/* Suppressed common indicators */}
      <CommonIndicatorsNotice suppressedList={suppressedIndicators} />

      {/* Results View */}
      {activeRun ? (
        activeRun.status === 'completed' ? (
          pairs.length > 0 ? (
            <PairsTable
              pairs={pairs}
              evidenceList={evidenceList}
              investigationId={investigationId}
            />
          ) : (
            <div className="p-12 text-center rounded-lg border border-dashed border-zinc-800 text-zinc-500 text-sm">
              No shared indicators were found across the personas in this investigation.
            </div>
          )
        ) : activeRun.status === 'failed' ? (
          <div className="p-8 text-center rounded-lg bg-rose-950/20 border border-rose-900/50 text-rose-300 text-sm">
            <p className="font-semibold mb-1">Pipeline execution failed</p>
            <p className="text-xs text-rose-400">{activeRun.error_message}</p>
          </div>
        ) : (
          <div className="p-12 text-center rounded-lg border border-dashed border-zinc-800 text-zinc-400 text-sm space-y-2">
            <div className="w-6 h-6 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin mx-auto"></div>
            <p>Analyzing and cross-matching indicators across all platform personas...</p>
          </div>
        )
      ) : (
        <div className="p-12 text-center rounded-lg border border-dashed border-zinc-800 text-zinc-500 text-sm space-y-2">
          <p className="font-medium text-zinc-400">No correlation run yet</p>
          <p className="text-xs text-zinc-500">
            Click "Run correlation" above to evaluate cryptographic and infrastructure linkages.
          </p>
        </div>
      )}

      {/* Persistent Muted Ethics / Evidence Disclaimer */}
      <div className="pt-4 border-t border-zinc-900 text-center">
        <p className="text-xs text-zinc-500 italic">
          Evidence supports investigation. It does not identify a real-world person.
        </p>
      </div>
    </div>
  );
}
