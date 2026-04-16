import { useEffect, useRef, useState } from 'react';
import { Bot, ChevronDown, ChevronRight, Code2, FileText, Folder, FolderOpen, FolderTree, Globe, Loader2, Maximize2, Minimize2, PanelLeftClose, PanelLeftOpen, PanelRightClose, Play, RefreshCw, RotateCcw, Save, Search, Square, TerminalSquare, Wrench, X } from 'lucide-react';
import ProjectChatPanel, { type CoderCustomization } from './ProjectChatPanel';

import { CodeEditor } from './Editor';
import { Terminal } from './Terminal';

const API = 'http://localhost:8000/api';

type RuntimeState = {
  runtime_type?: string;
  run_command?: string | null;
  setup_command?: string | null;
  install_required?: boolean;
  preview_url?: string | null;
  ready?: boolean;
  preview_error?: string | null;
  process_id?: string;
  status?: { exists?: boolean; running?: boolean; command?: string; uptime_seconds?: number; backend?: string; container_name?: string };
  sandbox?: { mode?: string; image?: string | null; runtime?: string | null; network?: string | null };
};

type FileNode = {
  name: string;
  type: 'directory' | 'file';
  path: string;
  children?: FileNode[];
  loaded?: boolean;
};



type Props = {
  workspaceId: string | null;
  projectId: string;
  projectPath?: string | null;
  coderCustomization?: CoderCustomization | null;
  onProjectChanged?: () => void;
  projectSidebarCollapsed?: boolean;
  onToggleProjectSidebar?: () => void;
  isFullscreen?: boolean;
  onToggleFullscreen?: () => void;
};

const getLanguage = (path: string | null) => {
  if (!path) return 'plaintext';
  if (path.endsWith('.py')) return 'python';
  if (path.endsWith('.ts') || path.endsWith('.tsx')) return 'typescript';
  if (path.endsWith('.js') || path.endsWith('.jsx')) return 'javascript';
  if (path.endsWith('.json')) return 'json';
  if (path.endsWith('.css')) return 'css';
  if (path.endsWith('.html')) return 'html';
  if (path.endsWith('.md')) return 'markdown';
  return 'plaintext';
};

const getPort = (cmd?: string | null) => {
  const match = cmd?.match(/(\d{4,5})/);
  return match ? match[1] : null;
};

const normalizeNode = (item: any): FileNode => ({
  name: item.name,
  type: item.type,
  path: item.path,
  children: item.type === 'directory' ? [] : undefined,
  loaded: item.type === 'directory' ? false : undefined,
});

