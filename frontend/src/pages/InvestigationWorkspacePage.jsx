import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import PageHeader from '../components/ui/PageHeader';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import Button from '../components/ui/Button';
import Spinner from '../components/ui/Spinner';
import EmptyState from '../components/ui/EmptyState';
import ErrorState from '../components/ui/ErrorState';
import StageStatusCards from '../components/investigations/StageStatusCards';
import OverviewTab from '../components/investigations/tabs/OverviewTab';
import EvidenceGraphTab from '../components/investigations/tabs/EvidenceGraphTab';
import ChronologyTab from '../components/investigations/tabs/ChronologyTab';
import InfrastructureTab from '../components/investigations/tabs/InfrastructureTab';
import BehaviourTab from '../components/investigations/tabs/BehaviourTab';
import StylometryTab from '../components/investigations/tabs/StylometryTab';
import DossierTab from '../components/investigations/tabs/DossierTab';
import { useToast } from '../components/ui/Toast';
import {
  fetchInvestigationById,
  fetchInvestigationDatasets,
  fetchPipelineStages,
  fetchPipelineRuns,
  fetchPipelineRunDetail,
  triggerPipelineRun,
} from '../lib/api';

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'graph', label: 'Evidence Graph' },
  { id: 'chronology', label: 'Chronology' },
  { id: 'infrastructure', label: 'Infrastructure' },
  { id: 'behaviour', label: 'Behaviour' },
  { id: 'stylometry', label: 'Stylometry' },
  { id: 'dossier', label: 'Dossier' },
];

