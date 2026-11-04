import React from 'react';

export default function StageStatusCards({ registryStages = [], currentRun = null }) {
  const stageRunsMap = {};
  if (currentRun && currentRun.stages) {
    currentRun.stages.forEach((sr) => {
      stageRunsMap[sr.stage] = sr;
    });
  }

  const getStatusBadge = (stageInfo, stageRun) => {
    if (!stageInfo.available) {
      return (
        <span className="px-2 py-0.5 rounded text-xs font-medium bg-zinc-900 text-zinc-500 border border-zinc-800">
          Planned
        </span>
      );
    }

    if (!stageRun) {
      return (
        <span className="px-2 py-0.5 rounded text-xs font-medium bg-zinc-800/80 text-zinc-400 border border-zinc-700">
          Idle
        </span>
      );
    }

    const st = stageRun.status;
    if (st === 'completed') {
      return (
        <span className="px-2 py-0.5 rounded text-xs font-semibold bg-emerald-950/60 text-emerald-400 border border-emerald-800/80 flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
          COMPLETED
        </span>
      );
    }
    if (st === 'running') {
      return (
        <span className="px-2 py-0.5 rounded text-xs font-semibold bg-cyan-950/60 text-cyan-400 border border-cyan-800/80 flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse"></span>
          RUNNING
        </span>
      );
    }
    if (st === 'pending') {
      return (
        <span className="px-2 py-0.5 rounded text-xs font-semibold bg-amber-950/60 text-amber-400 border border-amber-800/80">
          PENDING
        </span>
      );
    }
    if (st === 'failed') {
      return (
        <span className="px-2 py-0.5 rounded text-xs font-semibold bg-rose-950/60 text-rose-400 border border-rose-800/80">
          FAILED
        </span>
      );
    }
    if (st === 'skipped') {
      return (
        <span className="px-2 py-0.5 rounded text-xs font-medium bg-zinc-900 text-zinc-500 border border-zinc-800">
          SKIPPED
        </span>
      );
    }

    return (
      <span className="px-2 py-0.5 rounded text-xs font-medium bg-zinc-800 text-zinc-400 border border-zinc-700">
        {st.toUpperCase()}
      </span>
    );
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5 mb-6">
      {registryStages.map((stage) => {
        const stageRun = stageRunsMap[stage.name];
        const summary = stageRun?.summary || {};
        const coverage = summary.coverage || null;

        return (
          <div
            key={stage.name}
            className={`p-4 rounded-lg border transition-all ${
              stageRun?.status === 'running'
                ? 'bg-cyan-950/10 border-cyan-700/60 ring-1 ring-cyan-700/30'
                : stageRun?.status === 'failed'
                ? 'bg-rose-950/10 border-rose-800/50'
                : 'bg-zinc-900/60 border-zinc-800/80 hover:border-zinc-700'
            }`}
          >
            <div className="flex items-center justify-between gap-2 mb-2">
              <h4 className="text-sm font-semibold text-zinc-200 truncate">{stage.label}</h4>
              {getStatusBadge(stage, stageRun)}
            </div>

            <p className="text-xs text-zinc-400 line-clamp-2 mb-3 h-8">{stage.description}</p>

            {stageRun ? (
              <div className="space-y-1.5 text-xs border-t border-zinc-800/60 pt-2.5">
                <div className="flex justify-between text-zinc-400">
                  <span>Evidence created:</span>
                  <span className="font-mono text-zinc-200 font-medium">
                    {stageRun.items_processed ?? summary.evidence_created ?? 0}
                  </span>
                </div>

                {coverage && (
                  <div className="flex justify-between text-zinc-400">
                    <span>Actor coverage:</span>
                    <span className="font-mono text-zinc-300">
                      {coverage.actors_with_dimension_indicators} / {coverage.actors_total} personas
                    </span>
                  </div>
                )}

                {summary.duration_ms !== undefined && (
                  <div className="flex justify-between text-zinc-500 text-[11px]">
                    <span>Execution time:</span>
                    <span className="font-mono">{summary.duration_ms} ms</span>
                  </div>
                )}

                {stageRun.error_message && (
                  <div className="mt-2 p-2 rounded bg-rose-950/40 border border-rose-900/60 text-rose-300 text-[11px]">
                    {stageRun.error_message}
                  </div>
                )}
              </div>
            ) : (
              <div className="text-xs text-zinc-500 italic border-t border-zinc-800/60 pt-2.5">
                Not included in run
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