const insertChildren = (nodes: FileNode[], targetPath: string, children: FileNode[]): FileNode[] =>
  nodes.map((node) => {
    if (node.path === targetPath && node.type === 'directory') return { ...node, children, loaded: true };
    if (node.type === 'directory' && node.children) return { ...node, children: insertChildren(node.children, targetPath, children) };
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

export default function CodeWorkspace({ workspaceId, projectId, projectPath, coderCustomization, onProjectChanged, projectSidebarCollapsed = false, onToggleProjectSidebar, isFullscreen = false, onToggleFullscreen }: Props) {
  const [activeSidePanel, setActiveSidePanel] = useState<'files' | 'search'>('files');
  const [showSidePanel, setShowSidePanel] = useState(true);
  const [showBottomPanel, setShowBottomPanel] = useState(true);
  const [activeBottomTab, setActiveBottomTab] = useState<'terminal' | 'output'>('terminal');
  const [activeEditorTab, setActiveEditorTab] = useState<'code' | 'preview'>('code');
  const [chatOpen, setChatOpen] = useState(true);
  const [treeNodes, setTreeNodes] = useState<FileNode[]>([]);
  const [expandedDirs, setExpandedDirs] = useState<string[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState('// Select a file from the explorer');
  const [saving, setSaving] = useState(false);
  const [runtime, setRuntime] = useState<RuntimeState | null>(null);
  const [runtimeLoading, setRuntimeLoading] = useState(false);
  const [startPhase, setStartPhase] = useState<'idle' | 'setup' | 'run'>('idle');
  const [runtimeOutput, setRuntimeOutput] = useState('');
  const [setupRunning, setSetupRunning] = useState(false);
  const [setupOutput, setSetupOutput] = useState('');
  const [previewRefreshKey, setPreviewRefreshKey] = useState(0);
  const [awaitingPreview, setAwaitingPreview] = useState(false);
  const [termPid, setTermPid] = useState<string | null>(null);
  const terminalRef = useRef<any>(null);
  const socketsRef = useRef<Record<string, WebSocket>>({});
  const inferredPort = getPort(runtime?.run_command);
  const previewUrl = runtime?.preview_url || (inferredPort ? `http://127.0.0.1:${inferredPort}` : null);
  const previewAvailable = Boolean(runtime?.status?.running && previewUrl && runtime?.ready);
  const previewPending = Boolean(runtime?.status?.running && previewUrl && runtime?.ready === false);
  const needsSetupBeforeRun = Boolean(!runtime?.status?.running && runtime?.setup_command && runtime?.install_required);
  const runtimeBackend = runtime?.status?.backend || runtime?.sandbox?.mode || 'local';
  const containerName = runtime?.status?.container_name;
  const previewPort = previewUrl ? new URL(previewUrl).port : null;
  const sandboxRuntimeName = runtime?.sandbox?.runtime || '';
  const manualSetupLabel = setupRunning ? 'Setup Running...' : needsSetupBeforeRun ? 'Setup Only' : 'Re-run Setup';
  const primaryActionLabel = runtime?.status?.running
    ? 'Stop Project'
    : runtimeLoading
      ? startPhase === 'setup'
        ? 'Preparing Project...'
        : 'Starting Project...'
      : needsSetupBeforeRun
        ? 'Setup & Start'
        : runtime?.run_command
          ? 'Start Project'
          : 'No Start Command';
  const rootLabel = projectPath?.split(/[\\/]/).pop() || 'PROJECT';
  const customSkillCount = Array.isArray(coderCustomization?.skills) ? coderCustomization.skills.length : 0;
  const promptOverrideCount = Array.isArray(coderCustomization?.prompt_overrides) ? coderCustomization.prompt_overrides.length : 0;
  const customizationSummary = String(coderCustomization?.summary || '').trim();

  const fetchDirectory = async (path = '') => {
    if (!workspaceId) return [];
    const response = await fetch(`${API}/workspace/${workspaceId}/fs/?path=${encodeURIComponent(path)}`);
    const data = await response.json();
    return data.type === 'directory' ? (data.items ?? []).map(normalizeNode) : [];
  };

  const refreshTree = async () => {
    if (!workspaceId) return;
    let snapshot = await fetchDirectory('');
    for (const path of [...expandedDirs].sort((a, b) => a.split('/').length - b.split('/').length)) {
      try {
        snapshot = insertChildren(snapshot, path, await fetchDirectory(path));
      } catch {}
    }
    setTreeNodes(snapshot);
  };

  const fetchRuntime = async () => {
    if (!workspaceId) return null;
    const response = await fetch(`${API}/workspace/${workspaceId}/runtime/`);
    const data = await response.json();
    setRuntime(data);
    if (data?.status?.running && data.preview_error && data.ready === false) {
      setRuntimeOutput((current) => current || `Preview warming up: ${data.preview_error}`);
    }
    return data as RuntimeState;
  };

  const fetchSetupStatus = async () => {
    if (!workspaceId) return null;
    const response = await fetch(`${API}/workspace/${workspaceId}/setup/`);
    const data = await response.json();
    if (data?.status && !data.status.running) {
      setSetupRunning(false);
    }
    return data;
  };

  const startSetupProcess = async ({ resetOutput = true }: { resetOutput?: boolean } = {}) => {
    if (!workspaceId) return null;
    setSetupRunning(true);
    if (resetOutput) {
      setSetupOutput('');
    }
    setShowBottomPanel(true);
    setActiveBottomTab('output');
    const response = await fetch(`${API}/workspace/${workspaceId}/setup/`, { method: 'POST' });
    const data = await response.json();
    if (!response.ok || data?.error) {
      setSetupRunning(false);
      throw new Error(data?.error || 'Setup failed to start.');
    }
    return data;
  };

  const waitForSetupToFinish = async (timeoutMs = 120_000) => {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const data = await fetchSetupStatus();
      if (!data?.status?.running) {
        return data;
      }
      await new Promise((resolve) => setTimeout(resolve, 900));
    }
    return null;
  };



  useEffect(() => {
    if (!workspaceId) return;
    void refreshTree();
    void fetchRuntime();
  }, [workspaceId, projectId]);

  useEffect(() => {
    if (!workspaceId) return;

    const isActivelyChanging = runtimeLoading || setupRunning || awaitingPreview || previewPending;
    const pollDelay = isActivelyChanging
      ? 1500
      : runtime?.status?.running
        ? 15000
        : 30000;

    const timeout = window.setTimeout(() => {
      void fetchRuntime();
    }, pollDelay);

    return () => window.clearTimeout(timeout);
  }, [
    workspaceId,
    runtimeLoading,
    setupRunning,
    awaitingPreview,
    previewPending,
    runtime?.status?.running,
  ]);

  useEffect(() => {
    return () => {
      Object.values(socketsRef.current).forEach((socket) => socket.close());
      socketsRef.current = {};
    };
  }, []);

  useEffect(() => {
    if (!runtime?.status?.running) {
      setAwaitingPreview(false);
      return;
    }
    if (awaitingPreview && previewAvailable) {
      setActiveEditorTab('preview');
      setAwaitingPreview(false);
    }
  }, [awaitingPreview, previewAvailable, runtime?.status?.running]);

  const loadFile = async (path: string) => {
    if (!workspaceId) return;
    setSelectedFile(path);
    const response = await fetch(`${API}/workspace/${workspaceId}/fs/?path=${encodeURIComponent(path)}`);
    const data = await response.json();
    if (data.type === 'file') {
      setFileContent(data.content);
      setActiveEditorTab('code');
    }
  };

  const saveFile = async () => {
    if (!workspaceId || !selectedFile) return;
    setSaving(true);
    await fetch(`${API}/workspace/${workspaceId}/fs/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: selectedFile, content: fileContent }),
    });
    setSaving(false);
    refreshTree();
    onProjectChanged?.();
  };

  const toggleDirectory = async (path: string) => {
    if (expandedDirs.includes(path)) {
      setExpandedDirs((current) => current.filter((item) => item !== path));
      return;
    }
    setExpandedDirs((current) => [...current, path]);
    const existing = findNode(treeNodes, path);
    if (existing?.loaded) return;
    const children = await fetchDirectory(path);
    setTreeNodes((current) => insertChildren(current, path, children));
  };

  const spawnTerm = () => {
    if (!workspaceId || termPid) return;
    fetch(`${API}/workspace/${workspaceId}/spawn/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: 'cmd.exe' }),
    }).then((r) => r.json()).then((data) => { if (data.process_id) setTermPid(data.process_id); });
  };

  useEffect(() => { if (workspaceId && !termPid) spawnTerm(); }, [workspaceId, termPid]);

  const connectSocket = (pid: string, onMessage: (data: any) => void) => {
    if (!workspaceId || socketsRef.current[pid]) return;
    const socket = new WebSocket(`ws://localhost:8000/ws/workspace/${workspaceId}/process/${pid}/`);
    socket.onmessage = (event) => onMessage(JSON.parse(event.data));
    socket.onclose = () => { delete socketsRef.current[pid]; };
    socketsRef.current[pid] = socket;
  };

  useEffect(() => {
    if (termPid) connectSocket(termPid, (data) => { if (data.output && terminalRef.current) terminalRef.current.write(data.output); });
    if (runtime?.process_id && runtime.status?.running) connectSocket(runtime.process_id, (data) => {
      if (data.output) setRuntimeOutput((current) => current + data.output);
      if (data.status) setRuntime((current) => (current ? { ...current, status: data.status } : null));
    });
    if (setupRunning && workspaceId) connectSocket(`${workspaceId}_setup`, (data) => {
      if (data.output) setSetupOutput((current) => current + data.output);
      if (data.status && !data.status.running) {
        setSetupRunning(false);
        void fetchRuntime();
      }
    });
  }, [workspaceId, termPid, runtime?.process_id, runtime?.status?.running, setupRunning]);

  const termInput = (data: string) => {
    if (termPid && socketsRef.current[termPid]?.readyState === WebSocket.OPEN) {
      socketsRef.current[termPid].send(JSON.stringify({ input: data }));
    }
  };

  const runProject = async () => {
    if (!workspaceId) return;
    setRuntimeLoading(true);
    setStartPhase(needsSetupBeforeRun ? 'setup' : 'run');
    setRuntimeOutput('');
    setShowBottomPanel(true);
    setActiveBottomTab('output');
    try {
      if (needsSetupBeforeRun) {
        setSetupOutput('Preparing project dependencies before launch...\n');
        await startSetupProcess({ resetOutput: false });
        const setupStatus = await waitForSetupToFinish();
        if (!setupStatus) {
          setRuntimeOutput('Setup is still running. Let it finish in the output panel, then start the project.');
          setAwaitingPreview(false);
          return;
        }
        const refreshedRuntime = await fetchRuntime();
        if (refreshedRuntime?.install_required) {
          setRuntimeOutput('Setup finished, but the project still looks unprepared. Review the setup output and try again.');
          setAwaitingPreview(false);
          return;
        }
      }

      setStartPhase('run');
      setAwaitingPreview(true);
      setRuntimeOutput((current) => current || 'Starting project...\n');
      const response = await fetch(`${API}/workspace/${workspaceId}/runtime/`, { method: 'POST' });
      const data = await response.json();
      if (!response.ok || data?.error) {
        throw new Error(data?.error || 'Unable to start the project.');
      }
      setRuntime(data);
      if (data.ready && (data.preview_url || data.run_command)) {
        setActiveEditorTab('preview');
        setAwaitingPreview(false);
      } else if (data?.status?.running && data.preview_url) {
        setActiveEditorTab('preview');
      } else if (data.preview_error) {
        setRuntimeOutput((current) => `${current}${current.endsWith('\n') ? '' : '\n'}${data.preview_error}`);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to start the project.';
      setRuntimeOutput(message);
      setAwaitingPreview(false);
    } finally {
      setRuntimeLoading(false);
      setStartPhase('idle');
    }
  };

  const stopProject = async () => {
    if (!workspaceId) return;
    await fetch(`${API}/workspace/${workspaceId}/runtime/`, { method: 'DELETE' });
    setAwaitingPreview(false);
    void fetchRuntime();
    setActiveEditorTab('code');
  };

  const restartProject = async () => {
    if (!workspaceId) return;
    if (runtime?.status?.running) {
      await stopProject();
      await new Promise((resolve) => setTimeout(resolve, 450));
    }
    await runProject();
  };

  const runSetup = async () => {
    if (!workspaceId) return;
    try {
      await startSetupProcess();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Setup failed to start.';
      setSetupOutput(message);
    }
  };

  const handleCodeApplied = async (appliedFiles: string[]) => {
    await refreshTree();
    void fetchRuntime();
    onProjectChanged?.();
    if (selectedFile && appliedFiles.includes(selectedFile)) {
      void loadFile(selectedFile);
    } else if (appliedFiles.length > 0) {
      void loadFile(appliedFiles[0]);
    }
    if (runtime?.status?.running) setPreviewRefreshKey((current) => current + 1);
  };

  const handleAgentAction = async (actions: any[]) => {
    if (!Array.isArray(actions) || !actions.length) return;

    setShowBottomPanel(true);
    setActiveBottomTab('output');

    const actionTypes = new Set(actions.map((item) => String(item?.type || '')));
    const touchesRuntime = [...actionTypes].some((item) => item.startsWith('runtime_') || item === 'setup');
    const touchesFiles = actionTypes.has('setup') || actionTypes.has('terminal_command');

    if (touchesFiles) {
      await refreshTree();
    }

    if (touchesRuntime) {
      const nextRuntime = await fetchRuntime();
      await fetchSetupStatus();

      if (actionTypes.has('runtime_stop')) {
        setActiveEditorTab('code');
        setAwaitingPreview(false);
      }

      if ((actionTypes.has('runtime_start') || actionTypes.has('runtime_restart')) && nextRuntime?.preview_url) {
        setAwaitingPreview(!nextRuntime.ready);
        if (nextRuntime.ready) {
          setActiveEditorTab('preview');
          setPreviewRefreshKey((current) => current + 1);
        }
      }
    }
  };

  const renderTreeNode = (node: FileNode, depth = 0): any => (
    <div key={node.path}>
      <button
        type="button"
        onClick={() => (node.type === 'directory' ? toggleDirectory(node.path) : loadFile(node.path))}
        className={`flex w-full items-center gap-1 rounded-md py-1 pr-3 text-left text-[11px] ${selectedFile === node.path ? 'bg-blue-600 text-white' : 'text-[#cccccc] hover:bg-[#2a2d2e] hover:text-white'}`}
        style={{ paddingLeft: `${12 + depth * 14}px` }}
      >
        {node.type === 'directory' ? (expandedDirs.includes(node.path) ? <ChevronDown className="h-3.5 w-3.5 shrink-0 text-[#858585]" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0 text-[#858585]" />) : <span className="h-3.5 w-3.5 shrink-0" />}
        {node.type === 'directory' ? (expandedDirs.includes(node.path) ? <FolderOpen className="h-3.5 w-3.5 shrink-0 text-[#d7ba7d]" /> : <Folder className="h-3.5 w-3.5 shrink-0 text-[#d7ba7d]" />) : <FileText className="h-3.5 w-3.5 shrink-0 text-[#519aba]" />}
        <span className="truncate">{node.name}</span>
      </button>
      {node.type === 'directory' && expandedDirs.includes(node.path) && (node.children?.length ? node.children.map((child) => renderTreeNode(child, depth + 1)) : <div className="px-3 py-1 text-[10px] italic text-[#6b7280]" style={{ paddingLeft: `${30 + depth * 14}px` }}>Empty folder</div>)}
    </div>
  );

  if (!workspaceId) {
    return <div className="flex h-full items-center justify-center rounded-lg bg-[#1e1e1e] text-center text-slate-400"><div><FolderTree className="mx-auto mb-3 h-12 w-12 opacity-20" /><p className="font-medium">No active workspace</p><p className="mt-1 text-xs text-slate-500">Connect a project folder to start coding.</p></div></div>;
  }

  return (
    <div className={`flex h-full w-full min-h-0 min-w-0 overflow-hidden bg-[#1e1e1e] text-[#cccccc] ${isFullscreen ? 'rounded-none border-0' : 'rounded-lg border border-[#333333]'}`}>
      {showSidePanel && (
        <div className="flex w-[min(24rem,40vw)] min-w-[18rem] max-w-[25rem] shrink-0 flex-col overflow-hidden border-r border-[#333333] bg-[#252526]">
          <div className="flex h-[35px] items-center justify-between px-3 border-b border-[#333333] text-[11px] font-semibold uppercase tracking-wide text-[#BBBBBB]">
            <div className="flex h-full">
              <button onClick={() => setActiveSidePanel('files')} className={`flex h-full items-center gap-1.5 border-b-2 px-2 ${activeSidePanel === 'files' ? 'border-[#007acc] text-white' : 'border-transparent text-[#858585] hover:text-white'}`}><FolderTree className="h-3.5 w-3.5" /> Files</button>
              <button onClick={() => setActiveSidePanel('search')} className={`flex h-full items-center gap-1.5 border-b-2 px-2 ${activeSidePanel === 'search' ? 'border-[#007acc] text-white' : 'border-transparent text-[#858585] hover:text-white'}`}><Search className="h-3.5 w-3.5" /> Search</button>
            </div>
            <button onClick={() => setShowSidePanel(false)} className="rounded p-1 text-[#858585] hover:bg-[#333333] hover:text-white"><PanelLeftClose className="h-4 w-4" /></button>
          </div>
          <div className="flex-1 min-h-0 overflow-hidden">
            {activeSidePanel === 'files' && <div className="flex h-full min-h-0 flex-col"><div className="border-b border-[#333333] px-4 py-3"><div className="flex items-center gap-2 text-[11px] font-semibold text-[#9ca3af]"><ChevronDown className="h-3.5 w-3.5" /><span className="truncate">{rootLabel}</span></div></div><div className="flex-1 min-h-0 overflow-y-auto px-2 py-2">{treeNodes.map((node) => renderTreeNode(node))}</div></div>}
            {activeSidePanel === 'search' && <div className="mt-10 p-4 text-center"><Search className="mx-auto mb-3 h-8 w-8 text-[#4d4d4d]" /><p className="text-xs text-[#858585]">Search is coming next.</p></div>}
          </div>
        </div>
      )}

      <div className="relative flex min-h-0 min-w-0 flex-1">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col bg-[#1e1e1e]">
        <div className="flex h-[35px] min-w-0 items-center justify-between border-b border-[#333333] bg-black shrink-0">
          <div className="flex h-full min-w-0">
            <button onClick={() => setActiveEditorTab('code')} className={`flex h-full min-w-0 items-center border-r border-[#333333] px-4 text-[11px] font-medium ${activeEditorTab === 'code' ? 'border-t border-t-[#007acc] bg-[#1e1e1e] text-white' : 'text-[#858585] hover:bg-[#2a2d2e]'}`}><Code2 className="mr-1.5 h-3.5 w-3.5 shrink-0 text-blue-400" /><span className="truncate">{selectedFile ? selectedFile.split(/[\\/]/).pop() : 'Welcome'}</span></button>
            {runtime?.status?.running && previewUrl && <button onClick={() => previewAvailable && setActiveEditorTab('preview')} className={`flex h-full min-w-0 items-center border-r border-[#333333] px-4 text-[11px] font-medium ${activeEditorTab === 'preview' && previewAvailable ? 'border-t border-t-[#007acc] bg-[#1e1e1e] text-emerald-400' : previewAvailable ? 'text-emerald-600/70 hover:bg-[#2a2d2e]' : 'cursor-wait text-[#858585]'}`}><Globe className="mr-1.5 h-3.5 w-3.5 shrink-0" /><span className="truncate">{previewAvailable ? 'Live Preview' : 'Preview Starting...'}</span></button>}
          </div>
          <div className="flex min-w-0 max-w-[620px] items-center gap-2 overflow-x-auto px-3">
            {onToggleProjectSidebar && (
              <button
                onClick={onToggleProjectSidebar}
                className="rounded p-1.5 text-[#858585] hover:bg-[#333333] hover:text-white"
                title={projectSidebarCollapsed ? 'Expand project sidebar' : 'Collapse project sidebar'}
              >
                {projectSidebarCollapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
              </button>
            )}
            {!showSidePanel && <button onClick={() => setShowSidePanel(true)} className="rounded p-1.5 text-[#858585] hover:bg-[#333333] hover:text-white"><PanelRightClose className="h-4 w-4 scale-x-[-1]" /></button>}
            {!chatOpen && (
              <button
                onClick={() => setChatOpen(true)}
                className="inline-flex h-7 shrink-0 items-center gap-1.5 rounded border border-[#2f4f78] bg-[#0f2233] px-2.5 text-[10px] font-medium text-[#9dd2ff] hover:border-[#3b6a9e] hover:bg-[#13304a] hover:text-white"
                title="Reopen the coding agent panel"
              >
                <Bot className="h-3.5 w-3.5" />
                <span className="truncate">Open Chat</span>
              </button>
            )}
            {onToggleFullscreen && (
              <button
                onClick={onToggleFullscreen}
                className="rounded p-1.5 text-[#858585] hover:bg-[#333333] hover:text-white"
                title={isFullscreen ? 'Exit fullscreen workspace' : 'Open workspace fullscreen'}
              >
                {isFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
              </button>
            )}
            <div className="mx-1 h-4 w-px bg-[#333333]" />
            {coderCustomization && (
              <>
                {(customSkillCount > 0 || promptOverrideCount > 0) ? (
                  <>
                    <span
                      className="shrink-0 rounded border border-[#2f4f78] bg-[#0f2233] px-2 py-0.5 text-[10px] text-[#9dd2ff]"
                      title={customizationSummary || 'Project skills and prompt overrides loaded from .devhub'}
                    >
                      {customSkillCount} skills
                    </span>
                    <span
                      className="shrink-0 rounded border border-[#244053] bg-[#10202c] px-2 py-0.5 text-[10px] text-[#c7e6ff]"
                      title={customizationSummary || 'Project skills and prompt overrides loaded from .devhub'}
                    >
                      {promptOverrideCount} prompt rules
                    </span>
                  </>
                ) : (
                  <span
                    className="shrink-0 rounded border border-[#5f4c19] bg-[#2d230c] px-2 py-0.5 text-[10px] text-[#f6d77a]"
                    title="This project has no .devhub coder customization yet. Open the Coding Agent panel to enable the Project Kit."
                  >
                    Project kit empty
                  </span>
                )}
              </>
            )}
            {runtimeBackend === 'docker' && <span className="shrink-0 rounded border border-[#2f4f78] bg-[#0f2233] px-2 py-0.5 text-[10px] text-[#9dd2ff]" title={runtime?.sandbox?.image || 'Docker sandbox'}>Running in Docker</span>}
            {sandboxRuntimeName && <span className="shrink-0 rounded border border-[#2b3443] bg-[#131a24] px-2 py-0.5 text-[10px] text-[#cbd5e1]">{sandboxRuntimeName === 'runsc' ? 'gVisor / runsc' : sandboxRuntimeName}</span>}
            {containerName && <span className="shrink-0 rounded border border-[#333333] bg-[#141414] px-2 py-0.5 text-[10px] text-[#cbd5e1]" title={containerName}>{containerName}</span>}
            {runtime?.setup_command && !runtime?.status?.running && <button onClick={() => { void runSetup(); }} disabled={setupRunning || runtimeLoading} className="flex h-6 shrink-0 items-center gap-1.5 rounded border border-[#333333] px-2.5 text-[10px] font-medium text-[#cccccc] hover:bg-[#2a2d2e] hover:text-white disabled:opacity-50">{setupRunning ? <Loader2 className="h-3 w-3 animate-spin text-white" /> : <Wrench className="h-3 w-3 text-[#cccccc]" />}<span className="truncate">{manualSetupLabel}</span></button>}
            {needsSetupBeforeRun && <span className="shrink-0 rounded border border-[#5a4d24] bg-[#2b2513] px-2 py-0.5 text-[10px] text-[#f6d77a]">Setup required</span>}
            {previewPending && <span className="shrink-0 rounded border border-[#2f4f78] bg-[#10263e] px-2 py-0.5 text-[10px] text-[#8ec7ff]">Starting preview...</span>}
            {runtime?.status?.running && <button onClick={() => { void restartProject(); }} disabled={runtimeLoading} className="flex h-6 shrink-0 items-center gap-1.5 rounded border border-[#333333] px-2.5 text-[10px] font-medium text-[#cccccc] hover:bg-[#2a2d2e] hover:text-white disabled:opacity-50"><RotateCcw className="h-3 w-3" /><span className="truncate">Restart</span></button>}
            {runtime?.status?.running ? <button onClick={stopProject} className="flex h-6 shrink-0 items-center gap-1.5 rounded bg-[#801c1c] px-2.5 text-[10px] font-medium text-white hover:bg-[#a12323]"><Square className="h-3 w-3 fill-white" /><span className="truncate">{primaryActionLabel}</span></button> : <button onClick={() => { void runProject(); }} disabled={runtimeLoading || !runtime?.run_command} className="flex h-6 shrink-0 items-center gap-1.5 rounded border border-[#2a6834] bg-[#1e4c25] px-2.5 text-[10px] font-medium text-white hover:bg-[#265e2f] disabled:opacity-50">{runtimeLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3 fill-emerald-400" />}<span className="truncate">{primaryActionLabel}</span></button>}
          </div>
        </div>

        <div className="relative flex-1 min-h-0 min-w-0 bg-[#1e1e1e]">
          {activeEditorTab === 'code' && <div className="absolute inset-0 flex min-h-0 min-w-0 flex-col"><div className="flex h-6 items-center border-b border-[#2d2d2d] bg-[#1e1e1e] px-4 text-[10px] text-[#858585]">{selectedFile ? selectedFile.replace(/\\/g, '/') : 'Select a file to begin'}</div><div className="relative flex-1 min-h-0 min-w-0">{selectedFile ? <><CodeEditor language={getLanguage(selectedFile)} value={fileContent} onChange={(value) => setFileContent(value ?? '')} /><button onClick={saveFile} disabled={saving} className="absolute bottom-4 right-6 z-10 flex items-center gap-2 rounded bg-[#007acc] px-4 py-2 text-xs font-medium text-white hover:bg-[#0062a3] disabled:opacity-50">{saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />} {saving ? 'Saving...' : 'Save File'}</button></> : <div className="absolute inset-0 flex items-center justify-center pointer-events-none"><img src="/logo.png" alt="" className="h-48 w-48 grayscale opacity-[0.03]" /></div>}</div></div>}
          {activeEditorTab === 'preview' && runtime?.status?.running && previewUrl && previewAvailable && <div className="absolute inset-0 flex min-h-0 min-w-0 flex-col bg-white"><div className="flex h-8 items-center gap-2 border-b border-[#dddddd] bg-[#f3f3f3] px-3"><button className="flex items-center gap-1 rounded border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-mono text-slate-500 shadow-sm hover:bg-slate-50" onClick={() => window.open(previewUrl, '_blank')}><Globe className="h-3 w-3 text-blue-500" />{previewUrl.replace(/^https?:\/\//, '')}</button><button onClick={() => setPreviewRefreshKey((current) => current + 1)} className="rounded p-1 text-slate-500 hover:bg-slate-200"><RefreshCw className="h-3.5 w-3.5" /></button></div><iframe key={`${runtime.process_id}-${previewRefreshKey}`} src={previewUrl} className="h-full w-full border-0 bg-white" title="Live Preview" /></div>}
          {activeEditorTab === 'preview' && runtime?.status?.running && previewUrl && !previewAvailable && <div className="absolute inset-0 flex min-h-0 min-w-0 flex-col items-center justify-center gap-4 bg-[#111827] px-6 text-center text-white"><Loader2 className="h-8 w-8 animate-spin text-slate-300" /><div><p className="text-sm font-medium">Preview is still starting</p><p className="mt-2 max-w-md text-xs leading-6 text-slate-400">{runtime?.preview_error || 'The local server has not responded yet. Keep the project running for a moment and it will become available automatically.'}</p></div></div>}
        </div>

        {showBottomPanel && <div className="flex h-64 min-h-0 shrink-0 flex-col overflow-hidden border-t border-[#333333] bg-[#1e1e1e]"><div className="relative flex h-8 items-center justify-between border-b border-[#2d2d2d] bg-[#1e1e1e] px-4 shrink-0"><div className="flex h-full gap-4"><button onClick={() => setActiveBottomTab('terminal')} className={`flex h-full items-center border-b-[2px] text-[10px] font-medium uppercase tracking-wide ${activeBottomTab === 'terminal' ? 'border-[#007acc] text-white' : 'border-transparent text-[#858585] hover:text-[#cccccc]'}`}><TerminalSquare className="mr-1.5 h-3.5 w-3.5" />Terminal</button><button onClick={() => setActiveBottomTab('output')} className={`flex h-full items-center border-b-[2px] text-[10px] font-medium uppercase tracking-wide ${activeBottomTab === 'output' ? 'border-[#007acc] text-white' : 'border-transparent text-[#858585] hover:text-[#cccccc]'}`}><Play className="mr-1.5 h-3.5 w-3.5" />App Output</button></div><button onClick={() => setShowBottomPanel(false)} className="rounded p-1 text-[#858585] hover:bg-[#333333] hover:text-white"><X className="h-3.5 w-3.5" /></button></div><div className="relative flex-1 min-h-0 overflow-hidden bg-[#1e1e1e]">{activeBottomTab === 'terminal' ? <div className="absolute inset-0 overflow-hidden p-1"><Terminal ref={terminalRef} onInput={termInput} /></div> : <div className="absolute inset-0 overflow-y-auto p-4 text-[12px] leading-relaxed text-[#cccccc] selection:bg-[#264f78]"><pre className="whitespace-pre-wrap font-mono">{runtimeOutput}{setupOutput ? `${runtimeOutput ? '\n\n' : ''}--- Setup Output ---\n${setupOutput}` : ''}{!runtimeOutput && !setupOutput && !setupRunning && !runtimeLoading && !runtime?.status?.running ? <span className="italic text-[#858585]">Start the project to stream setup and runtime output here...</span> : ''}</pre></div>}</div></div>}

        <div className="z-20 flex h-5 shrink-0 items-center justify-between bg-[#007acc] px-3 text-[10px] text-white">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1 rounded px-1 hover:bg-white/20"><Wrench className="h-3 w-3" />DevHub IDE</span>
            {selectedFile && <span>{getLanguage(selectedFile).toUpperCase()}</span>}
            <span className="rounded px-1 hover:bg-white/20">{runtimeBackend === 'docker' ? 'SANDBOX: DOCKER' : 'SANDBOX: LOCAL'}</span>
            {sandboxRuntimeName && <span className="rounded px-1 hover:bg-white/20">{sandboxRuntimeName === 'runsc' ? 'RUNTIME: GVISOR' : `RUNTIME: ${sandboxRuntimeName.toUpperCase()}`}</span>}
            {runtime?.status?.running && previewPort && <span className="flex items-center gap-1 px-1"><span className="h-1.5 w-1.5 rounded-full bg-green-300 animate-pulse" />Port {previewPort}</span>}
          </div>
          <div className="flex items-center gap-3">{!showBottomPanel && <button onClick={() => { setShowBottomPanel(true); setActiveBottomTab('terminal'); }} className="flex items-center gap-1 rounded px-1 hover:bg-white/20"><TerminalSquare className="h-3 w-3" />Layout: Bottom Panel Hidden</button>}</div>
        </div>
      </div>
      {!chatOpen && (
        <button
          type="button"
          onClick={() => setChatOpen(true)}
          className="absolute right-3 top-1/2 z-30 flex -translate-y-1/2 items-center gap-2 rounded-l-2xl rounded-r-md border border-[#2f4f78] bg-[linear-gradient(180deg,#14314b,#0f2233)] px-3 py-2 text-left text-[11px] font-medium text-[#dbeafe] shadow-[0_14px_30px_rgba(0,0,0,0.38)] transition hover:border-[#4b7fb8] hover:text-white"
          title="Bring back the workspace chat"
          aria-label="Bring back the workspace chat"
        >
          <Bot className="h-4 w-4 shrink-0" />
          <span className="whitespace-nowrap">Open Coding Agent</span>
        </button>
      )}
      {chatOpen && (
        <ProjectChatPanel
          projectId={projectId}
          mode="workspace"
          selectedFile={selectedFile}
          fileContent={fileContent}
          treeNodes={treeNodes}
          coderCustomization={coderCustomization}
          onCodeApplied={handleCodeApplied}
          onAgentAction={handleAgentAction}
          onCustomizationChanged={onProjectChanged}
          onToggleChat={setChatOpen}
          chatOpen={chatOpen}
        />
      )}
      </div>
    </div>
  );
}
