import { useEffect, useRef, useState } from 'react';
import {
  ChevronDown, ChevronRight, ChevronLeft, Code2, ExternalLink, File, FileCode,
  FileJson, FileText, Folder, FolderOpen, Globe, Loader2,
  Maximize2, Minimize2, MessageSquare, Play, RefreshCw, RotateCcw, Save,
  Square, TerminalSquare, Wrench, X, AlertTriangle, Sparkles, PanelLeftOpen, Plus
} from 'lucide-react';
import ProjectChatPanel, { type CoderCustomization, type ExternalAgentRun } from './ProjectChatPanel';
import { CodeEditor } from './Editor';
import { Terminal } from './Terminal';
import type { AgentStreamEvent } from './AgentStepTimeline';

// Strip ANSI escape codes for clean text display
const stripAnsi = (str: string) =>
  str.replace(/\x1b\[[0-9;]*[A-Za-z]/g, '').replace(/\x1b\][^\x07]*\x07/g, '');

const API = 'http://localhost:8000/api';

// --- Types -------------------------------------------------------------------

type RuntimeState = {
  runtime_type?: string;
  run_command?: string | null;
  setup_command?: string | null;
  install_required?: boolean;
  preview_url?: string | null;
  ready?: boolean;
  preview_error?: string | null;
  process_id?: string;
  status?: {
    exists?: boolean; running?: boolean; command?: string;
    uptime_seconds?: number; backend?: string; container_name?: string;
  };
  secondary_statuses?: Array<{
    runtime_type?: string;
    run_command?: string | null;
    preview_url?: string | null;
    process_id?: string;
    status?: {
      exists?: boolean; running?: boolean; command?: string;
      uptime_seconds?: number; backend?: string; container_name?: string;
    };
  }>;
  sandbox?: { mode?: string; image?: string | null; runtime?: string | null; network?: string | null };
  heal?: {
    heal_type?: 'code_fix' | 'dependency';
    status?: 'agent_started' | 'agent_running' | 'rate_limited' | 'installing' | 'restarting' | 'restarted' | 'failed' | string;
    run_id?: string;
    module?: string;
    package?: string;
    message?: string;
    error?: string;
    healed?: boolean;
    files_modified?: string[];
    files_accessed?: string[];
    workspace_actions?: any[];
    tool_events?: any[];
    events?: AgentStreamEvent[];
    restarted?: boolean;
    updated_at?: number;
  };
};

type HealStatus = NonNullable<RuntimeState['heal']>;

const HEAL_ACTIVE_STATUSES = new Set(['agent_started', 'agent_running', 'installing', 'restarting']);
const HEAL_ERROR_STATUSES = new Set(['failed', 'agent_error', 'rate_limited', 'no_files_found', 'restart_failed', 'heal-rate-limit-exceeded']);

function isHealActive(heal: RuntimeState['heal'] | null | undefined) {
  return Boolean(heal?.status && HEAL_ACTIVE_STATUSES.has(heal.status));
}

function isHealError(heal: RuntimeState['heal'] | null | undefined) {
  return Boolean(heal?.status && HEAL_ERROR_STATUSES.has(heal.status));
}

function healStatusMessage(heal: RuntimeState['heal'] | null | undefined) {
  if (!heal) return '';
  const status = heal.status || '';
  const fileCount = heal.files_modified?.length ?? 0;
  const packageName = heal.package || heal.module;

  if (heal.heal_type === 'dependency') {
    if (status === 'installing') return 'Installing missing dependency';
    if (status === 'restarting') return packageName ? `Installed ${packageName}; restarting` : 'Dependency installed; restarting';
    if (status === 'restarted') return packageName ? `Installed ${packageName}; restarted` : 'Dependency installed; restarted';
    if (status === 'heal-rate-limit-exceeded' || status === 'rate_limited') return 'Dependency healing paused after repeated failures';
    if (status === 'failed') return packageName ? `Failed to install ${packageName}` : 'Dependency install failed';
    return heal.message || 'Checking runtime dependency';
  }

  if (status === 'agent_started' || status === 'agent_running') return 'AI fixing runtime code error';
  if (status === 'restarting') return fileCount ? `AI fixed ${fileCount} file${fileCount === 1 ? '' : 's'}; restarting` : 'AI fix applied; restarting';
  if (status === 'restarted') return fileCount ? `AI fixed ${fileCount} file${fileCount === 1 ? '' : 's'}; restarted` : 'AI fix applied; restarted';
  if (status === 'no_files_found') return 'Auto-fix could not find the failing project file';
  if (status === 'no_changes') return 'AI did not change files';
  if (status === 'rate_limited') return 'Auto-fix paused after repeated crashes';
  if (status === 'agent_error' || status === 'failed') return 'AI auto-fix failed';
  if (status === 'restart_failed') return 'Restart after auto-fix failed';
  return heal.message || 'Checking runtime error';
}

function healLogLine(heal: HealStatus) {
  const message = healStatusMessage(heal);
  const details: string[] = [];
  if (heal.files_modified?.length) details.push(`files: ${heal.files_modified.join(', ')}`);
  if (heal.package && heal.package !== heal.module) details.push(`package: ${heal.package}`);
  if (heal.error) details.push(`error: ${heal.error}`);
  return `[DevHub] ${message}${details.length ? ` (${details.join('; ')})` : ''}\n`;
}

function healAgentContent(heal: RuntimeState['heal'] | null | undefined) {
  if (!heal) return '';
  const fileCount = heal.files_modified?.length ?? 0;
  if (isHealActive(heal)) {
    return 'Runtime recovery is in progress. DevHub is inspecting the startup failure, applying a fix, and will restart the project automatically.';
  }
  if (heal.status === 'restarted') {
    return fileCount
      ? `Runtime recovery completed. DevHub updated ${fileCount} file${fileCount === 1 ? '' : 's'} and restarted the project automatically.`
      : 'Runtime recovery completed and the project restarted automatically.';
  }
  if (heal.status === 'restarting') {
    return fileCount
      ? `Runtime recovery applied a fix to ${fileCount} file${fileCount === 1 ? '' : 's'} and is restarting the project.`
      : 'Runtime recovery applied a fix and is restarting the project.';
  }
  if (heal.status === 'no_changes') {
    return 'Runtime recovery finished without applying a file change.';
  }
  return `Runtime recovery stopped. ${heal.error || heal.message || healStatusMessage(heal)}`.trim();
}

function buildRuntimeAgentRun(heal: RuntimeState['heal'] | null | undefined): ExternalAgentRun | null {
  if (!heal) return null;

  const filesAccessed = Array.isArray(heal.files_accessed) ? heal.files_accessed : [];
  const metadata = {
    approach: heal.heal_type === 'dependency'
      ? 'DevHub detected a missing dependency during startup, installed it, and restarted the runtime.'
      : 'DevHub traced the startup crash, reviewed the affected files, applied a patch, and restarted the runtime.',
    chat_mode: 'runtime_recovery',
    files_accessed: filesAccessed.map((path) => ({ path, reason: 'Read from the startup traceback context' })),
    workspace_actions: Array.isArray(heal.workspace_actions) ? heal.workspace_actions : [],
    applied_files: Array.isArray(heal.files_modified) ? heal.files_modified : [],
  };

  return {
    id: String(heal.run_id || heal.updated_at || `runtime-heal-${Date.now()}`),
    title: 'Runtime Recovery',
    content: healAgentContent(heal),
    active: isHealActive(heal),
    events: Array.isArray(heal.events) ? heal.events : [],
    metadata,
  };
}

type FileNode = {
  name: string;
  type: 'directory' | 'file';
  path: string;
  children?: FileNode[];
  loaded?: boolean;
};

type TerminalSession = {
  processId: string;
  command: string;
  title: string;
  output: string;
  running: boolean;
};

type AppOutputSession = {
  processId: string;
  title: string;
  output: string;
  running: boolean;
};

