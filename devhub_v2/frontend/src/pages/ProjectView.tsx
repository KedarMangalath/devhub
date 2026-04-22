import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Check, ChevronDown, ChevronRight, Code2, FileCode, Loader2, PanelLeftClose, PanelLeftOpen, PencilLine, Play, Plus, Sparkles, X, XCircle, Trash2 } from 'lucide-react';

import BlueprintPanel from '../components/BlueprintPanel';
import CodeWorkspace from '../components/CodeWorkspace';
import GitHubPanel from '../components/GitHubPanel';
import MermaidDiagram from '../components/MermaidDiagram';
import OnboardingPanel from '../components/OnboardingPanel';
import ProjectChatPanel from '../components/ProjectChatPanel';
import ToastStack from '../components/ToastStack';

const API = 'http://localhost:8000/api';
const PIPELINE_STAGES = ['backlog', 'development', 'testing', 'code_review', 'staging'];
const IMPLEMENTATION_ACTIONS = ['implementation_started', 'implementation_completed', 'implementation_failed'];

/** Strip pushd/popd wrapper from a run command for cleaner display. */
function cleanRunCommand(cmd: string | null | undefined): string {
  if (!cmd) return 'Not detected';
  // pushd "dir" && actual_command && popd  →  actual_command (in dir/)
  const pushd = cmd.match(/^pushd\s+"([^"]+)"\s+&&\s+(.+?)\s+&&\s+popd$/i);
  if (pushd) {
    return `${pushd[2]}  (in ${pushd[1]}/)`.trim();
  }
  // cd dir && actual_command  →  actual_command (in dir/)
  const cd = cmd.match(/^cd\s+(\S+)\s+&&\s+(.+)$/i);
  if (cd) {
    return `${cd[2]}  (in ${cd[1]}/)`.trim();
  }
  return cmd;
}

function getImplementationHistory(feature: any) {
  const history = Array.isArray(feature?.pipeline_history) ? feature.pipeline_history : [];
  return history.filter((item: any) => IMPLEMENTATION_ACTIONS.includes(item.action));
}

