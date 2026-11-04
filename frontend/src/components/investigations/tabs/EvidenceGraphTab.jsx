import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import cytoscape from 'cytoscape';
import Card from '../../ui/Card';
import Badge from '../../ui/Badge';
import Button from '../../ui/Button';
import Spinner from '../../ui/Spinner';
import EmptyState from '../../ui/EmptyState';
import { fetchInvestigationGraph } from '../../../lib/api';

const NODE_COLORS = {
  persona: '#0284c7', // sky-600
  marketplace: '#64748b', // slate-500
  pgp: '#d97706', // amber-600
  wallet: '#059669', // emerald-600
  infrastructure: '#9333ea', // purple-600
};

const NODE_SHAPES = {
  persona: 'ellipse',
  marketplace: 'round-rectangle',
  pgp: 'diamond',
  wallet: 'hexagon',
  infrastructure: 'pentagon',
};

export default function EvidenceGraphTab({ investigationId, runId, onTriggerRun }) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);

  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filter controls
  const [minScore, setMinScore] = useState(0.2);
  const [selectedLayout, setSelectedLayout] = useState('cose');
  const [enabledTypes, setEnabledTypes] = useState({
    persona: true,
    marketplace: true,
    pgp: true,
    wallet: true,
    infrastructure: true,
  });

  // Selected element for side panel
  const [selectedElement, setSelectedElement] = useState(null);
  const [showTableMode, setShowTableMode] = useState(false);

  // Fetch graph data from backend
  const loadGraph = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetchInvestigationGraph(investigationId, {
        run_id: runId,
        min_score: minScore,
        max_nodes: 250,
      });
      setGraphData(res);
    } catch (err) {
      setError(err.message || 'Failed to fetch evidence graph.');
    } finally {
      setLoading(false);
    }
  }, [investigationId, runId, minScore]);

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);

  // Initialize or update Cytoscape instance
  useEffect(() => {
    if (!containerRef.current || !graphData || showTableMode) return;

    // Filter nodes by enabled types
    const filteredNodes = (graphData.nodes || []).filter((n) => {
      const type = n.data?.type;
      return enabledTypes[type] !== false;
    });

    const activeNodeIds = new Set(filteredNodes.map((n) => n.data.id));

    // Filter edges whose source & target exist in activeNodeIds
    const filteredEdges = (graphData.edges || []).filter((e) => {
      return activeNodeIds.has(e.data.source) && activeNodeIds.has(e.data.target);
    });

    try {
      if (cyRef.current) {
        cyRef.current.destroy();
      }

      const cy = cytoscape({
        container: containerRef.current,
        elements: {
          nodes: filteredNodes,
          edges: filteredEdges,
        },
        style: [
          {
            selector: 'node',
            style: {
              'background-color': (ele) => NODE_COLORS[ele.data('type')] || '#64748b',
              shape: (ele) => NODE_SHAPES[ele.data('type')] || 'ellipse',
              label: (ele) => (ele.data('type') === 'persona' ? (ele.data('username') || ele.data('label') || '') : (ele.data('label') || '')),
              color: '#f1f5f9',
              'font-size': '11px',
              'font-family': 'monospace',
              'text-valign': 'bottom',
              'text-margin-y': 4,
              width: (ele) => (ele.data('type') === 'persona' ? 32 : 24),
              height: (ele) => (ele.data('type') === 'persona' ? 32 : 24),
              'border-width': 2,
              'border-color': '#0f172a',
            },
          },
          {
            selector: 'node:selected',
            style: {
              'border-width': 3,
              'border-color': '#38bdf8',
              'background-color': '#0284c7',
            },
          },
          {
            selector: 'edge',
            style: {
              width: (ele) => {
                const score = ele.data('combined_score');
                return score ? Math.max(1.5, score * 5) : 1.5;
              },
              'line-color': (ele) => {
                const type = ele.data('type');
                if (type === 'correlated') return '#38bdf8';
                if (type === 'uses') return '#10b981';
                return '#475569';
              },
              'line-style': (ele) => (ele.data('type') === 'correlated' ? 'solid' : 'dashed'),
              'curve-style': 'bezier',
              opacity: 0.8,
              label: (ele) => (ele.data('type') === 'correlated' ? (ele.data('level') || '') : ''),
              'font-size': '10px',
              'font-family': 'monospace',
              'text-rotation': 'autorotate',
              'text-margin-y': -8,
              color: '#94a3b8',
            },
          },
          {
            selector: 'edge:selected',
            style: {
              width: 4,
              'line-color': '#f59e0b',
              opacity: 1,
            },
          },
        ],
        layout: {
          name: selectedLayout,
          animate: false,
          padding: 30,
        },
      });

      // Event listeners
      cy.on('tap', 'node', (evt) => {
        const node = evt.target;
        setSelectedElement({ kind: 'node', data: node.data() });
      });

      cy.on('tap', 'edge', (evt) => {
        const edge = evt.target;
        setSelectedElement({ kind: 'edge', data: edge.data() });
      });

      cy.on('tap', (evt) => {
        if (evt.target === cy) {
          setSelectedElement(null);
        }
      });

      cyRef.current = cy;
    } catch (cyErr) {
      console.warn('Cytoscape layout failed to initialize (jsdom or render error):', cyErr);
    }

    return () => {
      if (cyRef.current) {
        cyRef.current.destroy();
        cyRef.current = null;
      }
    };
  }, [graphData, enabledTypes, selectedLayout, showTableMode]);

  const handleFit = () => {
    if (cyRef.current) {
      cyRef.current.fit(undefined, 30);
    }
  };

  const handleToggleType = (type) => {
    setEnabledTypes((prev) => ({ ...prev, [type]: !prev[type] }));
  };

  if (loading) {
    return (
      <div className="py-20 flex flex-col items-center justify-center gap-3">
        <Spinner size="md" />
        <span className="text-xs text-slate-400 font-mono">Generating topological evidence graph...</span>
      </div>
    );
  }

  if (error) {
    return (
      <Card className="p-6">
        <EmptyState
          title="Graph Generation Failed"
          message={error}
          action={
            <Button variant="secondary" size="sm" onClick={loadGraph}>
              Retry
            </Button>
          }
        />
      </Card>
    );
  }

  if (!runId) {
    return (
      <Card className="p-8">
        <EmptyState
          title="No Correlation Graph Available"
          message="Execute the correlation pipeline to generate an interactive topological graph of personas and shared indicators."
          action={
            onTriggerRun ? (
              <Button variant="primary" size="sm" onClick={onTriggerRun}>
                Run Correlation
              </Button>
            ) : null
          }
        />
      </Card>
    );
  }

  const nodes = graphData?.nodes || [];
  const edges = graphData?.edges || [];

  if (nodes.length === 0) {
    return (
      <Card className="p-8">
        <EmptyState
          title="No Graph Nodes Available"
          message="No threat personas or shared infrastructure were found. Ensure that data has been ingested and the correlation pipeline has completed."
          action={
            onTriggerRun ? (
              <Button variant="primary" size="sm" onClick={onTriggerRun}>
                Run Correlation
              </Button>
            ) : null
          }
        />
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Truncation Notice */}
      {graphData?.truncated && (
        <div className="p-3 rounded-lg border border-amber-800/80 bg-amber-950/30 text-amber-300 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-bold">⚠ Display Capped:</span>
            <span>
              Graph node limit (250) reached. Showing highest-scoring personas and their shared indicators. Increase min-score to focus on denser links.
            </span>
          </div>
        </div>
      )}

      {/* Control Bar */}
      <div className="p-3.5 rounded-lg border border-slate-800 bg-slate-900/60 flex flex-wrap items-center justify-between gap-4 text-xs">
        <div className="flex flex-wrap items-center gap-4">
          {/* Min Score Slider */}
          <div className="flex items-center gap-2">
            <label htmlFor="min-score-input" className="text-slate-400 font-medium">
              Min Score:
            </label>
            <input
              id="min-score-input"
              type="range"
              min="0.1"
              max="1.0"
              step="0.05"
              value={minScore}
              onChange={(e) => setMinScore(parseFloat(e.target.value))}
              className="w-24 accent-sky-500 cursor-pointer"
            />
            <span className="font-mono text-slate-200 font-semibold">{minScore.toFixed(2)}</span>
          </div>

          {/* Node Type Toggles */}
          <div className="flex flex-wrap items-center gap-2 border-l border-slate-800 pl-4">
            <span className="text-slate-400 font-medium mr-1">Nodes:</span>
            {Object.keys(enabledTypes).map((type) => (
              <label key={type} className="flex items-center gap-1.5 cursor-pointer text-slate-300 select-none">
                <input
                  type="checkbox"
                  checked={enabledTypes[type]}
                  onChange={() => handleToggleType(type)}
                  className="rounded border-slate-700 bg-slate-800 text-sky-500 focus:ring-0"
                />
                <span className="capitalize text-[11px] flex items-center gap-1">
                  <span
                    className="w-2 h-2 rounded-full inline-block"
                    style={{ backgroundColor: NODE_COLORS[type] }}
                  />
                  {type}
                </span>
              </label>
            ))}
          </div>

          {/* Layout Selector */}
          <div className="flex items-center gap-2 border-l border-slate-800 pl-4">
            <label htmlFor="layout-select" className="text-slate-400 font-medium">
              Layout:
            </label>
            <select
              id="layout-select"
              value={selectedLayout}
              onChange={(e) => setSelectedLayout(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-slate-200 rounded px-2 py-1 text-xs focus:outline-none"
            >
              <option value="cose">Force (Cose)</option>
              <option value="circle">Circle</option>
              <option value="grid">Grid</option>
            </select>
          </div>
        </div>

        {/* View Actions */}
        <div className="flex items-center gap-2">
          {!showTableMode && (
            <Button variant="secondary" size="sm" onClick={handleFit}>
              Fit View
            </Button>
          )}
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setShowTableMode(!showTableMode)}
          >
            {showTableMode ? 'Show Graph Canvas' : 'Show as Table'}
          </Button>
        </div>
      </div>

      {/* Main Workspace Display */}
      {showTableMode ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card className="p-4 overflow-hidden border-slate-800">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 mb-3">
              Graph Nodes ({nodes.length})
            </h3>
            <div className="max-h-96 overflow-y-auto">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-900 text-slate-400 uppercase text-[10px]">
                  <tr>
                    <th scope="col" className="p-2">Type</th>
                    <th scope="col" className="p-2">Label</th>
                    <th scope="col" className="p-2">Context</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {nodes.map((n) => (
                    <tr key={n.data.id} className="hover:bg-slate-800/40">
                      <td className="p-2">
                        <Badge variant="outline">{n.data.type}</Badge>
                      </td>
                      <td className="p-2 font-mono text-slate-200">{n.data.label}</td>
                      <td className="p-2 text-slate-400 text-[11px]">
                        {n.data.type === 'persona'
                          ? `${n.data.marketplace} (${n.data.post_count} posts)`
                          : `Used by ${n.data.persona_count || 0} personas`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card className="p-4 overflow-hidden border-slate-800">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 mb-3">
              Graph Edges ({edges.length})
            </h3>
            <div className="max-h-96 overflow-y-auto">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-900 text-slate-400 uppercase text-[10px]">
                  <tr>
                    <th scope="col" className="p-2">Type</th>
                    <th scope="col" className="p-2">Source</th>
                    <th scope="col" className="p-2">Target</th>
                    <th scope="col" className="p-2">Score</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {edges.map((e) => (
                    <tr key={e.data.id} className="hover:bg-slate-800/40">
                      <td className="p-2">
                        <Badge variant="outline">{e.data.type}</Badge>
                      </td>
                      <td className="p-2 font-mono">{e.data.source}</td>
                      <td className="p-2 font-mono">{e.data.target}</td>
                      <td className="p-2 font-mono">
                        {e.data.combined_score ? e.data.combined_score.toFixed(2) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="flex items-center justify-between px-1">
            <p className="text-xs text-slate-400 font-mono">
              Drag nodes to explore. Click a node or edge for evidence.
            </p>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
            {/* Cytoscape Canvas */}
            <div className="lg:col-span-3 rounded-lg border border-slate-800 bg-slate-950/80 relative min-h-[520px] overflow-hidden">
              <div
                ref={containerRef}
                data-testid="cytoscape-container"
                className="w-full h-full min-h-[520px]"
              />
              {/* Watermark/legend */}
              <div className="absolute bottom-3 left-3 px-2.5 py-1.5 rounded bg-slate-900/90 border border-slate-800 text-[10px] text-slate-400 space-y-1 backdrop-blur-xs select-none">
                <div className="font-semibold text-slate-300 uppercase tracking-wider">Topology Legend</div>
                <div className="flex items-center gap-3">
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-sky-500" /> Persona
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-xs bg-slate-400" /> Marketplace
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-amber-500" /> PGP Key
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-emerald-500" /> Wallet
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-purple-500" /> Infra
                  </span>
                </div>
              </div>
            </div>

            {/* Inspection Inspector / Side Panel */}
          <Card className="p-4 border-slate-800 flex flex-col justify-between">
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200 border-b border-slate-800 pb-2 mb-3">
                Topology Inspector
              </h3>

              {!selectedElement ? (
                <div className="py-12 text-center text-xs text-slate-500">
                  Click any node or link in the graph to inspect structural evidence.
                </div>
              ) : selectedElement.kind === 'node' ? (
                <div className="space-y-3 text-xs">
                  <div>
                    <span className="text-[10px] uppercase font-semibold text-slate-400">Node Type</span>
                    <div className="mt-1">
                      <Badge variant="outline">{selectedElement.data.type}</Badge>
                    </div>
                  </div>

                  <div>
                    <span className="text-[10px] uppercase font-semibold text-slate-400">Identifier / Label</span>
                    <div className="mt-1 font-mono text-slate-200 font-semibold break-all">
                      {selectedElement.data.full_value || selectedElement.data.label}
                    </div>
                  </div>

                  {selectedElement.data.type === 'persona' && (
                    <>
                      <div>
                        <span className="text-[10px] uppercase font-semibold text-slate-400">Marketplace</span>
                        <div className="mt-1 text-slate-300">{selectedElement.data.marketplace}</div>
                      </div>
                      <div>
                        <span className="text-[10px] uppercase font-semibold text-slate-400">Observed Posts</span>
                        <div className="mt-1 font-mono text-slate-300">{selectedElement.data.post_count}</div>
                      </div>
                      {selectedElement.data.actor_id && (
                        <div className="pt-2">
                          <Link
                            to={`/investigations/${investigationId}/actors/${selectedElement.data.actor_id}`}
                          >
                            <Button variant="primary" size="sm" className="w-full">
                              View Actor Profile &rarr;
                            </Button>
                          </Link>
                        </div>
                      )}
                    </>
                  )}

                  {selectedElement.data.type !== 'persona' && selectedElement.data.persona_count && (
                    <div>
                      <span className="text-[10px] uppercase font-semibold text-slate-400">Shared By</span>
                      <div className="mt-1 text-slate-300 font-mono">
                        {selectedElement.data.persona_count} threat personas
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-3 text-xs">
                  <div>
                    <span className="text-[10px] uppercase font-semibold text-slate-400">Edge Type</span>
                    <div className="mt-1">
                      <Badge variant="outline">{selectedElement.data.type}</Badge>
                    </div>
                  </div>

                  {selectedElement.data.type === 'correlated' ? (
                    <>
                      <div>
                        <span className="text-[10px] uppercase font-semibold text-slate-400">
                          Heuristic Score
                        </span>
                        <div className="mt-1 text-base font-bold font-mono text-sky-400">
                          {(selectedElement.data.combined_score || 0).toFixed(4)}
                        </div>
                      </div>

                      <div>
                        <span className="text-[10px] uppercase font-semibold text-slate-400">Confidence Level</span>
                        <div className="mt-1">
                          <Badge variant="success">
                            {selectedElement.data.level?.toUpperCase() || 'NONE'}
                          </Badge>
                        </div>
                      </div>

                      {selectedElement.data.contradiction_count > 0 && (
                        <div>
                          <span className="text-[10px] uppercase font-semibold text-rose-400">
                            Contradictions
                          </span>
                          <div className="mt-1 text-rose-300 font-semibold">
                            {selectedElement.data.contradiction_count} identified
                          </div>
                        </div>
                      )}
                    </>
                  ) : (
                    <div>
                      <span className="text-[10px] uppercase font-semibold text-slate-400">Relation</span>
                      <div className="mt-1 font-mono text-slate-300 break-all text-[11px]">
                        {selectedElement.data.source} &rarr; {selectedElement.data.target}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="pt-3 border-t border-slate-800 text-[10px] text-slate-500">
              DARKTRACE Heuristic Correlation Graph
            </div>
          </Card>
        </div>
      </div>
    )}
  </div>
);
}