export default function InvestigationWorkspacePage() {
  const { id } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = searchParams.get('tab') || 'overview';

  const toast = useToast();
  const [investigation, setInvestigation] = useState(null);
  const [datasets, setDatasets] = useState([]);
  const [stages, setStages] = useState([]);
  const [runs, setRuns] = useState([]);
  const [activeRun, setActiveRun] = useState(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [triggeringRun, setTriggeringRun] = useState(false);

  const pollIntervalRef = useRef(null);

  const setTab = (tabId) => {
    setSearchParams({ tab: tabId });
  };

  const loadCaseData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [invData, datasetsData, stagesData, runsData] = await Promise.all([
        fetchInvestigationById(id),
        fetchInvestigationDatasets(id),
        fetchPipelineStages().catch(() => []),
        fetchPipelineRuns(id).catch(() => []),
      ]);

      setInvestigation(invData);
      setDatasets(datasetsData || []);
      setStages(stagesData || []);
      setRuns(runsData || []);

      if (runsData && runsData.length > 0) {
        setActiveRun(runsData[0]);
      }
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadCaseData();
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [loadCaseData]);

  // Polling for active run status
  useEffect(() => {
    if (activeRun && (activeRun.status === 'queued' || activeRun.status === 'running')) {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

      pollIntervalRef.current = setInterval(async () => {
        try {
          const updated = await fetchPipelineRunDetail(id, activeRun.id);
          setActiveRun(updated);

          if (updated.status === 'completed') {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
            toast.success(`Correlation run #${updated.id} completed successfully.`);
            const refreshedRuns = await fetchPipelineRuns(id);
            setRuns(refreshedRuns || []);
          } else if (updated.status === 'failed') {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
            toast.error(`Correlation run #${updated.id} failed.`);
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
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [activeRun?.status, activeRun?.id, id, toast]);

  const handleRunCorrelation = async () => {
    setTriggeringRun(true);
    try {
      const newRun = await triggerPipelineRun(id);
      setActiveRun(newRun);
      setRuns((prev) => [newRun, ...prev]);
      toast.success(`Correlation pipeline run #${newRun.id} initiated.`);
    } catch (err) {
      toast.error(err.message || 'Failed to start correlation run.');
    } finally {
      setTriggeringRun(false);
    }
  };

  if (loading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center gap-3">
        <Spinner size="lg" />
        <p className="text-xs text-slate-400 font-mono">Loading investigation workspace #{id}...</p>
      </div>
    );
  }

  if (error) {
    if (error.status === 404 || error.code === 'NOT_FOUND') {
      return (
        <div className="py-12 space-y-4">
          <Link to="/investigations" className="text-xs text-sky-400 hover:text-sky-300 font-medium">
            &larr; Back to Investigations
          </Link>
          <EmptyState
            title="Investigation Not Found"
            message={`The requested investigation #${id} does not exist or you do not have permission to access it.`}
            action={
              <Link to="/investigations">
                <Button variant="secondary" size="sm">
                  View My Investigations
                </Button>
              </Link>
            }
          />
        </div>
      );
    }

    return (
      <div className="py-12 space-y-4">
        <Link to="/investigations" className="text-xs text-sky-400 hover:text-sky-300 font-medium">
          &larr; Back to Investigations
        </Link>
        <ErrorState
          title="Failed to Load Investigation"
          message={error.message || 'Unable to retrieve case workspace.'}
          details={error.details}
          onRetry={loadCaseData}
        />
      </div>
    );
  }

  if (!investigation) return null;

  const isRunActive = activeRun && (activeRun.status === 'queued' || activeRun.status === 'running');

  return (
    <div className="space-y-6">
      {/* Navigation Breadcrumb & Actions */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          to="/investigations"
          className="text-xs text-sky-400 hover:text-sky-300 font-medium inline-flex items-center gap-1"
        >
          &larr; Back to Investigations
        </Link>

        <div className="flex items-center gap-2.5">
          <Link to={`/investigations/${id}/collect`}>
            <Button variant="secondary" size="sm">
              + Add Data
            </Button>
          </Link>
          <Button
            variant="primary"
            size="sm"
            loading={triggeringRun || isRunActive}
            onClick={handleRunCorrelation}
          >
            {isRunActive ? 'Correlating...' : 'Run Correlation'}
          </Button>
        </div>
      </div>

      {/* Case Header */}
      <PageHeader
        title={investigation.title}
        description={investigation.description || 'No description provided.'}
        action={<Badge variant={investigation.status}>{investigation.status}</Badge>}
      />

      {/* Metric Overview Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card className="p-3.5 border-slate-800">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block">
            Owner
          </span>
          <div className="mt-1 font-mono text-xs font-semibold text-slate-200 truncate">
            {investigation.created_by?.username || 'Investigator'}
          </div>
        </Card>

        <Card className="p-3.5 border-slate-800">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block">
            Collected Posts
          </span>
          <div className="mt-1 font-mono text-base font-bold text-slate-100">
            {investigation.counts?.posts?.toLocaleString() || 0}
          </div>
        </Card>

        <Card className="p-3.5 border-slate-800">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block">
            Extracted Indicators
          </span>
          <div className="mt-1 font-mono text-base font-bold text-slate-100">
            {investigation.counts?.indicators?.toLocaleString() || 0}
          </div>
        </Card>

        <Card className="p-3.5 border-slate-800">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 block">
            Latest Pipeline Run
          </span>
          <div className="mt-1">
            {activeRun ? (
              <Badge variant={activeRun.status === 'completed' ? 'success' : isRunActive ? 'warning' : 'neutral'}>
                {activeRun.status?.toUpperCase()} (#{activeRun.id})
              </Badge>
            ) : (
              <span className="text-xs text-slate-500">No runs yet</span>
            )}
          </div>
        </Card>
      </div>

      {/* Pipeline Stage Execution Status (if run exists) */}
      {activeRun && stages.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold uppercase tracking-wider text-slate-400">
              Pipeline Stages
            </span>
            <span className="font-mono text-slate-500">Run #{activeRun.id}</span>
          </div>
          <StageStatusCards registryStages={stages} currentRun={activeRun} />
        </div>
      )}

      {/* 7 Workspace Tabs Bar */}
      <div className="border-b border-slate-800">
        <nav className="flex space-x-1 sm:space-x-2 overflow-x-auto pb-1" aria-label="Investigation tabs">
          {TABS.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setTab(tab.id)}
                className={`px-3.5 py-2 text-xs font-semibold rounded-md transition-colors cursor-pointer whitespace-nowrap flex items-center gap-1.5 ${
                  isActive
                    ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40 shadow-xs'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Viewport */}
      <div className="pt-2">
        {activeTab === 'overview' && (
          <OverviewTab
            investigationId={id}
            runId={activeRun?.id}
            onTriggerRun={handleRunCorrelation}
          />
        )}

        {activeTab === 'graph' && (
          <EvidenceGraphTab
            investigationId={id}
            runId={activeRun?.id}
          />
        )}

        {activeTab === 'chronology' && (
          <ChronologyTab
            investigationId={id}
            runId={activeRun?.id}
          />
        )}

        {activeTab === 'infrastructure' && (
          <InfrastructureTab
            investigationId={id}
            runId={activeRun?.id}
          />
        )}

        {activeTab === 'behaviour' && (
          <BehaviourTab
            investigationId={id}
            runId={activeRun?.id}
          />
        )}

        {activeTab === 'stylometry' && (
          <StylometryTab
            investigationId={id}
            runId={activeRun?.id}
          />
        )}

        {activeTab === 'dossier' && (
          <DossierTab
            investigationId={id}
            runId={activeRun?.id}
          />
        )}
      </div>
    </div>
  );
}