type Props = {
  workspaceId: string | null;
  projectId: string;
  projectName?: string;
  projectPath?: string | null;
  coderCustomization?: CoderCustomization | null;
  onProjectChanged?: () => void;
  projectSidebarCollapsed?: boolean;
  onToggleProjectSidebar?: () => void;
  isFullscreen?: boolean;
  onToggleFullscreen?: () => void;
  onRuntimeRunningChange?: (running: boolean) => void;
  autoRun?: boolean;
};

// --- File-icon helpers --------------------------------------------------------

const EXT_COLORS: Record<string, string> = {
  py: '#4ade80', ts: '#60a5fa', tsx: '#818cf8', js: '#fbbf24', jsx: '#f59e0b',
  css: '#a78bfa', scss: '#f472b6', html: '#fb923c', json: '#84cc16',
  md: '#94a3b8', rs: '#f97316', go: '#06b6d4', rb: '#ef4444',
  sh: '#22d3ee', yml: '#e879f9', yaml: '#e879f9', toml: '#fb923c',
  sql: '#60a5fa', graphql: '#e879f9', vue: '#34d399', svelte: '#f97316',
};

function FileIcon({ name, className = 'h-3.5 w-3.5 shrink-0' }: { name: string; className?: string }) {
  const ext = name.split('.').pop()?.toLowerCase() ?? '';
  const color = EXT_COLORS[ext] ?? '#6b7280';
  if (['json', 'toml', 'yaml', 'yml'].includes(ext)) return <FileJson className={className} style={{ color }} />;
  if (['md', 'txt', 'rst'].includes(ext)) return <FileText className={className} style={{ color }} />;
  if (ext) return <FileCode className={className} style={{ color }} />;
  return <File className={className} style={{ color: '#6b7280' }} />;
}

const getLanguage = (path: string | null) => {
  if (!path) return 'plaintext';
  if (path.endsWith('.py')) return 'python';
  if (path.endsWith('.ts') || path.endsWith('.tsx')) return 'typescript';
  if (path.endsWith('.js') || path.endsWith('.jsx')) return 'javascript';
  if (path.endsWith('.json')) return 'json';
  if (path.endsWith('.css') || path.endsWith('.scss')) return 'css';
  if (path.endsWith('.html')) return 'html';
  if (path.endsWith('.md')) return 'markdown';
  if (path.endsWith('.rs')) return 'rust';
  if (path.endsWith('.go')) return 'go';
  if (path.endsWith('.rb')) return 'ruby';
  if (path.endsWith('.sh')) return 'shell';
  return 'plaintext';
};

const normalizeNode = (item: any): FileNode => ({
  name: item.name, type: item.type, path: item.path,
  children: item.type === 'directory' ? [] : undefined,
  loaded: item.type === 'directory' ? false : undefined,
});

const looksLikeBackendCommand = (command: string) =>
  /\b(manage\.py|uvicorn|gunicorn|flask|fastapi|django|rails|php artisan|go run|cargo run)\b/i.test(command);

const looksLikeFrontendCommand = (command: string) =>
  /\b(vite|next|react-scripts|npm run dev|pnpm dev|yarn dev|webpack|astro|nuxt|ng serve)\b/i.test(command);

function runtimeOutputLabel(runtimeLike: { run_command?: string | null; runtime_type?: string }, index = 0, primary = false) {
  const command = String(runtimeLike.run_command || '');
  const runtimeType = String(runtimeLike.runtime_type || '').toLowerCase();
  if (looksLikeFrontendCommand(command)) return primary ? 'Frontend' : `Frontend ${index + 1}`;
  if (looksLikeBackendCommand(command)) return primary ? 'Backend' : `Backend ${index + 1}`;
  if (runtimeType === 'node') return primary ? 'Node App' : `Node App ${index + 1}`;
  if (runtimeType === 'python') return primary ? 'Python App' : `Python App ${index + 1}`;
  return primary ? 'App' : `App ${index + 1}`;
}

const insertChildren = (nodes: FileNode[], targetPath: string, children: FileNode[]): FileNode[] =>
  nodes.map((node) => {
    if (node.path === targetPath && node.type === 'directory') return { ...node, children, loaded: true };
    if (node.type === 'directory' && node.children)
      return { ...node, children: insertChildren(node.children, targetPath, children) };
    return node;
  });

const findNode = (nodes: FileNode[], targetPath: string): FileNode | null => {
  for (const node of nodes) {
    if (node.path === targetPath) return node;
    if (node.type === 'directory' && node.children?.length) {
      const match = findNode(node.children, targetPath);
      if (match) return match;
    }
  }
  return null;
};

// --- Drag-resize hook ---------------------------------------------------------