export default function ProjectView() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('overview');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [workspaceFullscreen, setWorkspaceFullscreen] = useState(false);
  const [workspaceMounted, setWorkspaceMounted] = useState(false);
  const [workspaceRuntimeRunning, setWorkspaceRuntimeRunning] = useState(false);
  const [showLeaveRuntimeModal, setShowLeaveRuntimeModal] = useState(false);
  const [stoppingForLeave, setStoppingForLeave] = useState(false);
  const [workItemsView, setWorkItemsView] = useState<'list' | 'board'>('list');
  const [project, setProject] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [features, setFeatures] = useState<any[]>([]);
  const [showAddFeature, setShowAddFeature] = useState(false);
  const [featureForm, setFeatureForm] = useState({ title: '', description: '' });
  const [creatingFeature, setCreatingFeature] = useState(false);
  const [actionLoading, setActionLoading] = useState('');
  const [actionFeedback, setActionFeedback] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [agentRunning, setAgentRunning] = useState(false);
  const [blueprintRunTarget, setBlueprintRunTarget] = useState<string | null>(null);
  const [agentResult, setAgentResult] = useState<any>(null);
  const [deepDocsProgress, setDeepDocsProgress] = useState<{ pct: number; section: string; completed: number; total: number } | null>(null);
  const [documentationRunning, setDocumentationRunning] = useState(false);
  const [expandedFeature, setExpandedFeature] = useState<string | null>(null);
  const [expandedPipelineFeature, setExpandedPipelineFeature] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showProjectSettings, setShowProjectSettings] = useState(false);
  const [savingProject, setSavingProject] = useState(false);
  const [projectForm, setProjectForm] = useState({ name: '', description: '', github_url: '', tech_stack: '' });
  const [implementationRun, setImplementationRun] = useState<{ featureId: string; featureTitle: string; baselineCount: number; startedSeen: boolean } | null>(null);
  const [implementationProgress, setImplementationProgress] = useState(0);
  const [completionPrompt, setCompletionPrompt] = useState<{ type: 'success' | 'error'; title: string; text: string } | null>(null);
  const [agentEvents, setAgentEvents] = useState<any[]>([]);
  const implementationPollRef = useRef<number | null>(null);
  const implementationProgressRef = useRef<number | null>(null);
  const deepDocsPollRef = useRef<number | null>(null);
  const contextInitPollRef = useRef<number | null>(null);
  const initialTabAppliedRef = useRef(false);
  const contentScrollRef = useRef<HTMLDivElement | null>(null);

  const tabs = [
    { id: 'overview', label: 'Overview', icon: 'OV', helper: 'Project health and next steps' },
    { id: 'onboarding', label: 'Onboarding', icon: 'ON', helper: 'Understand this codebase first' },
    { id: 'blueprint', label: 'Blueprint', icon: 'BP', helper: 'Deep architecture wiki' },
    { id: 'work_items', label: 'Work Items', icon: 'WI', helper: 'List and board for the same work' },
    { id: 'github', label: 'GitHub', icon: 'GH', helper: 'Issues, PRs, and repo sync' },
    { id: 'chat', label: 'Chat', icon: 'CH', helper: 'Project-level AI assistant' },
    { id: 'code', label: 'Workspace', icon: 'WS', helper: 'Code, preview, and AI edits' },
  ];

  const fetchProject = () => {
    fetch(`${API}/projects/${id}/`, { cache: 'no-store' })
      .then((r) => r.json())
      .then((data) => {
        if (!data.error) {
          setProject(data);
          setFeatures(data.features || []);
          setProjectForm({
            name: data.name || '',
            description: data.description || '',
            github_url: data.github_url || '',
            tech_stack: Array.isArray(data.tech_stack) ? data.tech_stack.join(', ') : '',
          });
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => { fetchProject(); }, [id]);

  useEffect(() => {
    initialTabAppliedRef.current = false;
  }, [id]);

  useEffect(() => {
    if (!project || initialTabAppliedRef.current) return;
    const recommended = project.recommended_start_tab || 'overview';
    setActiveTab(recommended);
    initialTabAppliedRef.current = true;
  }, [project]);

  useEffect(() => {
    if (activeTab === 'code') {
      setWorkspaceMounted(true);
    }
  }, [activeTab]);

  useEffect(() => {
    if (!project?.workspace_id) {
      setWorkspaceRuntimeRunning(false);
      return;
    }

    let cancelled = false;
    fetch(`${API}/workspace/${project.workspace_id}/runtime/`)
      .then((response) => response.json())
      .then((data) => {
        if (!cancelled) {
          const running = Boolean(data?.status?.running);
          setWorkspaceRuntimeRunning(running);
          if (running) {
            setWorkspaceMounted(true);
          }
        }
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [project?.workspace_id]);

  useEffect(() => {
    if (!workspaceRuntimeRunning) return undefined;

    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [workspaceRuntimeRunning]);

  useEffect(() => {
    if (!workspaceRuntimeRunning || !id) return undefined;

    const projectPath = `/project/${id}`;
    window.history.replaceState({ devhubProjectGuard: true }, '', window.location.href);
    window.history.pushState({ devhubProjectGuard: true }, '', window.location.href);

    const handlePopState = () => {
      if (window.location.pathname === projectPath) return;
      window.history.pushState({ devhubProjectGuard: true }, '', projectPath);
      setShowLeaveRuntimeModal(true);
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [workspaceRuntimeRunning, id]);

  useEffect(() => {
    if (contentScrollRef.current) {
      contentScrollRef.current.scrollTop = 0;
    }
  }, [activeTab, project?.id]);

  useEffect(() => {
    if (activeTab === 'docs') {
      setActiveTab('blueprint');
    }
  }, [activeTab]);

  useEffect(() => {
    const stored = window.localStorage.getItem('devhub.project.sidebar.collapsed');
    setSidebarCollapsed(stored === '1');
  }, []);

  useEffect(() => {
    window.localStorage.setItem('devhub.project.sidebar.collapsed', sidebarCollapsed ? '1' : '0');
  }, [sidebarCollapsed]);

  useEffect(() => {
    if (activeTab !== 'code') {
      setWorkspaceFullscreen(false);
    }
  }, [activeTab]);

  useEffect(() => {
    if (!workspaceFullscreen) return undefined;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setWorkspaceFullscreen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [workspaceFullscreen]);

  useEffect(() => {
    return () => {
      if (implementationPollRef.current) window.clearInterval(implementationPollRef.current);
      if (implementationProgressRef.current) window.clearInterval(implementationProgressRef.current);
      if (deepDocsPollRef.current) window.clearInterval(deepDocsPollRef.current);
      if (contextInitPollRef.current) window.clearInterval(contextInitPollRef.current);
    };
  }, []);

  const applyDeepDocsProgressEvent = (event: any) => {
    if (!event || event.status === 'idle') return;
    const sectionLabels: Record<string, string> = {
      design_doc: 'Design Doc',
      overview: 'Overview',
      repository: 'Repository',
      build_context: 'Preparing codebase context',
      services: 'Services & Components',
      api: 'API Reference',
      database: 'Database Schema',
      workflows: 'Workflows & Sequences',
      setup: 'Setup & Environment',
      quality: 'Quality & Security',
      knowledge: 'Knowledge Base',
      complete: 'Blueprint complete',
    };

    if (event.status === 'done') {
      setDeepDocsProgress(null);
      return;
    }

    if (event.status === 'failed') {
      setAgentResult({ error: event.error || 'Deep documentation generation failed.' });
      setDeepDocsProgress(null);
      if (deepDocsPollRef.current) {
        window.clearInterval(deepDocsPollRef.current);
        deepDocsPollRef.current = null;
      }
      return;
    }

    setDeepDocsProgress({
      pct: event.progress_pct || 0,
      section: event.section_label || sectionLabels[event.section_key] || event.section_key || 'Generating...',
      completed: event.completed_sections || 0,
      total: event.total_sections || 7,
    });
  };

  useEffect(() => {
    if (!implementationRun) {
      if (implementationPollRef.current) window.clearInterval(implementationPollRef.current);
      if (implementationProgressRef.current) window.clearInterval(implementationProgressRef.current);
      implementationPollRef.current = null;
      implementationProgressRef.current = null;
      return;
    }

    implementationPollRef.current = window.setInterval(() => {
      fetchProject();
    }, 2500);

    implementationProgressRef.current = window.setInterval(() => {
      setImplementationProgress((current) => {
        if (current >= 92) return current;
        if (current < 36) return current + 8;
        if (current < 68) return current + 4;
        return current + 2;
      });
    }, 700);

    return () => {
      if (implementationPollRef.current) window.clearInterval(implementationPollRef.current);
      if (implementationProgressRef.current) window.clearInterval(implementationProgressRef.current);
      implementationPollRef.current = null;
      implementationProgressRef.current = null;
    };
  }, [implementationRun]);

  useEffect(() => {
    if (!project?.context_initializing) {
      if (contextInitPollRef.current) window.clearInterval(contextInitPollRef.current);
      contextInitPollRef.current = null;
      return;
    }

    if (contextInitPollRef.current) window.clearInterval(contextInitPollRef.current);
    contextInitPollRef.current = window.setInterval(() => {
      fetchProject();
    }, 2500);

    return () => {
      if (contextInitPollRef.current) window.clearInterval(contextInitPollRef.current);
      contextInitPollRef.current = null;
    };
  }, [project?.context_initializing, id]);

  useEffect(() => {
    if (!agentResult) return undefined;
    const timeout = window.setTimeout(() => setAgentResult(null), agentResult.error ? 2600 : 1800);
    return () => window.clearTimeout(timeout);
  }, [agentResult]);

  useEffect(() => {
    if (!actionFeedback) return undefined;
    const timeout = window.setTimeout(() => setActionFeedback(null), actionFeedback.type === 'error' ? 2600 : 1800);
    return () => window.clearTimeout(timeout);
  }, [actionFeedback]);

  useEffect(() => {
    if (!implementationRun) return;
    const targetFeature = features.find((feature: any) => feature.id === implementationRun.featureId);
    if (!targetFeature) return;

    const implementationHistory = getImplementationHistory(targetFeature);
    if (implementationHistory.length <= implementationRun.baselineCount) return;

    const latest = implementationHistory[implementationHistory.length - 1];
    if (!latest) return;

    if (latest.action === 'implementation_started' && !implementationRun.startedSeen) {
      setImplementationRun((current) => current ? { ...current, startedSeen: true } : current);
      setImplementationProgress((current) => Math.max(current, 24));
      return;
    }

    if (latest.action === 'implementation_completed') {
      setImplementationProgress(100);
      setImplementationRun(null);
      setActionFeedback({ type: 'success', text: `${implementationRun.featureTitle} implementation completed.` });
      setCompletionPrompt({
        type: 'success',
        title: 'Implementation Complete',
        text: latest.comment || `${implementationRun.featureTitle} has been implemented and the workspace is ready to review.`,
      });
      fetchProject();
      return;
    }

    if (latest.action === 'implementation_failed') {
      setImplementationRun(null);
      setActionFeedback({ type: 'error', text: `${implementationRun.featureTitle} implementation failed.` });
      setCompletionPrompt({
        type: 'error',
        title: 'Implementation Failed',
        text: latest.comment || `The implementation for ${implementationRun.featureTitle} did not finish successfully.`,
      });
      fetchProject();
    }
  }, [features, implementationRun]);

  const createFeature = async () => {
    if (!featureForm.title.trim() || creatingFeature) return;
    setCreatingFeature(true);
    await fetch(`${API}/projects/${id}/features/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(featureForm) });
    setFeatureForm({ title: '', description: '' });
    setShowAddFeature(false);
    setCreatingFeature(false);
    fetchProject();
  };

  const pipelineAction = async (featureId: string, action: string) => {
    setActionLoading(featureId + action);
    setActionFeedback(null);
    try {
      const targetFeature = features.find((feature: any) => feature.id === featureId);
      const response = await fetch(`${API}/projects/${id}/pipeline/action/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ feature_id: featureId, action }),
      });
      const data = await response.json();

      if (!response.ok) {
        setActionFeedback({ type: 'error', text: data.error || 'Action failed.' });
        return;
      }

      setActionFeedback({ type: 'success', text: data.message || `Action "${action}" completed.` });
      if (action === 'implement' && targetFeature) {
        setImplementationRun({
          featureId,
          featureTitle: targetFeature.title,
          baselineCount: getImplementationHistory(targetFeature).length,
          startedSeen: false,
        });
        setImplementationProgress(12);
      }
      fetchProject();
    } catch {
      setActionFeedback({ type: 'error', text: 'Action failed because the server could not be reached.' });
    } finally {
      setActionLoading('');
    }
  };

  const startAgent = async (sectionKey?: string) => {
    if (agentRunning) return;
    const requestedSection = sectionKey?.trim() || '';
    const sectionLabels: Record<string, string> = {
      design_doc: 'Design Doc',
      overview: 'Overview',
      repository: 'Repository',
      services: 'Services',
      api: 'API',
      database: 'Database',
      workflows: 'Workflows',
      setup: 'Setup',
      quality: 'Quality',
      knowledge: 'Knowledge',
    };
    setAgentRunning(true);
    setBlueprintRunTarget(requestedSection || '__all__');
    setAgentResult(null);
    setAgentEvents([]);
    setDeepDocsProgress({
      pct: 0,
      section: requestedSection ? `Preparing ${sectionLabels[requestedSection] || requestedSection}` : 'Initializing...',
      completed: 0,
      total: requestedSection ? 1 : 7,
    });
    try {
      const pollProgress = async () => {
        try {
          const progressResponse = await fetch(`${API}/projects/${id}/agent/deep-docs/progress/`);
          if (!progressResponse.ok) return;
          const progressData = await progressResponse.json();
          applyDeepDocsProgressEvent(progressData);
        } catch {
          // keep stream as the primary channel; polling is a fallback
        }
      };

      if (deepDocsPollRef.current) window.clearInterval(deepDocsPollRef.current);
      void pollProgress();
      deepDocsPollRef.current = window.setInterval(() => {
        void pollProgress();
      }, 1000);

      const response = await fetch(`${API}/projects/${id}/agent/deep-docs/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestedSection ? { section_key: requestedSection } : {}),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({ error: 'Unknown error' }));
        setAgentResult({ error: errData.error || 'Deep documentation generation failed.' });
        setDeepDocsProgress(null);
        setAgentRunning(false);
        return;
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let streamFailed = false;

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            try {
              const event = JSON.parse(line.slice(6));
              // Live agent event (streaming during generation, not on section completion)
              if (event.type === 'agent_event' && event.event) {
                setAgentEvents((prev: any[]) => [...prev, event.event]);
                continue;
              }
              if (event.status === 'failed' && event.section_key === 'build_context') {
                streamFailed = true;
                setAgentResult({ error: event.error || 'Deep documentation generation failed.' });
                setDeepDocsProgress(null);
              } else {
                const isStarted = event.status === 'started';
                applyDeepDocsProgressEvent(event);
                if (event.agent_events?.length) {
                  setAgentEvents((prev: any[]) => [...prev, ...event.agent_events]);
                }
                if (!isStarted) {
                  // Update blueprint incrementally only when section data is available.
                  setProject((prev: any) => {
                    if (!prev) return prev;
                    const bp = { ...(prev.blueprint || {}) };
                    const data = event.section_data || {};
                    for (const [key, val] of Object.entries(data)) {
                      if (key !== '_error') bp[key] = val;
                    }
                    return { ...prev, blueprint: bp };
                  });
                }
              }
            } catch (e) {
              // skip malformed events
            }
          }
        }
      }

      if (!streamFailed) {
        setAgentResult({ message: requestedSection ? `${sectionLabels[requestedSection] || requestedSection} regenerated successfully.` : 'Deep documentation generated successfully.' });
        fetchProject();
      }
    } catch {
      setAgentResult({ error: 'Failed to connect to deep documentation endpoint.' });
    } finally {
      if (deepDocsPollRef.current) {
        window.clearInterval(deepDocsPollRef.current);
        deepDocsPollRef.current = null;
      }
      setAgentRunning(false);
      setBlueprintRunTarget(null);
      setDeepDocsProgress(null);
    }
  };

  const generateDocumentation = async () => {
    if (documentationRunning) return;
    setDocumentationRunning(true);
    setActionFeedback(null);
    try {
      const response = await fetch(`${API}/projects/${id}/documentation/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await response.json();
      if (!response.ok) {
        setActionFeedback({ type: 'error', text: data.error || 'Documentation generation failed.' });
        return;
      }
      setActionFeedback({ type: 'success', text: 'Codebase reference generated successfully.' });
      fetchProject();
    } catch {
      setActionFeedback({ type: 'error', text: 'Documentation generation failed because the server could not be reached.' });
    } finally {
      setDocumentationRunning(false);
    }
  };

  const deleteProject = async () => {
    if (!window.confirm('Are you sure you want to delete this project? This will remove all features and sandbox data.')) return;
    setIsDeleting(true);
    try {
      await fetch(`${API}/projects/${id}/delete/`, { method: 'DELETE' });
      navigate('/');
    } catch {
      setIsDeleting(false);
    }
  };

  const stopWorkspaceRuntime = async () => {
    if (!project?.workspace_id) return;
    try {
      const workspaceId = project.workspace_id;
      await Promise.allSettled([
        fetch(`${API}/workspace/${workspaceId}/runtime/`, { method: 'DELETE' }),
        fetch(`${API}/workspace/${workspaceId}/setup/`, { method: 'DELETE' }),
        fetch(`${API}/workspace/${workspaceId}/process/${encodeURIComponent(`${workspaceId}_cmd.exe`)}/`, { method: 'DELETE' }),
      ]);
    } finally {
      setWorkspaceRuntimeRunning(false);
    }
  };

  const leaveProject = async () => {
    if (workspaceRuntimeRunning) {
      setShowLeaveRuntimeModal(true);
      return;
    }
    navigate('/');
  };

  const confirmStopAndLeave = async () => {
    if (stoppingForLeave) return;
    setStoppingForLeave(true);
    try {
      await stopWorkspaceRuntime();
      setShowLeaveRuntimeModal(false);
      navigate('/');
    } finally {
      setStoppingForLeave(false);
    }
  };

  const saveProjectSettings = async () => {
    setSavingProject(true);
    try {
      const response = await fetch(`${API}/projects/${id}/update/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: projectForm.name.trim(),
          description: projectForm.description.trim(),
          github_url: projectForm.github_url.trim(),
          tech_stack: projectForm.tech_stack.split(',').map((item) => item.trim()).filter(Boolean),
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        setActionFeedback({ type: 'error', text: data.error || 'Unable to update project settings.' });
        return;
      }
      setShowProjectSettings(false);
      setActionFeedback({ type: 'success', text: 'Project details updated. Blueprint regeneration has started.' });
      fetchProject();
    } catch {
      setActionFeedback({ type: 'error', text: 'Unable to update project settings.' });
    } finally {
      setSavingProject(false);
    }
  };

  if (loading || isDeleting) {
    return (
      <div className="devhub-loading-screen devhub-project-view flex min-h-[var(--app-vh)] items-center justify-center bg-[#f8f9fa]">
        <div className="devhub-workspace-loader flex flex-col items-center gap-5">
          <div className="devhub-loader-icon-ring">
            <div className="devhub-loader-icon-core">
              <Code2 className="h-6 w-6" />
            </div>
          </div>
          <div className="devhub-loader-text-group">
            <p className="text-sm font-semibold text-slate-700 devhub-loader-title">{isDeleting ? 'Removing project…' : 'Loading workspace…'}</p>
            <p className="text-xs text-slate-400 devhub-loader-sub">Setting up your environment</p>
          </div>
          <div className="devhub-loader-bar-track">
            <div className="devhub-loader-bar-fill" />
          </div>
        </div>
      </div>
    );
  }

  const stageColor = (status: string) => ({
    backlog: 'bg-[#f5f1ec] text-slate-600',
    development: 'bg-[#e8f0ff] text-[#3458a5]',
    testing: 'bg-[#fff2dc] text-[#a56a1f]',
    code_review: 'bg-[#f5ecff] text-[#7f53aa]',
    staging: 'bg-[#e7f6ef] text-[#2f7d5a]',
  }[status] || 'bg-[#f5f1ec] text-slate-600');

  const bp = project?.blueprint;
  const sourceType = project?.source_type || 'starter';
  const onboardingSummary = project?.onboarding_summary || {};
  // In workspace: hide the top header bar only. The sidebar stays (icon-only) so you can navigate back.
  const hideProjectHeader = activeTab === 'code';

  return (
    <div className="devhub-project-view h-[var(--app-vh)] overflow-hidden bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.92),_rgba(244,246,248,0.98)_42%,_#eef1f4_100%)] text-slate-900 font-sans flex flex-col">
      <ToastStack
        items={[
          ...(agentResult
            ? [
                {
                  id: 'agent-result',
                  type: (agentResult.error ? 'error' : 'success') as 'error' | 'success',
                  text: String(agentResult.error || agentResult.message || 'Blueprint refreshed successfully.'),
                },
              ]
            : []),
          ...(actionFeedback
            ? [
                {
                  id: 'action-feedback',
                  type: actionFeedback.type,
                  text: actionFeedback.text,
                },
              ]
            : []),
        ]}
        onDismiss={(toastId) => {
          if (toastId === 'agent-result') setAgentResult(null);
          if (toastId === 'action-feedback') setActionFeedback(null);
        }}
      />
      {showLeaveRuntimeModal && (
        <div className="fixed inset-0 z-[160] flex items-center justify-center bg-black/60 px-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-[28px] border border-slate-200 bg-white p-5 text-slate-900 shadow-[0_34px_90px_rgba(0,0,0,0.28)]">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-[#70434f] text-white shadow-[0_16px_34px_rgba(112,67,79,0.28)]">
                  <Play className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">Running Session</p>
                  <h3 className="mt-1 text-lg font-semibold text-slate-950">Stop project before leaving?</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-600">
                    This workspace is still running. DevHub can stop the preview, terminal session, and setup process before returning to the landing page.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowLeaveRuntimeModal(false)}
                className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-500 transition hover:bg-slate-50 hover:text-slate-900"
                aria-label="Stay in project"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={() => setShowLeaveRuntimeModal(false)}
                disabled={stoppingForLeave}
                className="inline-flex h-10 items-center justify-center rounded-xl border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 disabled:opacity-60"
              >
                Stay here
              </button>
              <button
                type="button"
                onClick={() => { void confirmStopAndLeave(); }}
                disabled={stoppingForLeave}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-[#70434f] px-4 text-sm font-semibold text-white shadow-[0_16px_34px_rgba(112,67,79,0.25)] transition hover:bg-[#5f3843] disabled:opacity-60"
              >
                {stoppingForLeave ? <Loader2 className="h-4 w-4 animate-spin" /> : <XCircle className="h-4 w-4" />}
                {stoppingForLeave ? 'Stopping...' : 'Stop and leave'}
              </button>
            </div>
          </div>
        </div>
      )}
      {!hideProjectHeader && (
      <header className="sticky top-0 z-50 w-full border-b border-white/70 bg-white/65 backdrop-blur-xl shadow-[0_18px_50px_rgba(15,23,42,0.08)] devhub-header-enter">
        <div className="flex h-14 items-center px-6 justify-between max-w-[2000px] mx-auto">
          <div className="flex items-center gap-3">
            <button type="button" onClick={() => { void leaveProject(); }} className="w-8 h-8 rounded-lg bg-black flex items-center justify-center shadow-md"><Code2 className="w-5 h-5 text-white" /></button>
            <div className="w-px h-6 bg-slate-300" />
            <div>
              <h2 className="font-semibold text-sm">{project?.name}</h2>
              <div className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                <span className="text-[10px] text-slate-500">{project?.status}</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowProjectSettings(true)}
              className="inline-flex h-8 items-center gap-2 rounded-xl border border-black/5 bg-white/80 px-3 text-xs font-medium text-slate-600 shadow-[0_10px_24px_rgba(15,23,42,0.06)] transition-colors hover:bg-white"
            >
              <PencilLine className="h-3.5 w-3.5" />
              Edit Project
            </button>
            <button
              onClick={deleteProject}
              className="inline-flex h-8 items-center gap-2 rounded-xl bg-[#fff1f1] px-3 text-xs font-medium text-red-600 shadow-[0_10px_24px_rgba(15,23,42,0.06)] transition-colors hover:bg-[#ffe4e4]"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete
            </button>
            {activeTab === 'blueprint' && (
              <button onClick={() => startAgent()} disabled={agentRunning} className="h-8 px-3 rounded-md bg-black text-white text-xs font-medium shadow-md inline-flex items-center gap-2 disabled:opacity-50 hover:bg-slate-800">
                {agentRunning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                {agentRunning
                  ? (blueprintRunTarget === '__all__'
                      ? (deepDocsProgress ? `${deepDocsProgress.section} (${deepDocsProgress.completed}/${deepDocsProgress.total})` : 'Generating...')
                      : (deepDocsProgress ? deepDocsProgress.section : 'Generating...'))
                  : 'Regenerate Blueprint'}
              </button>
            )}
          </div>
        </div>
      </header>
      )}

      {!hideProjectHeader && project?.context_initializing && (
        <div className="max-w-[2000px] mx-auto w-full px-6 mt-2">
          <div className="p-3 rounded-2xl text-sm flex items-center justify-between border border-blue-100 bg-white/80 text-slate-700 backdrop-blur-xl shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
            <span>
              DevHub is auto-generating the blueprint{project?.source_type === 'starter' ? '' : ', onboarding context, and repository docs'} for this project.
            </span>
            <span className="inline-flex items-center gap-2 text-xs font-medium text-slate-500">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              Syncing
            </span>
          </div>
        </div>
      )}

      {!hideProjectHeader && implementationRun && (
        <div className="max-w-[2000px] mx-auto w-full px-6 mt-2">
          <div className="rounded-[28px] border border-white/70 bg-white/68 backdrop-blur-2xl shadow-[0_28px_80px_rgba(15,23,42,0.14)] px-5 py-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-3">
                <div className="mt-0.5 flex h-10 w-10 items-center justify-center rounded-2xl bg-black text-white shadow-[0_18px_40px_rgba(15,23,42,0.2)]">
                  <Sparkles className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Implementation In Progress</p>
                  <h3 className="text-base font-semibold text-slate-900">{implementationRun.featureTitle}</h3>
                  <p className="mt-1 text-sm text-slate-500">
                    DevHub is planning and applying the change set in the background. You can keep browsing while we finish.
                  </p>
                </div>
              </div>
              <div className="rounded-full border border-slate-200 bg-white/90 px-3 py-1 text-xs font-medium text-slate-600 shadow-[0_10px_24px_rgba(15,23,42,0.08)]">
                {Math.round(implementationProgress)}%
              </div>
            </div>
            <div className="mt-4 h-2.5 overflow-hidden rounded-full bg-slate-200/70">
              <div
                className="h-full rounded-full bg-[linear-gradient(90deg,#0f172a_0%,#111827_48%,#475569_100%)] shadow-[0_10px_24px_rgba(15,23,42,0.25)] transition-[width] duration-700 ease-out"
                style={{ width: `${implementationProgress}%` }}
              />
            </div>
          </div>
        </div>
      )}

      <main className="flex-1 min-h-0 min-w-0 flex flex-col lg:flex-row w-full overflow-hidden max-w-[2000px] mx-auto px-4 sm:px-6 py-4 gap-4">
        {/* Sidebar always visible — collapses to icons in workspace but remains expandable */}
        <nav className={`w-full shrink-0 flex lg:flex-col gap-2 lg:gap-1 pb-3 lg:pb-0 border-b lg:border-b-0 lg:border-r border-slate-200 overflow-x-auto lg:overflow-y-auto min-h-0 lg:sticky lg:top-4 lg:self-start lg:max-h-[calc(var(--app-vh)-8rem)] transition-[width,padding] duration-200 ${sidebarCollapsed ? 'lg:w-[84px] lg:px-2' : 'lg:w-64 lg:px-3'}`}>
          {/* Show project name + Views only on workspace tab where the top header is hidden */}
          {activeTab === 'code' && (
            <div className={`hidden lg:flex mb-3 border-b border-slate-200/70 pb-3 ${
              sidebarCollapsed ? 'flex-col items-center gap-2' : 'items-center justify-between gap-3'
            }`}>
              <button
                type="button"
                onClick={() => { void leaveProject(); }}
                className={`inline-flex shrink-0 items-center justify-center rounded-2xl transition-colors ${
                  sidebarCollapsed
                    ? 'h-11 w-11 bg-black text-white shadow-[0_16px_34px_rgba(15,23,42,0.18)]'
                    : 'h-10 w-10 bg-black text-white shadow-md hover:bg-slate-800'
                }`}
                title="Back to projects"
              >
                <Code2 className="h-[18px] w-[18px]" />
              </button>
              {!sidebarCollapsed && (
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold leading-5 text-slate-700">{project?.name || 'DevHub'}</span>
                  <span className="block text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-400">Views</span>
                </span>
              )}
              <button
                type="button"
                onClick={() => setSidebarCollapsed((current) => !current)}
                className={`inline-flex items-center justify-center rounded-xl border border-black/5 bg-white/85 text-slate-500 shadow-[0_10px_24px_rgba(15,23,42,0.06)] transition-colors hover:bg-white hover:text-slate-800 ${
                  sidebarCollapsed ? 'h-9 w-9' : 'h-9 w-9 shrink-0'
                }`}
                title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              >
                {sidebarCollapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
              </button>
            </div>
          )}
          {/* Collapse/expand toggle when not on workspace tab */}
          {activeTab !== 'code' && (
            <div className="hidden lg:flex mb-3 border-b border-slate-200/70 pb-3 items-center justify-end">
              <button
                type="button"
                onClick={() => setSidebarCollapsed((current) => !current)}
                className={`inline-flex items-center justify-center rounded-xl border border-black/5 bg-white/85 text-slate-500 shadow-[0_10px_24px_rgba(15,23,42,0.06)] transition-colors hover:bg-white hover:text-slate-800 ${
                  sidebarCollapsed ? 'h-9 w-9' : 'h-9 w-9 shrink-0'
                }`}
                title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              >
                {sidebarCollapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
              </button>
            </div>
          )}
          {tabs.map((tab) => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)}
              title={tab.label}
              className={`shrink-0 lg:w-full flex items-center gap-3 py-3 rounded-2xl text-left transition-all whitespace-nowrap ${sidebarCollapsed ? 'lg:justify-center lg:px-0' : 'px-3'} ${activeTab === tab.id ? 'bg-black text-white shadow-[0_18px_38px_rgba(15,23,42,0.18)]' : 'border border-transparent text-slate-600 hover:bg-white hover:border-black/5'}`}>
              <span className={`inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-[11px] font-semibold ${activeTab === tab.id ? 'bg-white/10 text-white' : 'bg-slate-100 text-slate-500'}`}>{tab.icon}</span>
              <span className={`min-w-0 ${sidebarCollapsed ? 'lg:hidden' : ''}`}>
                <span className="block text-xs font-semibold">{tab.label}</span>
                <span className={`hidden lg:block truncate text-[10px] ${activeTab === tab.id ? 'text-white/70' : 'text-slate-400'}`}>{tab.helper}</span>
              </span>
            </button>
          ))}
        </nav>

        <section
          className="flex-1 min-h-0 min-w-0 overflow-hidden flex flex-col bg-transparent"
        >
          <div
            ref={contentScrollRef}
            className={`project-scroll-shell flex-1 min-h-0 min-w-0 overflow-auto overflow-x-hidden ${
              activeTab === 'code'
                ? 'p-0'
                : activeTab === 'chat'
                  ? 'p-0 bg-white'
                  : activeTab === 'onboarding'
                    ? 'p-0'
                    : 'p-4 sm:p-6'
            }`}
          >
            {workspaceMounted && (
              <div className={activeTab === 'code' ? 'h-full min-h-0' : 'hidden'}>
                <CodeWorkspace
                  workspaceId={project?.workspace_id ?? null}
                  projectId={id ?? ''}
                  projectName={project?.name || 'Project'}
                  projectPath={project?.local_path}
                  coderCustomization={project?.coder_customization}
                  onProjectChanged={fetchProject}
                  projectSidebarCollapsed={sidebarCollapsed}
                  onToggleProjectSidebar={undefined}
                  isFullscreen={workspaceFullscreen}
                  onToggleFullscreen={() => setWorkspaceFullscreen((current) => !current)}
                  onRuntimeRunningChange={setWorkspaceRuntimeRunning}
                />
              </div>
            )}

            {activeTab === 'chat' && (
              <div className="flex flex-col h-full w-full bg-white">
                <ProjectChatPanel
                  projectId={id ?? ''}
                  mode="standalone"
                  selectedFile={null}
                  fileContent={""}
                  treeNodes={[]}
                  coderCustomization={project?.coder_customization}
                  onCodeApplied={fetchProject}
                  onCustomizationChanged={fetchProject}
                />
              </div>
            )}

            {/* ═════════════════════ OVERVIEW (Rich Dashboard) ═════════════════════ */}
            {activeTab === 'github' && (
              <GitHubPanel
                projectId={id ?? ''}
                integration={project?.github_integration}
              />
            )}

            {activeTab === 'overview' && (
              <div className="space-y-5">
                <div className="overflow-hidden rounded-[28px] border border-black/5 bg-[linear-gradient(145deg,rgba(255,255,255,0.96),rgba(248,250,252,0.92))] px-6 py-6 shadow-[0_22px_60px_rgba(15,23,42,0.1)]">
                  <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
                    <div className="min-w-0 max-w-4xl">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">Project Snapshot</p>
                      <h2 className="mt-2 break-words text-[clamp(1.65rem,3vw,2.6rem)] font-semibold leading-[1.05] text-slate-900">
                        {project?.name}
                      </h2>
                      <p className="mt-4 max-w-4xl break-words text-sm leading-7 text-slate-600">
                        {bp?.project_summary || project?.description || 'No project summary yet. Generate a blueprint to create one.'}
                      </p>
                    </div>
                    <div className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2 xl:w-[320px]">
                      <div className="rounded-2xl border border-black/5 bg-[#f8fafc] p-4 shadow-[0_16px_32px_rgba(15,23,42,0.06)]">
                        <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Status</p>
                        <div className="mt-3 flex items-center gap-2">
                          <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-[0_0_0_6px_rgba(74,222,128,0.14)]" />
                          <span className="text-sm font-medium capitalize text-slate-800">{project?.status || 'active'}</span>
                        </div>
                      </div>
                      <div className="rounded-2xl border border-black/5 bg-[#fff7ef] p-4 shadow-[0_16px_32px_rgba(15,23,42,0.06)]">
                        <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Workspace</p>
                        <p className="mt-3 text-sm font-medium text-slate-800">{project?.workspace_id ? 'Connected' : 'Not ready'}</p>
                        <p className="mt-1 text-xs text-slate-500">Editor, preview and runtime state stay in sync here.</p>
                      </div>
                    </div>
                  </div>
                  <div className="mt-5 flex flex-wrap gap-2">
                    {(project?.tech_stack || []).map((t: string) => (
                      <span
                        key={t}
                        className="rounded-full border border-black/5 bg-white px-3 py-1 text-[11px] font-medium capitalize text-slate-600 shadow-[0_10px_24px_rgba(15,23,42,0.05)]"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Stats row */}
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
                  {[
                    { label: 'Services', val: bp?.services?.length || 0, sub: 'Architecture', color: 'text-[#365fa8] bg-[#edf4ff] border-[#dce7ff]' },
                    { label: 'Endpoints', val: bp?.api_endpoints?.length || 0, sub: 'API Surface', color: 'text-[#8b5ec1] bg-[#f4efff] border-[#eadfff]' },
                    { label: 'DB Tables', val: bp?.database_schema?.length || 0, sub: 'Data Layer', color: 'text-[#be6a2f] bg-[#fff4ea] border-[#ffe4cc]' },
                    { label: 'Work Items', val: features.length, sub: `${features.filter((f: any) => f.status === 'staging').length} in staging`, color: 'text-[#2f7d5a] bg-[#ecfaf2] border-[#d5f0df]' },
                    { label: 'Components', val: bp?.key_components?.length || 0, sub: 'Key Modules', color: 'text-[#a27729] bg-[#fff9e8] border-[#f7e8bb]' },
                  ].map((s) => (
                    <div key={s.label} className={`rounded-[24px] border p-4 text-center shadow-[0_18px_40px_rgba(15,23,42,0.06)] ${s.color}`}>
                      <div className={`text-3xl font-semibold ${s.color.split(' ')[0]}`}>{s.val}</div>
                      <div className="mt-1 text-xs font-semibold uppercase tracking-[0.14em] opacity-80">{s.label}</div>
                      <div className="mt-1 text-[11px] opacity-60">{s.sub}</div>
                    </div>
                  ))}
                </div>

                {/* Architecture diagram + Quick Actions */}
                <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
                  <div className="xl:col-span-2 min-w-0">
                    {bp?.mermaid_architecture ? (
                      <div className="overflow-hidden rounded-[26px] border border-black/5 bg-white p-5 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
                        <h3 className="mb-3 text-sm font-semibold text-slate-800">System Architecture</h3>
                        <div className="max-w-full overflow-auto rounded-[22px] bg-[#fbfcfe] p-3">
                          <MermaidDiagram chart={bp.mermaid_architecture} id="overview-arch" />
                        </div>
                      </div>
                    ) : (
                      <div className="rounded-[26px] border border-dashed border-black/10 bg-[#fafbfc] p-8 text-center shadow-[0_12px_32px_rgba(15,23,42,0.05)]">
                        <p className="text-sm text-slate-500">Generate a blueprint to see the architecture diagram</p>
                        <button onClick={() => { setActiveTab('blueprint'); setTimeout(startAgent, 300); }} className="mt-3 rounded-xl bg-black px-4 py-2 text-xs font-medium text-white shadow-[0_14px_30px_rgba(15,23,42,0.16)]">
                          Generate Blueprint
                        </button>
                      </div>
                    )}
                  </div>

                  <div className="space-y-4 min-w-0">
                    {/* Quick Actions */}
                    <div className="rounded-[26px] border border-black/5 bg-white p-4 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
                      <h4 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Quick Actions</h4>
                      <div className="space-y-2">
                        {[
                          { label: 'Open Workspace', desc: 'Edit code & run terminal', tab: 'code', icon: 'WS' },
                          { label: 'Open Work Items', desc: 'Plan, review, and implement work', tab: 'work_items', icon: 'WI' },
                          { label: 'View Blueprint', desc: 'Architecture wiki', tab: 'blueprint', icon: 'BP' },
                          { label: 'Start Onboarding', desc: 'Guided setup walk-through', tab: 'onboarding', icon: 'ON' },
                        ].map(a => (
                          <button
                            key={a.tab}
                            onClick={() => setActiveTab(a.tab)}
                            className="flex w-full items-center gap-3 rounded-2xl border border-black/5 bg-[linear-gradient(180deg,#ffffff,#f8fafc)] px-3 py-3 text-left shadow-[0_12px_28px_rgba(15,23,42,0.05)] transition-transform duration-200 hover:-translate-y-0.5"
                          >
                            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-[#f4f6fb] text-[11px] font-semibold tracking-[0.16em] text-slate-500 shadow-[inset_0_1px_0_rgba(255,255,255,0.9)]">{a.icon}</span>
                            <div className="min-w-0">
                              <div className="truncate text-sm font-medium text-slate-800">{a.label}</div>
                              <div className="break-words text-[11px] text-slate-500">{a.desc}</div>
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Project Info */}
                    <div className="rounded-[26px] border border-black/5 bg-white p-4 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
                      <div className="mb-3 flex items-center justify-between gap-3">
                        <h4 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Project Info</h4>
                        <button onClick={deleteProject} className="flex items-center gap-1 rounded-full bg-[#fff1f1] px-3 py-1 text-[10px] font-medium text-red-600 transition-colors hover:bg-[#ffe4e4]">
                          <Trash2 className="w-3 h-3" /> Delete
                        </button>
                      </div>
                      <div className="space-y-2 text-xs text-slate-600">
                        <div className="rounded-2xl bg-[#f8fafc] px-3 py-2.5">
                          <b className="text-slate-500">Status:</b>{' '}
                          <span className="rounded-full bg-[#e7f6ef] px-2 py-0.5 text-[10px] font-medium text-[#2f7d5a]">{project?.status}</span>
                        </div>
                        <div className="rounded-2xl bg-[#f8fafc] px-3 py-2.5">
                          <b className="text-slate-500">Path:</b>{' '}
                          <code className="break-all rounded bg-white px-1.5 py-0.5 text-[10px] text-slate-600">{project?.local_path || '—'}</code>
                        </div>
                        <div className="rounded-2xl bg-[#f8fafc] px-3 py-2.5 break-words">
                          <b className="text-slate-500">Runtime:</b> {cleanRunCommand(project?.runtime?.run_command)}
                        </div>
                        <div className="rounded-2xl bg-[#f8fafc] px-3 py-2.5">
                          <b className="text-slate-500">Workspace:</b> {project?.workspace_id ? 'Active' : 'Unavailable'}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Features by stage breakdown */}
                <div className="rounded-[26px] border border-black/5 bg-white p-5 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
                  <div className="mb-4 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                    <h3 className="text-sm font-semibold text-slate-800">Feature Pipeline Overview</h3>
                    <p className="text-xs text-slate-400">A quick stage-by-stage pulse of the delivery flow.</p>
                  </div>
                  <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
                    {PIPELINE_STAGES.map(stage => {
                      const count = features.filter((f: any) => f.status === stage).length;
                      return (
                        <div key={stage} className="rounded-[22px] border border-black/5 bg-[#fbfcfe] px-4 py-4 text-center shadow-[0_10px_24px_rgba(15,23,42,0.04)]">
                          <div className={`text-2xl font-semibold ${stageColor(stage).split(' ')[1]}`}>{count}</div>
                          <div className="mt-1 text-[11px] font-medium capitalize text-slate-500">{stage.replace('_', ' ')}</div>
                          <div className={`mt-3 h-2 rounded-full ${count > 0 ? stageColor(stage).split(' ')[0] : 'bg-slate-100'}`} />
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'blueprint' && (
              <BlueprintPanel
                projectId={id ?? ''}
                blueprint={project?.blueprint}
                documentation={project?.documentation}
                scrollContainer={contentScrollRef.current}
                deepDocsProgress={deepDocsProgress}
                agentEvents={agentEvents}
                onRegenerateSection={(section) => void startAgent(section)}
                onGenerateDocumentation={generateDocumentation}
                documentationGenerating={documentationRunning}
                regeneratingSection={blueprintRunTarget === '__all__' ? null : blueprintRunTarget}
                blueprintBusy={agentRunning}
              />
            )}
            {activeTab === 'onboarding' && (
              <OnboardingPanel
                blueprint={project?.blueprint}
                projectName={project?.name || 'Project'}
                sourceType={sourceType}
                workItems={features}
                runtime={project?.runtime}
                workspaceReady={Boolean(project?.workspace_id)}
                onboardingSummary={onboardingSummary}
                onNavigateToTab={(tabId: string) => {
                  if (tabId === 'features' || tabId === 'pipeline') {
                    setActiveTab('work_items');
                    return;
                  }
                  setActiveTab(tabId);
                }}
              />
            )}

            {/* ═════════════════════ FEATURES (Full Lifecycle) ═════════════════════ */}
            {activeTab === 'work_items' && workItemsView === 'list' && (
              <div className="space-y-4">
                <div className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">Execution Surface</p>
                    <h2 className="text-lg font-semibold">Work Items</h2>
                    <p className="text-xs text-slate-400 mt-0.5">{features.length} total · {features.filter((f: any) => f.status === 'development').length} in development</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="inline-flex rounded-2xl border border-black/5 bg-white p-1 shadow-[0_10px_24px_rgba(15,23,42,0.05)]">
                      <button type="button" onClick={() => setWorkItemsView('list')} className={`rounded-xl px-3 py-2 text-xs font-medium ${workItemsView === 'list' ? 'bg-black text-white' : 'text-slate-500'}`}>List</button>
                      <button type="button" onClick={() => setWorkItemsView('board')} className="rounded-xl px-3 py-2 text-xs font-medium text-slate-500">Board</button>
                    </div>
                    <button onClick={() => setShowAddFeature(true)} className="h-8 px-3 rounded-lg bg-black text-white text-xs font-medium inline-flex items-center gap-1.5 shadow-sm">
                      <Plus className="w-3.5 h-3.5" /> New Work Item
                    </button>
                  </div>
                </div>
                {features.length === 0 && (
                  <div className="text-center py-16 bg-slate-50 rounded-xl border border-dashed border-slate-200">
                    <div className="text-4xl mb-3">✨</div>
                    <p className="font-medium text-slate-500">No work items yet</p>
                    <p className="text-xs text-slate-400 mt-1 max-w-xs mx-auto">Create a work item and DevHub will generate a spec, implementation plan, and shared delivery state for it.</p>
                    <button onClick={() => setShowAddFeature(true)} className="mt-4 px-4 py-2 bg-black text-white text-xs rounded-lg font-medium">Create First Work Item</button>
                  </div>
                )}
                {features.map((feature: any) => {
                  const isExpanded = expandedFeature === feature.id;
                  const spec = feature.spec || {};
                  return (
                    <div key={feature.id} className="bg-white rounded-xl border border-slate-200 overflow-hidden hover:shadow-md transition-shadow">
                      {/* Feature Header */}
                      <div className="flex items-start justify-between p-4 cursor-pointer" onClick={() => setExpandedFeature(isExpanded ? null : feature.id)}>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <h3 className="font-semibold text-sm">{feature.title}</h3>
                            <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${stageColor(feature.status)}`}>{feature.status?.replace('_', ' ')}</span>
                            {spec.estimated_complexity && <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium ${spec.estimated_complexity === 'high' ? 'bg-red-100 text-red-700' : spec.estimated_complexity === 'medium' ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}`}>{spec.estimated_complexity}</span>}
                            {spec.estimated_effort && <span className="text-[9px] text-slate-400 bg-slate-50 px-1.5 py-0.5 rounded">⏱ {spec.estimated_effort}</span>}
                          </div>
                          <p className="text-xs text-slate-500 mt-1">{feature.description}</p>
                        </div>
                        <ChevronDown className={`w-4 h-4 text-slate-400 ml-2 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                      </div>

                      {/* Expanded Detail */}
                      {isExpanded && (
                        <div className="border-t border-slate-100 bg-slate-50/30">
                          <div className="p-5 space-y-4">
                            {/* User Story */}
                            {spec.user_story && (
                              <div className="bg-indigo-50 border border-indigo-100 rounded-lg p-3">
                                <div className="text-[10px] font-bold text-indigo-500 uppercase mb-1">User Story</div>
                                <p className="text-xs text-indigo-800 italic">{spec.user_story}</p>
                              </div>
                            )}

                            {/* Technical Approach */}
                            {spec.technical_approach && (
                              <div>
                                <h4 className="text-xs font-bold text-slate-500 uppercase mb-1">Technical Approach</h4>
                                <p className="text-xs text-slate-700 leading-relaxed">{spec.technical_approach}</p>
                              </div>
                            )}

                            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                              {/* Files to Modify */}
                              {(spec.files_to_modify || []).length > 0 && (
                                <div className="bg-white rounded-lg border border-slate-200 p-3">
                                  <h4 className="text-[10px] font-bold text-slate-500 uppercase mb-2 flex items-center gap-1"><FileCode className="w-3 h-3" /> Files to Modify</h4>
                                  <div className="space-y-1.5">
                                    {(spec.files_to_modify || []).map((f: any, i: number) => (
                                      <div key={i} className="text-[11px]">
                                        <code className="bg-slate-100 px-1.5 py-0.5 rounded font-mono text-blue-700">{f.path}</code>
                                        {f.changes && <p className="text-slate-500 mt-0.5 pl-1">{f.changes}</p>}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {/* New Files */}
                              {(spec.new_files_needed || []).length > 0 && (
                                <div className="bg-white rounded-lg border border-slate-200 p-3">
                                  <h4 className="text-[10px] font-bold text-slate-500 uppercase mb-2">✨ New Files Needed</h4>
                                  <div className="space-y-1.5">
                                    {(spec.new_files_needed || []).map((f: any, i: number) => (
                                      <div key={i} className="text-[11px]">
                                        <code className="bg-emerald-50 text-emerald-700 px-1.5 py-0.5 rounded font-mono">{f.path}</code>
                                        {f.purpose && <p className="text-slate-500 mt-0.5 pl-1">{f.purpose}</p>}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>

                            {/* Acceptance Criteria */}
                            {(spec.acceptance_criteria || []).length > 0 && (
                              <div>
                                <h4 className="text-[10px] font-bold text-slate-500 uppercase mb-2">Acceptance Criteria</h4>
                                <div className="space-y-1">
                                  {(spec.acceptance_criteria || []).map((c: string, i: number) => (
                                    <div key={i} className="flex gap-2 text-xs text-slate-700"><span className="text-emerald-500 shrink-0">✓</span>{c}</div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* Testing Plan */}
                            {spec.testing_plan && (
                              <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
                                {(spec.testing_plan.unit_tests || []).length > 0 && (
                                  <div className="bg-white rounded-lg border border-slate-200 p-3">
                                    <h4 className="text-[10px] font-bold text-slate-500 uppercase mb-1">Unit Tests</h4>
                                    {(spec.testing_plan.unit_tests || []).map((t: string, i: number) => (
                                      <div key={i} className="text-[10px] text-slate-600 mb-0.5">• {t}</div>
                                    ))}
                                  </div>
                                )}
                                {(spec.testing_plan.integration_tests || []).length > 0 && (
                                  <div className="bg-white rounded-lg border border-slate-200 p-3">
                                    <h4 className="text-[10px] font-bold text-slate-500 uppercase mb-1">Integration Tests</h4>
                                    {(spec.testing_plan.integration_tests || []).map((t: string, i: number) => (
                                      <div key={i} className="text-[10px] text-slate-600 mb-0.5">• {t}</div>
                                    ))}
                                  </div>
                                )}
                                {(spec.testing_plan.edge_cases || []).length > 0 && (
                                  <div className="bg-white rounded-lg border border-slate-200 p-3">
                                    <h4 className="text-[10px] font-bold text-slate-500 uppercase mb-1">Edge Cases</h4>
                                    {(spec.testing_plan.edge_cases || []).map((t: string, i: number) => (
                                      <div key={i} className="text-[10px] text-slate-600 mb-0.5">• {t}</div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            )}

                            {/* API + DB Changes */}
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                              {(spec.api_changes || []).length > 0 && (
                                <div className="bg-blue-50 border border-blue-100 rounded-lg p-3">
                                  <h4 className="text-[10px] font-bold text-blue-600 uppercase mb-1">API Changes</h4>
                                  {(spec.api_changes || []).map((a: any, i: number) => (
                                    <div key={i} className="text-[10px] text-slate-700 flex gap-1.5 mb-0.5">
                                      <span className={`font-bold ${a.method === 'POST' ? 'text-blue-600' : a.method === 'DELETE' ? 'text-red-600' : 'text-emerald-600'}`}>{a.method}</span>
                                      <code className="font-mono">{a.path}</code>
                                    </div>
                                  ))}
                                </div>
                              )}
                              {(spec.database_changes || []).length > 0 && (
                                <div className="bg-orange-50 border border-orange-100 rounded-lg p-3">
                                  <h4 className="text-[10px] font-bold text-orange-600 uppercase mb-1">Database Changes</h4>
                                  {(spec.database_changes || []).map((d: any, i: number) => (
                                    <div key={i} className="text-[10px] text-slate-700 mb-0.5">
                                      <code className="font-mono font-medium">{d.table}</code>: {d.change}
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>

                            {/* Risks */}
                            {(spec.risks || []).length > 0 && (
                              <div className="bg-yellow-50 border border-yellow-100 rounded-lg p-3">
                                <h4 className="text-[10px] font-bold text-yellow-700 uppercase mb-1">⚠️ Risks</h4>
                                {(spec.risks || []).map((r: string, i: number) => (
                                  <div key={i} className="text-[10px] text-slate-700 mb-0.5">• {r}</div>
                                ))}
                                {spec.rollback_plan && <div className="text-[10px] text-slate-600 mt-1 pt-1 border-t border-yellow-100"><b>Rollback:</b> {spec.rollback_plan}</div>}
                              </div>
                            )}

                            {/* Test Results if exists */}
                            {feature.test_results && (
                              <div className={`rounded-lg p-3 text-xs ${feature.test_results.overall_status === 'passed' ? 'bg-emerald-50 text-emerald-700 border border-emerald-100' : feature.test_results.overall_status === 'failed' ? 'bg-red-50 text-red-700 border border-red-100' : 'bg-amber-50 text-amber-700 border border-amber-100'}`}>
                                <div className="flex items-center justify-between mb-1">
                                  <b>Test Results</b>
                                  <span className="text-[10px] font-mono">Score: {feature.test_results.score}/100</span>
                                </div>
                                <p>{feature.test_results.summary}</p>
                              </div>
                            )}
                          </div>

                          {/* Action bar at bottom of expanded */}
                          <div className="flex flex-wrap gap-2 px-5 py-3 border-t border-slate-100 bg-white">
                            {feature.status !== 'staging' && (
                              <button onClick={() => pipelineAction(feature.id, 'implement')} disabled={actionLoading === feature.id + 'implement'} className="inline-flex h-8 items-center gap-1.5 rounded-xl bg-black px-4 text-xs font-medium text-white shadow-[0_12px_24px_rgba(15,23,42,0.14)] disabled:opacity-50 hover:bg-slate-800">
                                {actionLoading === feature.id + 'implement' ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />} AI Implement
                              </button>
                            )}
                            {feature.status !== 'staging' && (
                              <button onClick={() => pipelineAction(feature.id, 'advance')} disabled={actionLoading === feature.id + 'advance'} className="inline-flex h-8 items-center gap-1 rounded-xl bg-[#eef4ff] px-3 text-xs font-medium text-[#3458a5] disabled:opacity-50 hover:bg-[#e3edff]">
                                <ChevronRight className="w-3 h-3" /> Move Forward
                              </button>
                            )}
                            <button onClick={() => pipelineAction(feature.id, 'approve')} disabled={actionLoading === feature.id + 'approve'} className="inline-flex h-8 items-center gap-1 rounded-xl bg-[#edf8f1] px-3 text-xs font-medium text-[#2f7d5a] disabled:opacity-50 hover:bg-[#e2f3e8]">
                              <Check className="w-3 h-3" /> Approve
                            </button>
                            {feature.status !== 'backlog' && (
                              <button onClick={() => pipelineAction(feature.id, 'reject')} disabled={actionLoading === feature.id + 'reject'} className="inline-flex h-8 items-center gap-1 rounded-xl bg-[#fff1f1] px-3 text-xs font-medium text-[#b24a4a] disabled:opacity-50 hover:bg-[#ffe5e5]">
                                <XCircle className="w-3 h-3" /> Send Back
                              </button>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Collapsed actions */}
                      {!isExpanded && (
                        <div className="flex flex-wrap gap-2 px-4 pb-3">
                          {feature.status !== 'staging' && (
                            <button onClick={(e) => { e.stopPropagation(); pipelineAction(feature.id, 'implement'); }} disabled={actionLoading === feature.id + 'implement'} className="h-7 px-3 rounded bg-black text-white text-[10px] font-medium inline-flex items-center gap-1 disabled:opacity-50">
                              {actionLoading === feature.id + 'implement' ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />} Implement
                            </button>
                          )}
                          {feature.status !== 'staging' && (
                            <button onClick={(e) => { e.stopPropagation(); pipelineAction(feature.id, 'advance'); }} disabled={actionLoading === feature.id + 'advance'} className="inline-flex h-7 items-center gap-1 rounded-xl bg-[#eef4ff] px-3 text-[10px] font-medium text-[#3458a5] disabled:opacity-50">
                              <ChevronRight className="w-3 h-3" /> Forward
                            </button>
                          )}
                          <button onClick={(e) => { e.stopPropagation(); pipelineAction(feature.id, 'approve'); }} disabled={actionLoading === feature.id + 'approve'} className="inline-flex h-7 items-center gap-1 rounded-xl bg-[#edf8f1] px-3 text-[10px] font-medium text-[#2f7d5a] disabled:opacity-50">
                            <Check className="w-3 h-3" /> Approve
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* ═════════════════════ PIPELINE (Rich Kanban) ═════════════════════ */}
            {activeTab === 'work_items' && workItemsView === 'board' && (
              <div className="flex h-full min-h-0 flex-col">
                <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">Delivery Flow</p>
                    <h2 className="mt-1 text-xl font-semibold text-slate-900">Work Items Board</h2>
                    <p className="mt-1 text-sm text-slate-500">Board view of the same work items shown in the list.</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="inline-flex rounded-2xl border border-black/5 bg-white p-1 shadow-[0_10px_24px_rgba(15,23,42,0.05)]">
                      <button type="button" onClick={() => setWorkItemsView('list')} className="rounded-xl px-3 py-2 text-xs font-medium text-slate-500">List</button>
                      <button type="button" onClick={() => setWorkItemsView('board')} className={`rounded-xl px-3 py-2 text-xs font-medium ${workItemsView === 'board' ? 'bg-black text-white' : 'text-slate-500'}`}>Board</button>
                    </div>
                    <span className="rounded-full border border-black/5 bg-[#f8fafc] px-3 py-1 text-xs font-medium text-slate-500 shadow-[0_10px_24px_rgba(15,23,42,0.05)]">{features.length} work items total</span>
                  </div>
                </div>
                <div className="grid min-h-0 grid-flow-col auto-cols-[minmax(280px,1fr)] gap-4 overflow-x-auto overflow-y-hidden pb-4 pr-1">
                  {PIPELINE_STAGES.map((stage) => {
                    const stageFeatures = features.filter((feature: any) => feature.status === stage);
                    return (
                      <div key={stage} className="flex min-w-0 min-h-0 flex-col overflow-hidden rounded-[28px] border border-black/5 bg-[linear-gradient(180deg,rgba(255,255,255,0.94),rgba(247,249,251,0.9))] shadow-[0_22px_60px_rgba(15,23,42,0.08)]">
                        <div className="flex items-center justify-between border-b border-black/5 bg-white/80 px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                          <span className="flex items-center gap-1.5">
                            <span className={`w-2 h-2 rounded-full ${stageColor(stage).split(' ')[0]}`} />
                            {stage.replace('_', ' ')}
                          </span>
                          <span className="rounded-full border border-black/5 bg-white px-2.5 py-1 text-[10px] font-medium text-slate-400 shadow-[0_8px_20px_rgba(15,23,42,0.05)]">{stageFeatures.length}</span>
                        </div>
                        <div className="flex-1 min-h-[320px] space-y-3 overflow-y-auto bg-[#fbfcfe] p-3">
                          {stageFeatures.map((feature: any) => {
                            const spec = feature.spec || {};
                            const isExpanded = expandedPipelineFeature === feature.id;
                            const latestHistory = Array.isArray(feature.pipeline_history) && feature.pipeline_history.length
                              ? feature.pipeline_history[feature.pipeline_history.length - 1]
                              : null;
                            return (
                              <div key={feature.id} className="min-w-0 overflow-hidden rounded-[24px] border border-black/5 bg-white p-4 shadow-[0_16px_34px_rgba(15,23,42,0.06)]">
                                <button type="button" onClick={() => setExpandedPipelineFeature(isExpanded ? null : feature.id)} className="w-full text-left">
                                  <div className="flex items-start justify-between gap-3">
                                    <div className="min-w-0">
                                      <h4 className="mb-1 break-words text-sm font-semibold leading-5 text-slate-900">{feature.title}</h4>
                                      {feature.description && <p className={`break-words text-[11px] leading-5 text-slate-500 ${isExpanded ? '' : 'line-clamp-2'}`}>{feature.description}</p>}
                                    </div>
                                    <span className="rounded-full bg-[#f5f7fb] px-2 py-1 text-[10px] font-medium text-slate-400">{isExpanded ? 'Hide' : 'Expand'}</span>
                                  </div>
                                </button>

                                {/* Spec preview */}
                                {spec.technical_approach && (
                                  <p className={`mb-3 overflow-hidden break-words rounded-2xl bg-[#f8fafc] p-3 text-[11px] italic leading-5 text-slate-500 ${isExpanded ? '' : 'line-clamp-4'}`}>
                                    {spec.technical_approach}
                                  </p>
                                )}

                                {/* Metadata badges */}
                                <div className="mb-3 flex min-w-0 flex-wrap gap-2">
                                  {spec.estimated_complexity && (
                                    <span className={`max-w-full break-words rounded-full px-2 py-1 text-[10px] font-medium ${spec.estimated_complexity === 'high' ? 'bg-[#ffe8e8] text-[#b24a4a]' : spec.estimated_complexity === 'medium' ? 'bg-[#fff2dc] text-[#a56a1f]' : 'bg-[#e7f6ef] text-[#2f7d5a]'}`}>
                                      {spec.estimated_complexity}
                                    </span>
                                  )}
                                  {spec.estimated_effort && (
                                    <span className="max-w-full break-words rounded-full bg-[#f8fafc] px-2 py-1 text-[10px] text-slate-500">
                                      ⏱ {spec.estimated_effort}
                                    </span>
                                  )}
                                  {(spec.acceptance_criteria || []).length > 0 && (
                                    <span className="max-w-full break-words rounded-full bg-[#f2f6ff] px-2 py-1 text-[10px] text-[#4866aa]">
                                      ✓ {(spec.acceptance_criteria || []).length} criteria
                                    </span>
                                  )}
                                </div>

                                {latestHistory?.comment && (
                                  <div className="mb-3 rounded-2xl bg-[#fbfcfe] px-3 py-2 text-[11px] leading-5 text-slate-500">
                                    {latestHistory.comment}
                                  </div>
                                )}

                                {/* Test results badge */}
                                {feature.test_results && (
                                  <div className={`mb-3 rounded-2xl px-3 py-2 text-[10px] font-medium ${feature.test_results.overall_status === 'passed' ? 'bg-[#e7f6ef] text-[#2f7d5a]' : feature.test_results.overall_status === 'failed' ? 'bg-[#ffe8e8] text-[#b24a4a]' : 'bg-[#fff2dc] text-[#a56a1f]'}`}>
                                    Tests: {feature.test_results.overall_status} ({feature.test_results.score}/100)
                                  </div>
                                )}

                                {isExpanded && (
                                  <div className="mb-4 space-y-3 border-t border-black/5 pt-4">
                                    {(spec.files_to_modify || []).length > 0 && (
                                      <div className="rounded-2xl bg-[#fbfcfe] p-3">
                                        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">Files In Scope</p>
                                        <div className="mt-2 space-y-1.5">
                                          {(spec.files_to_modify || []).slice(0, 4).map((item: any, index: number) => (
                                            <div key={`${feature.id}-pipeline-file-${index}`} className="text-[11px] text-slate-600">
                                              <code className="rounded bg-white px-1.5 py-0.5 text-[10px] text-slate-700">{item.path}</code>
                                              {item.changes && <p className="mt-1 break-words text-slate-500">{item.changes}</p>}
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    )}
                                    <div className="flex flex-wrap gap-2">
                                      <button
                                        onClick={() => {
                                          setActiveTab('work_items');
                                          setWorkItemsView('list');
                                          setExpandedFeature(feature.id);
                                        }}
                                        className="rounded-xl bg-[#f3f6fb] px-3 py-2 text-[11px] font-medium text-slate-600 transition-colors hover:bg-[#e9eef5]"
                                      >
                                        Open List View
                                      </button>
                                      <button
                                        onClick={() => setActiveTab('code')}
                                        className="rounded-xl bg-[#f9f5ff] px-3 py-2 text-[11px] font-medium text-[#7f53aa] transition-colors hover:bg-[#f1e8ff]"
                                      >
                                        Go To Workspace
                                      </button>
                                    </div>
                                  </div>
                                )}

                                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                                  {stage !== 'staging' && (
                                    <button
                                      onClick={() => pipelineAction(feature.id, 'implement')}
                                      className="w-full min-w-0 rounded-xl bg-black px-3 py-2 text-center text-[11px] font-medium text-white shadow-[0_12px_24px_rgba(15,23,42,0.16)] transition-colors hover:bg-slate-800"
                                    >
                                      Implement
                                    </button>
                                  )}
                                  {stage !== 'staging' && (
                                    <button
                                      onClick={() => pipelineAction(feature.id, 'advance')}
                                      className="w-full min-w-0 rounded-xl bg-[#eef4ff] px-3 py-2 text-center text-[11px] font-medium text-[#3458a5] transition-colors hover:bg-[#e3edff]"
                                    >
                                      Move Forward
                                    </button>
                                  )}
                                  <button
                                    onClick={() => pipelineAction(feature.id, 'approve')}
                                    className="w-full min-w-0 rounded-xl bg-[#edf8f1] px-3 py-2 text-center text-[11px] font-medium text-[#2f7d5a] transition-colors hover:bg-[#e2f3e8]"
                                  >
                                    Approve
                                  </button>
                                  {stage !== 'backlog' && (
                                    <button
                                      onClick={() => pipelineAction(feature.id, 'reject')}
                                      className="w-full min-w-0 rounded-xl bg-[#fff1f1] px-3 py-2 text-center text-[11px] font-medium text-[#b24a4a] transition-colors hover:bg-[#ffe5e5]"
                                    >
                                      Send Back
                                    </button>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                          {stageFeatures.length === 0 && (
                            <div className="rounded-[22px] border border-dashed border-black/5 bg-white/75 px-4 py-12 text-center text-[11px] text-slate-400">
                              No work items
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </section>
      </main>

      {showAddFeature && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center">
          <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={() => setShowAddFeature(false)} />
          <div className="relative bg-white rounded-xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
            <div className="flex justify-between px-5 py-3 border-b border-slate-100">
              <h3 className="font-semibold text-sm">New Feature</h3>
              <button onClick={() => setShowAddFeature(false)} className="p-1 rounded hover:bg-slate-100"><X className="w-4 h-4 text-slate-400" /></button>
            </div>
            <div className="px-5 py-4 space-y-3">
              <input type="text" placeholder="Feature title" value={featureForm.title} onChange={(e) => setFeatureForm({ ...featureForm, title: e.target.value })} className="w-full h-9 px-3 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-black" />
              <textarea placeholder="Description" rows={3} value={featureForm.description} onChange={(e) => setFeatureForm({ ...featureForm, description: e.target.value })} className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-black resize-none" />
              <p className="text-[10px] text-slate-400">AI will generate a detailed spec with tech approach, acceptance criteria, testing plan, and can implement directly into the workspace.</p>
            </div>
            <div className="flex justify-end gap-2 px-5 py-3 border-t border-slate-100 bg-slate-50/50">
              <button onClick={() => setShowAddFeature(false)} className="px-3 py-1.5 text-xs text-slate-600 rounded-lg hover:bg-slate-200">Cancel</button>
              <button onClick={createFeature} disabled={creatingFeature || !featureForm.title.trim()} className="px-4 py-1.5 text-xs text-white bg-black rounded-lg disabled:opacity-50 inline-flex items-center gap-1">
                {creatingFeature && <Loader2 className="w-3 h-3 animate-spin" />} Create
              </button>
            </div>
          </div>
        </div>
      )}

      {showProjectSettings && (
        <div className="fixed inset-0 z-[105] flex items-center justify-center px-4">
          <div className="absolute inset-0 bg-black/18 backdrop-blur-md" onClick={() => setShowProjectSettings(false)} />
          <div className="relative max-h-[88vh] w-full max-w-2xl overflow-y-auto rounded-[32px] border border-white/80 bg-white/88 shadow-[0_32px_90px_rgba(15,23,42,0.18)] backdrop-blur-2xl">
            <div className="flex items-center justify-between border-b border-black/5 px-6 py-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">Project Settings</p>
                <h3 className="mt-1 text-lg font-semibold text-slate-900">Edit project details</h3>
              </div>
              <button onClick={() => setShowProjectSettings(false)} className="rounded-full bg-[#f5f7fb] p-2 text-slate-500 transition-colors hover:bg-[#ebeff5]">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="grid gap-4 px-6 py-5">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-slate-700">Project Name</label>
                  <input
                    type="text"
                    value={projectForm.name}
                    onChange={(event) => setProjectForm((current) => ({ ...current, name: event.target.value }))}
                    className="h-11 w-full rounded-2xl border border-black/10 bg-white px-4 text-sm text-slate-700 outline-none transition-shadow focus:shadow-[0_0_0_4px_rgba(15,23,42,0.06)]"
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-slate-700">Tech Stack</label>
                  <input
                    type="text"
                    value={projectForm.tech_stack}
                    onChange={(event) => setProjectForm((current) => ({ ...current, tech_stack: event.target.value }))}
                    placeholder="React, Django, PostgreSQL"
                    className="h-11 w-full rounded-2xl border border-black/10 bg-white px-4 text-sm text-slate-700 outline-none transition-shadow focus:shadow-[0_0_0_4px_rgba(15,23,42,0.06)]"
                  />
                </div>
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">Description</label>
                <textarea
                  rows={4}
                  value={projectForm.description}
                  onChange={(event) => setProjectForm((current) => ({ ...current, description: event.target.value }))}
                  className="w-full rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm text-slate-700 outline-none transition-shadow focus:shadow-[0_0_0_4px_rgba(15,23,42,0.06)]"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-sm font-medium text-slate-700">GitHub URL</label>
                <input
                  type="text"
                  value={projectForm.github_url}
                  onChange={(event) => setProjectForm((current) => ({ ...current, github_url: event.target.value }))}
                  placeholder="Optional repository URL"
                  className="h-11 w-full rounded-2xl border border-black/10 bg-white px-4 text-sm text-slate-700 outline-none transition-shadow focus:shadow-[0_0_0_4px_rgba(15,23,42,0.06)]"
                />
              </div>
            </div>
            <div className="flex items-center justify-end gap-3 border-t border-black/5 px-6 py-4">
              <button onClick={() => setShowProjectSettings(false)} className="rounded-2xl px-4 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-[#f3f5f8]">
                Cancel
              </button>
              <button
                onClick={saveProjectSettings}
                disabled={savingProject || !projectForm.name.trim()}
                className="inline-flex items-center gap-2 rounded-2xl bg-black px-5 py-2.5 text-sm font-medium text-white shadow-[0_16px_30px_rgba(15,23,42,0.18)] transition-colors hover:bg-slate-800 disabled:opacity-50"
              >
                {savingProject && <Loader2 className="h-4 w-4 animate-spin" />}
                {savingProject ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {completionPrompt && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center px-4">
          <div className="absolute inset-0 bg-black/18 backdrop-blur-md" onClick={() => setCompletionPrompt(null)} />
          <div className="relative w-full max-w-lg rounded-[32px] border border-white/80 bg-white/78 p-6 shadow-[0_32px_90px_rgba(15,23,42,0.18)] backdrop-blur-2xl">
            <div className="flex items-start gap-4">
              <div className={`flex h-12 w-12 items-center justify-center rounded-2xl shadow-[0_18px_40px_rgba(15,23,42,0.12)] ${completionPrompt.type === 'error' ? 'bg-red-50 text-red-600' : 'bg-black text-white'}`}>
                {completionPrompt.type === 'error' ? <XCircle className="w-5 h-5" /> : <Check className="w-5 h-5" />}
              </div>
              <div className="flex-1">
                <p className="text-[11px] uppercase tracking-[0.22em] text-slate-400">
                  {completionPrompt.type === 'error' ? 'Needs Attention' : 'Ready To Review'}
                </p>
                <h3 className="mt-1 text-xl font-semibold text-slate-900">{completionPrompt.title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-500">{completionPrompt.text}</p>
              </div>
            </div>
            <div className="mt-6 flex items-center justify-end gap-3">
              <button
                onClick={() => setCompletionPrompt(null)}
                className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 shadow-[0_12px_30px_rgba(15,23,42,0.06)] transition hover:-translate-y-0.5 hover:shadow-[0_16px_36px_rgba(15,23,42,0.1)]"
              >
                Dismiss
              </button>
              <button
                onClick={() => {
                  setActiveTab('code');
                  setCompletionPrompt(null);
                }}
                className="rounded-full bg-black px-4 py-2 text-sm font-medium text-white shadow-[0_18px_40px_rgba(15,23,42,0.18)] transition hover:-translate-y-0.5 hover:shadow-[0_22px_48px_rgba(15,23,42,0.24)]"
              >
                Open Workspace
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