function useDragResize(
  initialPx: number, min: number, max: number,
  direction: 'h' | 'v' = 'h', invert = false,
) {
  const [size, setSize] = useState(initialPx);
  const [isDragging, setIsDragging] = useState(false);
  const dragging = useRef(false);
  const startPos = useRef(0);
  const startSize = useRef(initialPx);

  const onMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    setIsDragging(true);
    startPos.current = direction === 'h' ? e.clientX : e.clientY;
    startSize.current = size;
    const previousCursor = document.body.style.cursor;
    const previousUserSelect = document.body.style.userSelect;
    document.body.classList.add('workspace-resizing');
    document.body.style.cursor = direction === 'h' ? 'col-resize' : 'row-resize';
    document.body.style.userSelect = 'none';

    const onMove = (ev: MouseEvent) => {
      if (!dragging.current) return;
      ev.preventDefault();
      const raw = (direction === 'h' ? ev.clientX : ev.clientY) - startPos.current;
      const delta = invert ? -raw : raw;
      setSize(Math.min(max, Math.max(min, startSize.current + delta)));
    };
    const onUp = () => {
      dragging.current = false;
      setIsDragging(false);
      document.body.classList.remove('workspace-resizing');
      document.body.style.cursor = previousCursor;
      document.body.style.userSelect = previousUserSelect;
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      window.removeEventListener('blur', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    window.addEventListener('blur', onUp);
  };

  return { size, isDragging, onMouseDown };
}

// --- Main component -----------------------------------------------------------

export default function CodeWorkspace({
  workspaceId, projectId, projectName, projectPath, coderCustomization,
  onProjectChanged, projectSidebarCollapsed: _projectSidebarCollapsed, onToggleProjectSidebar,
  isFullscreen = false, onToggleFullscreen, onRuntimeRunningChange,
  autoRun = false,
}: Props) {
  const autoRunFiredRef = useRef(false);
  const [isInitializing, setIsInitializing] = useState(true);
  const [activeTab, setActiveTab] = useState<'preview' | 'code'>('preview');
  const [showConsole, setShowConsole] = useState(false);
  const [activeConsoleTab, setActiveConsoleTab] = useState<'terminal' | 'output'>('terminal');
  const [chatOpen, setChatOpen] = useState(true);
  const [treeNodes, setTreeNodes] = useState<FileNode[]>([]);
  const [expandedDirs, setExpandedDirs] = useState<string[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState('');
  const [saving, setSaving] = useState(false);
  const [runtime, setRuntime] = useState<RuntimeState | null>(null);
  const [runtimeLoading, setRuntimeLoading] = useState(false);
  const [startPhase, setStartPhase] = useState<'idle' | 'setup' | 'run' | 'healing'>('idle');
  const [runtimeOutput, setRuntimeOutput] = useState('');
  const [setupRunning, setSetupRunning] = useState(false);
  const [setupOutput, setSetupOutput] = useState('');
  const [previewRefreshKey, setPreviewRefreshKey] = useState(0);
  const [awaitingPreview, setAwaitingPreview] = useState(false);
  const [healStatus, setHealStatus] = useState<RuntimeState['heal'] | null>(null);
  const [runtimeAgentRun, setRuntimeAgentRun] = useState<ExternalAgentRun | null>(null);
  // When probe times out but server is running, user can force-open the iframe
  const [forcePreview, setForcePreview] = useState(false);
  const [previewLocation, setPreviewLocation] = useState('');
  const [terminalSessions, setTerminalSessions] = useState<TerminalSession[]>([]);
  const [activeTerminalPid, setActiveTerminalPid] = useState<string | null>(null);
  const [secondaryRuntimeOutputs, setSecondaryRuntimeOutputs] = useState<Record<string, string>>({});
  const [activeAppOutputPid, setActiveAppOutputPid] = useState<string | null>(null);
  const terminalRef = useRef<{ write: (data: string) => void; reset: (data?: string) => void; focus: () => void } | null>(null);
  const socketsRef = useRef<Record<string, WebSocket>>({});
  const lastHealEventRef = useRef<string | null>(null);

  const chatPanel   = useDragResize(560, 300, 760, 'h', true);
  const fileTree    = useDragResize(230, 150, 400, 'h');
  const consoleH    = useDragResize(220, 100, 500, 'v', true);
  const isResizing  = chatPanel.isDragging || fileTree.isDragging || consoleH.isDragging;

  const previewUrl       = runtime?.preview_url ?? null;
  // "truly ready" = probe succeeded; "force" = user bypassed the wait
  // If the process is running + has a URL, show the iframe - probe timeout is a backend network
  // limitation, the browser can always reach localhost directly.
  const previewAvailable = Boolean(runtime?.status?.running && previewUrl && (runtime?.ready || forcePreview || runtime?.preview_error));
  const previewTimedOut  = Boolean(runtime?.status?.running && previewUrl && !runtime?.ready && runtime?.preview_error && !forcePreview);
  const previewPending   = Boolean(runtime?.status?.running && previewUrl && !runtime?.ready && !runtime?.preview_error && !forcePreview);
  const needsSetup       = Boolean(!runtime?.status?.running && runtime?.setup_command && runtime?.install_required);
  const runtimeBackend   = runtime?.status?.backend || runtime?.sandbox?.mode || 'local';
  const previewPort      = previewUrl ? (() => { try { return new URL(previewUrl).port; } catch { return null; } })() : null;
  const isRunning        = Boolean(runtime?.status?.running);
  const setupRunning_    = setupRunning;
  const healActive       = isHealActive(healStatus);
  const healProblem      = isHealError(healStatus);
  const healSummary      = healStatusMessage(healStatus);
  const secondaryStatuses = Array.isArray(runtime?.secondary_statuses) ? runtime.secondary_statuses : [];
  const effectivePreviewUrl = previewLocation || previewUrl || '';
  const activeTerminalSession = terminalSessions.find((session) => session.processId === activeTerminalPid) || terminalSessions[0] || null;
  const appOutputSessions: AppOutputSession[] = [
    ...(runtime?.process_id ? [{
      processId: runtime.process_id,
      title: runtimeOutputLabel(runtime, 0, true),
      output: runtimeOutput,
      running: Boolean(runtime?.status?.running),
    }] : []),
    ...secondaryStatuses
      .filter((item) => item?.process_id)
      .map((item, index) => ({
        processId: String(item.process_id),
        title: runtimeOutputLabel(item, index, false),
        output: secondaryRuntimeOutputs[String(item.process_id)] || '',
        running: Boolean(item.status?.running),
      })),
    ...(workspaceId && (setupOutput || setupRunning_) ? [{
      processId: `${workspaceId}_setup`,
      title: 'Setup',
      output: setupOutput,
      running: setupRunning_,
    }] : []),
  ];
  const activeAppOutput = appOutputSessions.find((item) => item.processId === activeAppOutputPid) || appOutputSessions[0] || null;

  const startLabel = healActive
    ? 'Healing...'
    : runtimeLoading
    ? (startPhase === 'setup' ? 'Installing deps...' : startPhase === 'healing' ? 'AI fixing...' : 'Starting...')
    : needsSetup ? 'Setup & Run'
    : runtime?.run_command ? 'Start'
    : 'No command';

  useEffect(() => {
    const timer = setTimeout(() => setIsInitializing(false), 1200);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!previewUrl) {
      setPreviewLocation('');
      return;
    }
    setPreviewLocation((current) => {
      if (!current) return previewUrl;
      try {
        const currentUrl = new URL(current);
        const baseUrl = new URL(previewUrl);
        if (currentUrl.origin !== baseUrl.origin) return previewUrl;
        return current;
      } catch {
        return previewUrl;
      }
    });
  }, [previewUrl]);

  useEffect(() => {
    if (!appOutputSessions.length) {
      setActiveAppOutputPid(null);
      return;
    }
    if (!activeAppOutputPid || !appOutputSessions.some((item) => item.processId === activeAppOutputPid)) {
      setActiveAppOutputPid(appOutputSessions[0].processId);
    }
  }, [activeAppOutputPid, appOutputSessions]);

  // -- API helpers --------------------------------------------------------------

  const fetchDir = async (path = '') => {
    if (!workspaceId) return [];
    const r = await fetch(`${API}/workspace/${workspaceId}/fs/?path=${encodeURIComponent(path)}`);
    const d = await r.json();
    return d.type === 'directory' ? (d.items ?? []).map(normalizeNode) : [];
  };

  const refreshTree = async () => {
    if (!workspaceId) return;
    let snap = await fetchDir('');
    for (const p of [...expandedDirs].sort((a, b) => a.split('/').length - b.split('/').length)) {
      try { snap = insertChildren(snap, p, await fetchDir(p)); } catch {}
    }
    setTreeNodes(snap);
  };

  const applyHealStatus = (heal: RuntimeState['heal'] | null | undefined) => {
    if (!heal) return false;

    const active = isHealActive(heal);
    setHealStatus(heal);
    setRuntimeAgentRun(buildRuntimeAgentRun(heal));
    if (active) {
      setStartPhase('healing');
      setAwaitingPreview(false);
      setActiveTab('preview');
      setChatOpen(true);
    } else if (heal.status === 'restarted') {
      setStartPhase('run');
      setPreviewRefreshKey((c) => c + 1);
      if (heal.files_modified?.length) {
        void refreshTree();
        onProjectChanged?.();
      }
    } else {
      setStartPhase((current) => (current === 'healing' ? 'idle' : current));
    }

    const key = [
      heal.heal_type,
      heal.status,
      heal.module,
      heal.package,
      heal.restarted ? 'restarted' : '',
      heal.files_modified?.join('|') || '',
      heal.error || '',
    ].join(':');
    if (key !== lastHealEventRef.current) {
      lastHealEventRef.current = key;
      setRuntimeOutput((current) => `${current}${current && !current.endsWith('\n') ? '\n' : ''}${healLogLine(heal)}`);
    }
    return active;
  };

  const fetchRuntime = async () => {
    if (!workspaceId) return null;
    const r = await fetch(`${API}/workspace/${workspaceId}/runtime/`);
    const d = await r.json();
    setRuntime(d);
    onRuntimeRunningChange?.(Boolean(d?.status?.running));
    if (d?.heal) {
      applyHealStatus(d.heal);
    } else if (healStatus && d?.status?.running) {
      setHealStatus(null);
      lastHealEventRef.current = null;
      setStartPhase('idle');
    }
    return d as RuntimeState;
  };

  // Auto-start the project once for newly scaffolded starter projects.
  // Fires only on the first successful runtime fetch that has a run_command.
  useEffect(() => {
    if (!autoRun || autoRunFiredRef.current || !runtime?.run_command || runtime?.status?.running) return;
    autoRunFiredRef.current = true;
    void runProject();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRun, runtime]);

  const fetchSetupStatus = async () => {
    if (!workspaceId) return null;
    const r = await fetch(`${API}/workspace/${workspaceId}/setup/`);
    const d = await r.json();
    if (d?.status && !d.status.running) setSetupRunning(false);
    return d;
  };

  const fetchSetupOutput = async () => {
    if (!workspaceId) return null;
    const pid = `${workspaceId}_setup`;
    const r = await fetch(`${API}/workspace/${workspaceId}/process/${encodeURIComponent(pid)}/`);
    const d = await r.json();
    if (d?.output) setSetupOutput((c) => c + d.output);
    if (d?.status && !d.status.running) { setSetupRunning(false); void fetchRuntime(); }
    return d;
  };

  const startSetup = async ({ resetOutput = true } = {}) => {
    if (!workspaceId) return null;
    setSetupRunning(true);
    if (resetOutput) setSetupOutput('');
    setShowConsole(true);
    setActiveConsoleTab('output');
    const r = await fetch(`${API}/workspace/${workspaceId}/setup/`, { method: 'POST' });
    const d = await r.json();
    if (!r.ok || d?.error) { setSetupRunning(false); throw new Error(d?.error || 'Setup failed.'); }
    return d;
  };

  const waitForSetup = async (ms = 120_000) => {
    const deadline = Date.now() + ms;
    while (Date.now() < deadline) {
      const d = await fetchSetupStatus();
      if (!d?.status?.running) return d;
      await new Promise((res) => setTimeout(res, 900));
    }
    return null;
  };

  // -- Effects ------------------------------------------------------------------

  useEffect(() => {
    if (!workspaceId) return;
    void refreshTree();
    void fetchRuntime();
  }, [workspaceId, projectId]);

  useEffect(() => {
    if (!workspaceId) return;
    const healing = startPhase === 'healing' || healActive;
    const active = runtimeLoading || setupRunning_ || awaitingPreview || previewPending || healing;
    const delay  = active ? 1500 : isRunning ? 15000 : 30000;
    const t = window.setTimeout(() => void fetchRuntime(), delay);
    return () => window.clearTimeout(t);
  }, [workspaceId, runtimeLoading, setupRunning_, awaitingPreview, previewPending, isRunning, startPhase, healActive, healStatus]);

  useEffect(() => {
    if (!workspaceId || !setupRunning_) return;
    const t = window.setTimeout(async () => {
      await fetchSetupOutput(); await fetchSetupStatus();
    }, 1000);
    return () => window.clearTimeout(t);
  }, [workspaceId, setupRunning_, setupOutput]);

  useEffect(() => () => {
    Object.values(socketsRef.current).forEach((s) => s.close());
    socketsRef.current = {};
  }, []);

  // Once truly ready, switch to preview
  useEffect(() => {
    if (!isRunning) { setAwaitingPreview(false); return; }
    if (awaitingPreview && previewAvailable) {
      setActiveTab('preview');
      setAwaitingPreview(false);
    }
  }, [awaitingPreview, previewAvailable, isRunning]);

  // Reset force-preview when runtime stops
  useEffect(() => {
    if (!isRunning) setForcePreview(false);
  }, [isRunning]);

  // Auto-refresh iframe when probe finally passes after forcePreview was used
  const prevReadyRef = useRef<boolean>(false);
  useEffect(() => {
    const nowReady = Boolean(runtime?.ready);
    if (nowReady && !prevReadyRef.current && forcePreview) {
      setPreviewRefreshKey((c) => c + 1);
    }
    prevReadyRef.current = nowReady;
  }, [runtime?.ready, forcePreview]);

  // -- File ops -----------------------------------------------------------------

  const loadFile = async (path: string) => {
    if (!workspaceId) return;
    setSelectedFile(path);
    const r = await fetch(`${API}/workspace/${workspaceId}/fs/?path=${encodeURIComponent(path)}`);
    const d = await r.json();
    if (d.type === 'file') { setFileContent(d.content); setActiveTab('code'); }
  };

  const saveFile = async () => {
    if (!workspaceId || !selectedFile) return;
    setSaving(true);
    await fetch(`${API}/workspace/${workspaceId}/fs/`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: selectedFile, content: fileContent }),
    });
    setSaving(false);
    refreshTree();
    onProjectChanged?.();
  };

  const toggleDir = async (path: string) => {
    if (expandedDirs.includes(path)) { setExpandedDirs((c) => c.filter((p) => p !== path)); return; }
    setExpandedDirs((c) => [...c, path]);
    if (findNode(treeNodes, path)?.loaded) return;
    const children = await fetchDir(path);
    setTreeNodes((c) => insertChildren(c, path, children));
  };

  // -- Terminal -----------------------------------------------------------------

  const spawnTerm = async (command = 'cmd.exe') => {
    if (!workspaceId) return null;
    const r = await fetch(`${API}/workspace/${workspaceId}/spawn/`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command }),
    });
    const d = await r.json();
    if (!r.ok || d?.error || !d?.process_id) throw new Error(d?.error || 'Unable to open a terminal.');
    const processId = String(d.process_id);
    setTerminalSessions((current) => {
      if (current.some((session) => session.processId === processId)) return current;
      return [
        ...current,
        {
          processId,
          command: String(d.command || command),
          title: `Terminal ${current.length + 1}`,
          output: '',
          running: true,
        },
      ];
    });
    setActiveTerminalPid(processId);
    setShowConsole(true);
    setActiveConsoleTab('terminal');
    return processId;
  };

  const closeTerm = async (processId: string) => {
    if (!workspaceId) return;
    try {
      await fetch(`${API}/workspace/${workspaceId}/process/${encodeURIComponent(processId)}/`, { method: 'DELETE' });
    } finally {
      socketsRef.current[processId]?.close();
      delete socketsRef.current[processId];
      setTerminalSessions((current) => current.filter((session) => session.processId !== processId));
      setActiveTerminalPid((current) => (current === processId ? null : current));
    }
  };

  useEffect(() => {
    terminalRef.current?.reset('');
    setTerminalSessions([]);
    setActiveTerminalPid(null);
    setSecondaryRuntimeOutputs({});
    setActiveAppOutputPid(null);
    Object.values(socketsRef.current).forEach((socket) => socket.close());
    socketsRef.current = {};
  }, [workspaceId]);

  useEffect(() => {
    if (!workspaceId || terminalSessions.length) return;
    void spawnTerm().catch(() => {});
  }, [workspaceId, terminalSessions.length]);

  useEffect(() => {
    if (!terminalSessions.length) {
      if (activeTerminalPid) setActiveTerminalPid(null);
      return;
    }
    if (!activeTerminalPid || !terminalSessions.some((session) => session.processId === activeTerminalPid)) {
      setActiveTerminalPid(terminalSessions[0].processId);
    }
  }, [activeTerminalPid, terminalSessions]);

  const connectSocket = (pid: string, onMsg: (d: any) => void) => {
    if (!workspaceId || socketsRef.current[pid]) return;
    const ws = new WebSocket(`ws://localhost:8000/ws/workspace/${workspaceId}/process/${pid}/`);
    ws.onmessage = (ev) => onMsg(JSON.parse(ev.data));
    ws.onclose   = () => { delete socketsRef.current[pid]; };
    socketsRef.current[pid] = ws;
  };

  useEffect(() => {
    terminalSessions.forEach((session) => {
      connectSocket(session.processId, (d) => {
        if (!d.output && !d.status) return;
        setTerminalSessions((current) => current.map((item) => (
          item.processId === session.processId
            ? {
                ...item,
                output: d.output ? `${item.output}${d.output}` : item.output,
                running: d.status?.running ?? item.running,
              }
            : item
        )));
      });
    });
    if (runtime?.process_id && isRunning)
      connectSocket(runtime.process_id, (d) => {
        if (d.output) setRuntimeOutput((c) => c + d.output);
        if (d.status) setRuntime((c) => c ? { ...c, status: d.status } : null);
      });
    secondaryStatuses.forEach((secondary) => {
      if (!secondary.process_id || !secondary.status?.running) return;
      connectSocket(String(secondary.process_id), (d) => {
        if (d.output) {
          setSecondaryRuntimeOutputs((current) => ({
            ...current,
            [String(secondary.process_id)]: `${current[String(secondary.process_id)] || ''}${d.output}`,
          }));
        }
      });
    });
    if (setupRunning_ && workspaceId)
      connectSocket(`${workspaceId}_setup`, (d) => {
        if (d.output) setSetupOutput((c) => c + d.output);
        if (d.status && !d.status.running) { setSetupRunning(false); void fetchRuntime(); }
      });
  }, [workspaceId, terminalSessions, runtime?.process_id, isRunning, setupRunning_, secondaryStatuses]);

  const termInput = (data: string) => {
    if (activeTerminalPid && socketsRef.current[activeTerminalPid]?.readyState === WebSocket.OPEN)
      socketsRef.current[activeTerminalPid].send(JSON.stringify({ input: data }));
  };

  useEffect(() => {
    if (!showConsole || activeConsoleTab !== 'terminal' || !activeTerminalSession) return;
    const timer = window.setTimeout(() => terminalRef.current?.focus(), 0);
    return () => window.clearTimeout(timer);
  }, [activeConsoleTab, activeTerminalSession, showConsole]);

  const updatePreviewLocation = (nextValue: string) => {
    setPreviewLocation(nextValue);
  };

  const applyPreviewLocation = () => {
    if (!previewUrl) return;
    const nextValue = (previewLocation || '').trim();
    if (!nextValue) {
      setPreviewLocation(previewUrl);
      return;
    }
    try {
      const baseUrl = new URL(previewUrl);
      const nextUrl = new URL(nextValue, baseUrl);
      if (nextUrl.origin !== baseUrl.origin) {
        setPreviewLocation(baseUrl.toString());
        return;
      }
      setPreviewLocation(nextUrl.toString());
      setPreviewRefreshKey((current) => current + 1);
    } catch {
      setPreviewLocation(previewUrl);
    }
  };

  // -- Runtime controls ---------------------------------------------------------

  const runProject = async () => {
    if (!workspaceId) return;
    let keepHealingPhase = false;
    setRuntimeLoading(true);
    setStartPhase(needsSetup ? 'setup' : 'run');
    setHealStatus(null);
    setRuntimeAgentRun(null);
    lastHealEventRef.current = null;
    setRuntimeOutput('');
    setSecondaryRuntimeOutputs({});
    setShowConsole(true);
    setActiveConsoleTab('output');
    try {
      if (needsSetup) {
        setSetupOutput('Installing dependencies before launch...\n');
        await startSetup({ resetOutput: false });
        const s = await waitForSetup();
        if (!s) { setRuntimeOutput('Setup timed out. Check the output panel.'); return; }
        const r = await fetchRuntime();
        if (r?.install_required) { setRuntimeOutput('Dependencies still missing. Review output and retry.'); return; }
      }
      setStartPhase('run');
      setAwaitingPreview(true);
      setRuntimeOutput('Starting project...\n');
      const res  = await fetch(`${API}/workspace/${workspaceId}/runtime/`, { method: 'POST' });
      const data = await res.json();
      if (!res.ok || data?.error) throw new Error(data?.error || 'Unable to start the project.');
      setRuntime(data);
      if (data.preview_error) setRuntimeOutput((c) => `${c}\n${data.preview_error}`);
      if (data.heal) keepHealingPhase = applyHealStatus(data.heal);
      if (data.ready || forcePreview) { setActiveTab('preview'); setAwaitingPreview(false); }
      else if (data?.status?.running && data.preview_url) setActiveTab('preview');
    } catch (e) {
      setRuntimeOutput(e instanceof Error ? e.message : 'Unable to start the project.');
      setAwaitingPreview(false);
    } finally {
      setRuntimeLoading(false);
      if (!keepHealingPhase) setStartPhase('idle');
    }
  };

  const stopProject = async () => {
    if (!workspaceId) return;
    await fetch(`${API}/workspace/${workspaceId}/runtime/`, { method: 'DELETE' });
    onRuntimeRunningChange?.(false);
    setAwaitingPreview(false);
    setForcePreview(false);
    setHealStatus(null);
    setRuntimeAgentRun(null);
    lastHealEventRef.current = null;
    setSecondaryRuntimeOutputs({});
    void fetchRuntime();
  };

  const restartProject = async () => {
    if (!workspaceId) return;
    if (isRunning) { await stopProject(); await new Promise((r) => setTimeout(r, 450)); }
    await runProject();
  };

  const handleCodeApplied = async (files: string[]) => {
    await refreshTree();
    void fetchRuntime();
    onProjectChanged?.();
    if (selectedFile && files.includes(selectedFile)) void loadFile(selectedFile);
    else if (files.length > 0) void loadFile(files[0]);
    if (isRunning) setPreviewRefreshKey((c) => c + 1);
  };

  const handleAgentAction = async (actions: any[]) => {
    if (!Array.isArray(actions) || !actions.length) return;
    setShowConsole(true);
    setActiveConsoleTab('output');
    const types = new Set(actions.map((a) => String(a?.type || '')));
    if ([...types].some((t) => t === 'setup' || t === 'terminal_command')) await refreshTree();
    if ([...types].some((t) => t.startsWith('runtime_') || t === 'setup')) {
      const next = await fetchRuntime();
      await fetchSetupStatus();
      if (types.has('runtime_stop')) setAwaitingPreview(false);
      if ((types.has('runtime_start') || types.has('runtime_restart')) && next?.preview_url) {
        setAwaitingPreview(!next.ready);
        if (next.ready) { setActiveTab('preview'); setPreviewRefreshKey((c) => c + 1); }
      }
    }
  };

  // -- File tree -----------------------------------------------------------------

  const renderNode = (node: FileNode, depth = 0): any => (
    <div key={node.path}>
      <button
        type="button"
        onClick={() => node.type === 'directory' ? toggleDir(node.path) : loadFile(node.path)}
        className={`group flex w-full items-center gap-1.5 rounded-md py-[3px] pr-3 text-left text-[12px] transition-colors ${
          selectedFile === node.path
            ? 'bg-[#2b1d22] text-[#d9a4b2]'
            : 'text-[#a6a6a0] hover:bg-white/10 hover:text-white'
        }`}
        style={{ paddingLeft: `${10 + depth * 13}px` }}
      >
        {node.type === 'directory'
          ? expandedDirs.includes(node.path)
            ? <ChevronDown className="h-3 w-3 shrink-0 text-[#858585]" />
            : <ChevronRight className="h-3 w-3 shrink-0 text-[#858585]" />
          : <span className="h-3 w-3 shrink-0" />}
        {node.type === 'directory'
          ? expandedDirs.includes(node.path)
            ? <FolderOpen className="h-3.5 w-3.5 shrink-0 text-[#fbbf24]" />
            : <Folder className="h-3.5 w-3.5 shrink-0 text-[#fbbf24]/70" />
          : <FileIcon name={node.name} />}
        <span className="truncate leading-none">{node.name}</span>
      </button>
      {node.type === 'directory' && expandedDirs.includes(node.path) && (
        node.children?.length
          ? node.children.map((c) => renderNode(c, depth + 1))
          : <div className="py-1 text-[10px] italic text-[#4a4a65]" style={{ paddingLeft: `${28 + depth * 13}px` }}>Empty</div>
      )}
    </div>
  );

  // -- No workspace fallback -----------------------------------------------------

  if (!workspaceId) {
    return (
      <div className="flex h-full items-center justify-center rounded-xl bg-[#252526] text-center">
        <div className="px-8 py-12">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-[#3c3c3c] text-[#d9a4b2]">
            <Code2 className="h-7 w-7" />
          </div>
          <p className="text-sm font-medium text-[#d4d4d4]">No active workspace</p>
          <p className="mt-1.5 text-xs text-[#858585]">Connect a project folder to start coding.</p>
        </div>
      </div>
    );
  }

  // --- Render -------------------------------------------------------------------
  if (isInitializing) {
    return (
      <div className="devhub-loading-screen flex h-full w-full items-center justify-center sleek-tab-enter">
        <div className="flex flex-col items-center gap-6">
          <div className="relative flex h-20 w-20 items-center justify-center">
            <div className="absolute inset-0 rounded-full" style={{ border: '2px solid rgba(140,84,98,0.12)' }} />
            <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-[#8c5462] animate-spin" />
            <div className="devhub-loading-icon-bg flex h-14 w-14 items-center justify-center rounded-2xl shadow-2xl">
              <Code2 className="h-7 w-7 text-[#8c5462] animate-pulse" />
            </div>
          </div>
          <div className="text-center">
            <h3 className="devhub-loading-title text-sm font-semibold tracking-wide">Initializing IDE</h3>
            <p className="devhub-loading-subtitle mt-1.5 text-[11px] uppercase tracking-widest font-medium">Mounting Workspace Environment</p>
          </div>
          <div className="devhub-loading-track w-32 h-1 overflow-hidden rounded-full">
            <div className="h-full bg-gradient-to-r from-[#8c5462] to-[#d9a4b2] animate-[loader-bar-indeterminate_1.5s_infinite]" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`devhub-workspace flex h-full w-full min-h-0 min-w-0 overflow-hidden bg-[#0a0a0c] text-[#e8e8e3] sleek-tab-enter ${
        isFullscreen ? '' : 'border-white/10'
      }`}
      style={{ userSelect: isResizing ? 'none' : undefined }}
    >

      {/* == LEFT: Content area ================================================ */}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col bg-[#0a0a0c]">

        {/* Tab strip - sits at top of content area only */}
        <div className="flex h-12 shrink-0 items-center justify-between border-b border-white/10 bg-[#111111] px-3">
          {/* Left: chat toggle + view tabs */}
          <div className="flex items-center gap-0.5">
                        <button
              onClick={() => setActiveTab('preview')}
              className={`flex h-7 items-center gap-1.5 rounded-md px-3 text-[11px] font-medium transition-colors ${
                activeTab === 'preview'
                  ? 'border border-[#8c5462] bg-[#2b1d22] text-[#d9a4b2]'
                  : 'text-[#a6a6a0] hover:bg-white/10 hover:text-white'
              }`}
            >
              <Globe className="h-3.5 w-3.5" />
              Preview
              {previewPending && <Loader2 className="ml-0.5 h-3 w-3 animate-spin text-[#d9a4b2]" />}
              {previewTimedOut && !forcePreview && <AlertTriangle className="ml-0.5 h-3 w-3 text-[#fbbf24]" />}
            </button>
            <button
              onClick={() => setActiveTab('code')}
              className={`flex h-7 items-center gap-1.5 rounded-md px-3 text-[11px] font-medium transition-colors ${
                activeTab === 'code'
                  ? 'border border-[#8c5462] bg-[#2b1d22] text-[#d9a4b2]'
                  : 'text-[#a6a6a0] hover:bg-white/10 hover:text-white'
              }`}
            >
              <Code2 className="h-3.5 w-3.5" />
              Code
            </button>
            <button
              onClick={() => setShowConsole((v) => !v)}
              className={`flex h-7 items-center gap-1.5 rounded-md px-3 text-[11px] font-medium transition-colors ${
                showConsole
                  ? 'bg-white/10 text-white'
                  : 'text-[#a6a6a0] hover:bg-white/10 hover:text-white'
              }`}
            >
              <TerminalSquare className="h-3.5 w-3.5" />
              Console
              {(setupRunning_ || runtimeLoading || healActive) && (
                <span className="ml-0.5 h-1.5 w-1.5 rounded-full bg-[#fbbf24] animate-pulse" />
              )}
            </button>
          </div>

          <div className="flex min-w-0 flex-1 items-center justify-end gap-2 pl-3">
            {healStatus && healSummary && (
              <div
                className={`flex min-w-0 max-w-[360px] items-center gap-1.5 rounded-full border px-3 py-1.5 text-[10px] font-semibold ${
                  healProblem
                    ? 'border-[#f87171]/25 bg-[#2a1717] text-[#fca5a5]'
                    : healActive
                      ? 'border-[#8c5462]/35 bg-[#2b1d22] text-[#d9a4b2]'
                      : 'border-[#34d399]/20 bg-[#10251b] text-[#86efac]'
                }`}
                title={healSummary}
              >
                {healActive ? (
                  <Loader2 className="h-3 w-3 shrink-0 animate-spin" />
                ) : healProblem ? (
                  <AlertTriangle className="h-3 w-3 shrink-0" />
                ) : (
                  <Wrench className="h-3 w-3 shrink-0" />
                )}
                <span className="truncate">{healSummary}</span>
              </div>
            )}

            {/* Stop button — visible whenever project is running */}
            {isRunning && (
              <button
                onClick={() => void stopProject()}
                disabled={runtimeLoading}
                className="flex h-7 items-center gap-1.5 rounded-md border border-[#3a2a30] bg-[#1f1a1d] px-2.5 text-[11px] font-medium text-[#f87171] transition-colors hover:border-[#f87171]/40 hover:bg-[#2a1717] disabled:opacity-40"
                title="Stop project"
              >
                <Square className="h-3 w-3 fill-[#f87171]" />
                Stop
              </button>
            )}

            {/* Right: preview URL bar (when preview active) */}
            {activeTab === 'preview' && previewAvailable && previewUrl && (
              <div className="flex items-center gap-1">
                <div className="flex max-w-[360px] items-center gap-1.5 rounded-full border border-white/10 bg-[#0a0a0c] px-3 py-1.5 text-[10px] font-mono text-[#a6a6a0]">
                  <Globe className="h-3 w-3 shrink-0 text-[#d9a4b2]" />
                  <input
                    value={previewLocation.replace(/^https?:\/\//, '')}
                    onChange={(event) => updatePreviewLocation(`${previewUrl?.startsWith('https://') ? 'https://' : 'http://'}${event.target.value}`)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') {
                        event.preventDefault();
                        applyPreviewLocation();
                      }
                    }}
                    className="min-w-0 flex-1 bg-transparent outline-none"
                    spellCheck={false}
                  />
                </div>
                <button
                  onClick={() => setPreviewRefreshKey((c) => c + 1)}
                  className="flex h-7 w-7 items-center justify-center rounded-md text-[#a6a6a0] transition-colors hover:bg-white/10 hover:text-white"
                  title="Reload preview"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                </button>
                <button
                  onClick={() => window.open(effectivePreviewUrl || previewUrl, '_blank')}
                  className="flex h-7 w-7 items-center justify-center rounded-md text-[#a6a6a0] transition-colors hover:bg-white/10 hover:text-white"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Main + (optional) file tree */}
        <div className="flex min-h-0 min-w-0 flex-1 flex-row">

          {/* File tree (Code tab only) */}
          {activeTab === 'code' && (
            <>
              <div
                className="flex shrink-0 flex-col border-r border-white/10 bg-[#111111]"
                style={{ width: fileTree.size, minWidth: 0 }}
              >
                <div className="flex h-9 shrink-0 items-center justify-between border-b border-white/10 px-3">
                  <span className="text-[10px] font-semibold uppercase tracking-widest text-[#75756f]">Files</span>
                  <button
                    onClick={() => void refreshTree()}
                    className="rounded p-1 text-[#75756f] transition-colors hover:bg-white/10 hover:text-white"
                  >
                    <RefreshCw className="h-3 w-3" />
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto px-1 py-1" style={{ minHeight: 0 }}>
                  {treeNodes.length
                    ? treeNodes.map((n) => renderNode(n))
                    : <p className="mt-6 text-center text-[11px] italic text-[#555555]">Loading...</p>}
                </div>
              </div>
              <div
                className="group relative w-[3px] shrink-0 cursor-col-resize bg-[#0a0a0c] transition-colors hover:bg-[#8c5462]/60"
                onMouseDown={fileTree.onMouseDown}
              />
            </>
          )}

          {/* Editor / Preview column */}
          <div className="flex min-h-0 min-w-0 flex-1 flex-col">

            {/* Tab content */}
            <div className="relative min-h-0 flex-1 overflow-hidden">

              {/* -- PREVIEW -- */}
              {activeTab === 'preview' && (
                <>
                  {/* Running + available (probe passed or forced) */}
                  {isRunning && previewUrl && previewAvailable && (
                    <div className="absolute inset-0 bg-[#0a0a0c] p-0">
                      <div className="relative h-full w-full overflow-hidden border-white/10 bg-[#f7f7f3] shadow-[0_24px_80px_rgba(0,0,0,0.38)]">
                        <iframe
                          key={`${runtime?.process_id}-${previewRefreshKey}`}
                          src={effectivePreviewUrl || previewUrl || undefined}
                          className="h-full w-full border-0"
                          style={{ pointerEvents: isResizing ? 'none' : 'auto' }}
                          title="Live Preview"
                        />
                        {isResizing && <div className="absolute inset-0 z-10 bg-transparent" />}
                      </div>
                    </div>
                  )}

                  {/* Running + probe timed out - show error + escape hatch, or AI healing banner */}
                  {isRunning && previewUrl && previewTimedOut && !forcePreview && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center gap-5 border-white/10 bg-[#151515] text-center">
                      {healActive ? (
                        <>
                          <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-[#8c5462]/25 bg-[#2b1d22]">
                            <Loader2 className="h-6 w-6 animate-spin text-[#d9a4b2]" />
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-[#d4d4d4]">{healSummary || 'Healing runtime error'}</p>
                            <p className="mt-1.5 max-w-xs text-xs leading-5 text-[#858585]">
                              DevHub is repairing the crashed startup path and will restart automatically.
                            </p>
                          </div>
                          <button
                            onClick={() => setShowConsole(true)}
                            className="text-[11px] text-[#858585] underline underline-offset-2 transition-colors hover:text-[#d9a4b2]"
                          >
                            View output
                          </button>
                        </>
                      ) : (
                        <>
                          <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-[#fbbf24]/20 bg-[#2d2000]">
                            <AlertTriangle className="h-6 w-6 text-[#fbbf24]" />
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-[#d4d4d4]">Preview probe timed out</p>
                            <p className="mt-1.5 max-w-xs text-xs leading-5 text-[#858585]">
                              {runtime?.preview_error}<br />
                              The server may still be starting - try opening it anyway.
                            </p>
                          </div>
                          <div className="flex gap-2">
                            <button
                              onClick={() => { setForcePreview(true); }}
                              className="flex items-center gap-1.5 rounded-lg bg-[#8c5462] px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-[#70434f]"
                            >
                              <Globe className="h-3.5 w-3.5" />
                              Open preview anyway
                            </button>
                            <button
                              onClick={() => void restartProject()}
                              disabled={runtimeLoading}
                              className="flex items-center gap-1.5 rounded-lg border border-[#3a2a30] bg-[#1f1a1d] px-4 py-2 text-xs font-semibold text-[#b9adb1] transition-colors hover:border-[#70434f] hover:text-[#f5eef1] disabled:opacity-40"
                            >
                              <RotateCcw className="h-3.5 w-3.5" />
                              Restart
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  )}

                  {/* Running + waiting for probe */}
                  {isRunning && previewUrl && previewPending && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 border-white/10 bg-[#151515] text-center">
                      <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-[#8c5462]/25 bg-[#2b1d22]">
                        <Loader2 className="h-6 w-6 animate-spin text-[#d9a4b2]" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-[#9d9d9d]">Preview warming up</p>
                        <p className="mt-1.5 text-xs text-[#6b6b6b]">Waiting for the server to respond...</p>
                      </div>
                      <button
                        onClick={() => { setForcePreview(true); setActiveTab('preview'); }}
                        className="text-[11px] text-[#858585] underline underline-offset-2 transition-colors hover:text-[#d9a4b2]"
                      >
                        Open anyway
                      </button>
                    </div>
                  )}

                  {/* Not running */}
                  {!isRunning && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center gap-5 border-white/10 bg-[#151515] text-center">
                      <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-white/10 bg-white/5">
                        <Globe className="h-7 w-7 text-[#75756f]" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-[#e8e8e3]">
                          {healStatus && healSummary
                            ? (healSummary || 'Healing runtime error')
                            : runtime?.run_command ? 'Project not running' : 'No run command detected'}
                        </p>
                        <p className="mt-1.5 max-w-xs text-xs leading-5 text-[#a6a6a0]">
                          {healActive
                            ? 'DevHub is repairing the startup error and will restart the project automatically.'
                            : healProblem
                              ? (healStatus?.error || healStatus?.message || 'Auto-heal stopped. Review the output and retry.')
                            : runtime?.run_command
                              ? 'Hit Start in the chat panel to launch your app.'
                              : 'Add a start script or run a command from the Console tab.'}
                        </p>
                      </div>
                      {runtime?.run_command && !healActive && (
                        <button
                          onClick={() => void runProject()}
                          disabled={runtimeLoading}
                          className="flex items-center gap-2 rounded-lg bg-[#8c5462] px-4 py-2 text-xs font-semibold text-white shadow-sm shadow-[#70434f]/20 transition-all hover:bg-[#70434f] disabled:opacity-40"
                        >
                          {runtimeLoading
                            ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            : startPhase === 'healing'
                              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              : <Play className="h-3.5 w-3.5 fill-white" />}
                          {runtimeLoading || startPhase === 'healing' ? startLabel : 'Start Project'}
                        </button>
                      )}
                    </div>
                  )}
                </>
              )}

              {/* -- CODE -- */}
              {activeTab === 'code' && (
                <div className="absolute inset-0 flex flex-col">
                  {selectedFile ? (
                    <>
                      {/* File tab bar */}
                      <div className="flex h-9 shrink-0 items-center border-b border-white/10 bg-[#111111]">
                        <div className="flex h-full items-center gap-1.5 border-r border-white/10 bg-[#181818] pl-3 pr-2 text-[11px]">
                          <FileIcon name={selectedFile.split(/[\\/]/).pop() ?? ''} />
                          <span className="text-[#d4d4d4]">{selectedFile.split(/[\\/]/).pop()}</span>
                          <button
                            onClick={() => setSelectedFile(null)}
                            className="ml-0.5 rounded p-0.5 text-[#6b6b6b] transition-colors hover:bg-[#3c3c3c] hover:text-[#d4d4d4]"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </div>
                        <div className="flex flex-1 items-center px-3">
                          <span className="truncate text-[10px] font-mono text-[#555555]">
                            {selectedFile.replace(/\\/g, '/')}
                          </span>
                        </div>
                        <button
                          onClick={saveFile}
                          disabled={saving}
                          className="mr-2 flex h-6 items-center gap-1.5 rounded-md bg-[#8c5462] px-2.5 text-[10px] font-semibold text-white transition-colors hover:bg-[#70434f] disabled:opacity-50"
                        >
                          {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />}
                          {saving ? 'Saving' : 'Save'}
                        </button>
                      </div>

                      {/* Editor */}
                      <div className="relative flex-1" style={{ minHeight: 0 }}>
                        <CodeEditor
                          language={getLanguage(selectedFile)}
                          value={fileContent}
                          onChange={(v) => setFileContent(v ?? '')}
                        />
                      </div>
                    </>
                  ) : (
                    <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-3 border-white/10 bg-[#151515] text-center">
                      <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/10 bg-white/5">
                        <Code2 className="h-7 w-7 text-[#75756f]" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-[#858585]">Pick a file to edit</p>
                        <p className="mt-1 text-xs text-[#555555]">Browse the file tree on the left</p>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Console drag handle */}
            {showConsole && (
              <div
                className="group relative h-[3px] shrink-0 cursor-row-resize bg-[#0a0a0c] transition-colors hover:bg-[#8c5462]/60"
                onMouseDown={consoleH.onMouseDown}
              />
            )}

            {/* Console panel */}
            {showConsole && (
              <div
                className="flex shrink-0 flex-col border-t border-white/10 bg-[#111111]"
                style={{ height: consoleH.size }}
              >
                <div className="flex h-8 shrink-0 items-center justify-between border-b border-white/10 px-3">
                  <div className="flex h-full gap-0.5">
                    {(['terminal', 'output'] as const).map((tab) => (
                      <button
                        key={tab}
                        onClick={() => setActiveConsoleTab(tab)}
                        className={`flex h-full items-center gap-1.5 border-b-2 px-3 text-[10px] font-semibold uppercase tracking-wide transition-colors ${
                          activeConsoleTab === tab
                            ? 'border-[#d9a4b2] text-white'
                            : 'border-transparent text-[#75756f] hover:text-[#e8e8e3]'
                        }`}
                      >
                        {tab === 'terminal' ? <TerminalSquare className="h-3 w-3" /> : <Play className="h-3 w-3" />}
                        {tab === 'terminal' ? 'Terminal' : 'App Output'}
                        {tab === 'output' && (setupRunning_ || runtimeLoading || healActive) && (
                          <span className="ml-1 h-1.5 w-1.5 rounded-full bg-[#fbbf24] animate-pulse" />
                        )}
                      </button>
                    ))}
                  </div>
                  <button
                    onClick={() => setShowConsole(false)}
                    className="rounded p-1 text-[#75756f] transition-colors hover:bg-white/10 hover:text-white"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>

                <div className="relative flex-1 overflow-hidden" style={{ minHeight: 0 }}>
                  {activeConsoleTab === 'terminal' ? (
                    <div className="absolute inset-0 flex flex-col overflow-hidden">
                      <div className="flex h-9 shrink-0 items-center justify-between border-b border-white/10 bg-[#0d0d0d] px-2">
                        <div className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto py-1">
                          {terminalSessions.map((session) => {
                            const active = session.processId === activeTerminalSession?.processId;
                            return (
                              <button
                                key={session.processId}
                                onClick={() => setActiveTerminalPid(session.processId)}
                                className={`flex shrink-0 items-center gap-2 rounded-md px-2.5 py-1 text-[10px] font-semibold transition-colors ${
                                  active
                                    ? 'bg-[#2b1d22] text-[#f5eef1]'
                                    : 'bg-transparent text-[#8e8e88] hover:bg-white/5 hover:text-white'
                                }`}
                                title={session.command}
                              >
                                <TerminalSquare className="h-3 w-3" />
                                <span className="max-w-[120px] truncate">{session.title}</span>
                                <span className={`h-1.5 w-1.5 rounded-full ${session.running ? 'bg-[#34d399]' : 'bg-[#6b6b6b]'}`} />
                              </button>
                            );
                          })}
                        </div>
                        <div className="ml-3 flex shrink-0 items-center gap-1">
                          <button
                            onClick={() => void spawnTerm()}
                            className="flex h-7 w-7 items-center justify-center rounded-md text-[#8e8e88] transition-colors hover:bg-white/10 hover:text-white"
                            title="New terminal"
                          >
                            <Plus className="h-3.5 w-3.5" />
                          </button>
                          {activeTerminalSession && terminalSessions.length > 1 && (
                            <button
                              onClick={() => void closeTerm(activeTerminalSession.processId)}
                              className="flex h-7 w-7 items-center justify-center rounded-md text-[#8e8e88] transition-colors hover:bg-white/10 hover:text-white"
                              title="Close terminal"
                            >
                              <X className="h-3.5 w-3.5" />
                            </button>
                          )}
                        </div>
                      </div>
                      <div className="min-h-0 flex-1 overflow-hidden p-1">
                        <Terminal
                          key={activeTerminalSession?.processId || 'empty-terminal'}
                          ref={terminalRef}
                          onInput={termInput}
                          outputStream={activeTerminalSession?.output || ''}
                        />
                      </div>
                    </div>
                  ) : (
                    <div className="absolute inset-0 flex flex-col overflow-hidden bg-[#0d0d0d]">
                      {appOutputSessions.length > 1 && (
                        <div className="flex h-9 shrink-0 items-center gap-1 overflow-x-auto border-b border-white/10 px-2">
                          {appOutputSessions.map((session) => {
                            const active = session.processId === activeAppOutput?.processId;
                            return (
                              <button
                                key={session.processId}
                                onClick={() => setActiveAppOutputPid(session.processId)}
                                className={`flex shrink-0 items-center gap-2 rounded-md px-2.5 py-1 text-[10px] font-semibold transition-colors ${
                                  active
                                    ? 'bg-[#2b1d22] text-[#f5eef1]'
                                    : 'bg-transparent text-[#8e8e88] hover:bg-white/5 hover:text-white'
                                }`}
                              >
                                <Play className="h-3 w-3" />
                                <span>{session.title}</span>
                                <span className={`h-1.5 w-1.5 rounded-full ${session.running ? 'bg-[#34d399]' : 'bg-[#6b6b6b]'}`} />
                              </button>
                            );
                          })}
                        </div>
                      )}
                      <div className="min-h-0 flex-1 overflow-y-auto p-4 font-mono text-[12px] leading-relaxed text-[#d8d8d2]">
                        <pre className="whitespace-pre-wrap break-words">
                          {stripAnsi(activeAppOutput?.output || '')}
                          {!activeAppOutput?.output && !setupRunning_ && !runtimeLoading && !isRunning && (
                            <span className="italic text-[#555555]">Start the project to stream output here...</span>
                          )}
                          {!activeAppOutput?.output && activeAppOutput?.running && (
                            <span className="italic text-[#555555]">Waiting for process output...</span>
                          )}
                        </pre>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Status bar */}
            <div className="flex h-[20px] shrink-0 items-center justify-between border-t border-white/10 bg-[#0d0d0d] px-3 text-[9px] font-medium uppercase tracking-widest text-[#75756f]">
              <div className="flex items-center gap-3">
                <span>DevHub</span>
                {selectedFile && <span>{getLanguage(selectedFile)}</span>}
                <span>{runtimeBackend === 'docker' ? 'Docker' : 'Local'}</span>
                {runtime?.runtime_type && <span>{runtime.runtime_type}</span>}
              </div>
              <div className="flex items-center gap-3">
                {healStatus && healSummary && (
                  <span className={`${healProblem ? 'text-[#fca5a5]' : healActive ? 'text-[#d9a4b2]' : 'text-[#86efac]'}`}>
                    {healSummary}
                  </span>
                )}
                {isRunning && previewPort && (
                  <span className="flex items-center gap-1 text-[#34d399]">
                    <span className="h-1.5 w-1.5 rounded-full bg-[#34d399] animate-pulse" />
                    PORT {previewPort}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* == RIGHT: Chat panel ================================================= */}
      {chatOpen ? (
        <>
          {/* Drag handle — left edge of right-side chat */}
          <div
            className="group relative w-[3px] shrink-0 cursor-col-resize bg-[#0a0a0c] transition-colors hover:bg-[#8c5462]/60"
            onMouseDown={chatPanel.onMouseDown}
          />

          <div className="flex h-full flex-col min-w-0 shrink-0 border-l border-white/10 bg-[#111111]" style={{ width: `${chatPanel.size}px` }}>
            {/* Header */}
            <div className="flex h-12 shrink-0 items-center justify-between border-b border-white/10 px-4">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-[#d9a4b2]" />
                <span className="text-xs font-semibold text-[#f3f3ee]">Workspace AI</span>
              </div>
            </div>

            {/* Chat content */}
            <div className="flex min-h-0 min-w-0 flex-1 flex-col" style={{ minHeight: 0 }}>
              <ProjectChatPanel
                projectId={projectId}
                mode="workspace"
                selectedFile={selectedFile}
                fileContent={fileContent}
                treeNodes={treeNodes}
                coderCustomization={coderCustomization}
                runtimeAgentRun={runtimeAgentRun}
                onCodeApplied={handleCodeApplied}
                onAgentAction={handleAgentAction}
                onCustomizationChanged={onProjectChanged}
                onToggleChat={setChatOpen}
                chatOpen={chatOpen}
              />
            </div>
          </div>
        </>
      ) : (
        <div className="flex w-12 shrink-0 flex-col items-center border-l border-white/5 bg-[#0d0d0d] py-3">
          <button
            onClick={() => setChatOpen(true)}
            title="Expand Chat Panel"
            className="flex h-8 w-8 items-center justify-center rounded-lg text-[#6b6b6b] transition-colors hover:bg-white/10 hover:text-white"
          >
            <MessageSquare className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}
