import { useEffect, useRef, useState } from 'react';
import { Bot, ChevronDown, ChevronRight, Code2, FileText, Folder, FolderOpen, FolderTree, Globe, Loader2, PanelLeftClose, PanelRightClose, Play, RefreshCw, Save, Search, Square, TerminalSquare, Wrench, X } from 'lucide-react';
import ProjectChatPanel from './ProjectChatPanel';

import { CodeEditor } from './Editor';
import { Terminal } from './Terminal';

const API = 'http://localhost:8000/api';

type RuntimeState = {
  runtime_type?: string;
  run_command?: string | null;
  setup_command?: string | null;
  preview_url?: string | null;
  ready?: boolean;
  preview_error?: string | null;
  process_id?: string;
  status?: { exists?: boolean; running?: boolean; command?: string; uptime_seconds?: number };
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
  onProjectChanged?: () => void;
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

export default function CodeWorkspace({ workspaceId, projectId, projectPath, onProjectChanged }: Props) {
  const [activeSidePanel, setActiveSidePanel] = useState<'files' | 'search'>('files');
  const [showSidePanel, setShowSidePanel] = useState(true);
  const [showBottomPanel, setShowBottomPanel] = useState(true);
  const [activeBottomTab, setActiveBottomTab] = useState<'terminal' | 'output'>('terminal');
  const [activeEditorTab, setActiveEditorTab] = useState<'code' | 'preview'>('code');
  const [chatOpen, setChatOpen] = useState(false);
  const [treeNodes, setTreeNodes] = useState<FileNode[]>([]);
  const [expandedDirs, setExpandedDirs] = useState<string[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState('// Select a file from the explorer');
  const [saving, setSaving] = useState(false);
  const [runtime, setRuntime] = useState<RuntimeState | null>(null);
  const [runtimeLoading, setRuntimeLoading] = useState(false);
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
  const rootLabel = projectPath?.split(/[\\/]/).pop() || 'PROJECT';

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

  const fetchRuntime = () => {
    if (!workspaceId) return;
    fetch(`${API}/workspace/${workspaceId}/runtime/`)
      .then((r) => r.json())
      .then((data) => {
        setRuntime(data);
        if (data?.status?.running && data.preview_error && data.ready === false) {
          setRuntimeOutput((current) => current || `Preview warming up: ${data.preview_error}`);
        }
      });
  };



  useEffect(() => {
    if (!workspaceId) return;
    refreshTree();
    fetchRuntime();
  }, [workspaceId, projectId]);

  useEffect(() => {
    if (!workspaceId) return;
    const interval = setInterval(fetchRuntime, 4000);
    return () => clearInterval(interval);
  }, [workspaceId]);

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
      if (data.status && !data.status.running) setSetupRunning(false);
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
    setRuntimeOutput('');
    setAwaitingPreview(true);
    setShowBottomPanel(true);
    setActiveBottomTab('output');
    try {
      const response = await fetch(`${API}/workspace/${workspaceId}/runtime/`, { method: 'POST' });
      const data = await response.json();
      setRuntime(data);
      if (data.ready && (data.preview_url || data.run_command)) {
        setActiveEditorTab('preview');
        setAwaitingPreview(false);
      } else if (data.preview_error) {
        setRuntimeOutput(data.preview_error);
      }
    } finally {
      setRuntimeLoading(false);
    }
  };

  const stopProject = async () => {
    if (!workspaceId) return;
    await fetch(`${API}/workspace/${workspaceId}/runtime/`, { method: 'DELETE' });
    setAwaitingPreview(false);
    fetchRuntime();
    setActiveEditorTab('code');
  };

  const runSetup = async () => {
    if (!workspaceId) return;
    setSetupRunning(true);
    setSetupOutput('');
    setShowBottomPanel(true);
    setActiveBottomTab('output');
    await fetch(`${API}/workspace/${workspaceId}/setup/`, { method: 'POST' });
  };

  const handleCodeApplied = async (appliedFiles: string[]) => {
    await refreshTree();
    fetchRuntime();
    onProjectChanged?.();
    if (selectedFile && appliedFiles.includes(selectedFile)) {
      loadFile(selectedFile);
    } else if (appliedFiles.length > 0) {
      loadFile(appliedFiles[0]);
    }
    if (runtime?.status?.running) setPreviewRefreshKey((current) => current + 1);
  };

  const renderTreeNode = (node: FileNode, depth = 0): any => (
    <div key={node.path}>
      <button
        type="button"
        onClick={() => (node.type === 'directory' ? toggleDirectory(node.path) : loadFile(node.path))}
        className={`flex w-full items-center gap-1 rounded-md py-1 pr-3 text-left text-[11px] ${selectedFile === node.path ? 'bg-[#37373d] text-white' : 'text-[#cccccc] hover:bg-[#2a2d2e] hover:text-white'}`}
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
    <div className="flex h-full w-full min-h-0 min-w-0 overflow-hidden rounded-lg border border-[#333333] bg-[#1e1e1e] text-[#cccccc]">
      <div className="z-10 flex w-12 shrink-0 flex-col items-center border-r border-[#333333] bg-[#252526] py-2">
        <button onClick={() => { setActiveSidePanel('files'); setShowSidePanel(true); }} className={`group relative mb-2 rounded-lg p-2.5 ${activeSidePanel === 'files' && showSidePanel ? 'text-white' : 'text-[#858585] hover:text-white'}`}><FolderTree className="h-5 w-5" />{activeSidePanel === 'files' && showSidePanel && <div className="absolute left-0 top-1/2 h-6 w-0.5 -translate-y-1/2 bg-[#007acc]" />}</button>
        <button onClick={() => { setActiveSidePanel('search'); setShowSidePanel(true); }} className={`group relative mb-2 rounded-lg p-2.5 ${activeSidePanel === 'search' && showSidePanel ? 'text-white' : 'text-[#858585] hover:text-white'}`}><Search className="h-5 w-5" />{activeSidePanel === 'search' && showSidePanel && <div className="absolute left-0 top-1/2 h-6 w-0.5 -translate-y-1/2 bg-[#007acc]" />}</button>
        <div className="flex-1" />
      </div>

      {showSidePanel && (
        <div className="flex w-[min(24rem,40vw)] min-w-[18rem] max-w-[25rem] shrink-0 flex-col overflow-hidden border-r border-[#333333] bg-[#252526]">
          <div className="flex h-[35px] items-center justify-between px-4 text-xs font-semibold uppercase tracking-wide text-[#BBBBBB]">
            {activeSidePanel === 'files' ? 'Explorer' : 'Search'}
            <button onClick={() => setShowSidePanel(false)} className="rounded p-1 text-[#858585] hover:bg-[#333333] hover:text-white"><PanelLeftClose className="h-4 w-4" /></button>
          </div>
          <div className="flex-1 min-h-0 overflow-hidden">
            {activeSidePanel === 'files' && <div className="flex h-full min-h-0 flex-col"><div className="border-b border-[#333333] px-4 py-3"><div className="flex items-center gap-2 text-[11px] font-semibold text-[#9ca3af]"><ChevronDown className="h-3.5 w-3.5" /><span className="truncate">{rootLabel}</span></div></div><div className="flex-1 min-h-0 overflow-y-auto px-2 py-2">{treeNodes.map((node) => renderTreeNode(node))}</div></div>}
            {activeSidePanel === 'search' && <div className="mt-10 p-4 text-center"><Search className="mx-auto mb-3 h-8 w-8 text-[#4d4d4d]" /><p className="text-xs text-[#858585]">Search is coming next.</p></div>}
          </div>
        </div>
      )}

      <div className="flex min-h-0 min-w-0 flex-1 flex-col bg-[#1e1e1e]">
        <div className="flex h-[35px] min-w-0 items-center justify-between border-b border-[#333333] bg-[#181818] shrink-0">
          <div className="flex h-full min-w-0">
            <button onClick={() => setActiveEditorTab('code')} className={`flex h-full min-w-0 items-center border-r border-[#333333] px-4 text-[11px] font-medium ${activeEditorTab === 'code' ? 'border-t border-t-[#007acc] bg-[#1e1e1e] text-white' : 'text-[#858585] hover:bg-[#2a2d2e]'}`}><Code2 className="mr-1.5 h-3.5 w-3.5 shrink-0 text-blue-400" /><span className="truncate">{selectedFile ? selectedFile.split(/[\\/]/).pop() : 'Welcome'}</span></button>
            {runtime?.status?.running && previewUrl && <button onClick={() => previewAvailable && setActiveEditorTab('preview')} className={`flex h-full min-w-0 items-center border-r border-[#333333] px-4 text-[11px] font-medium ${activeEditorTab === 'preview' && previewAvailable ? 'border-t border-t-[#007acc] bg-[#1e1e1e] text-emerald-400' : previewAvailable ? 'text-emerald-600/70 hover:bg-[#2a2d2e]' : 'cursor-wait text-[#858585]'}`}><Globe className="mr-1.5 h-3.5 w-3.5 shrink-0" /><span className="truncate">{previewAvailable ? 'Live Preview' : 'Preview Starting...'}</span></button>}
          </div>
          <div className="flex min-w-0 max-w-[420px] items-center gap-2 overflow-x-auto px-3">
            {!showSidePanel && <button onClick={() => setShowSidePanel(true)} className="rounded p-1.5 text-[#858585] hover:bg-[#333333] hover:text-white"><PanelRightClose className="h-4 w-4 scale-x-[-1]" /></button>}
            <div className="mx-1 h-4 w-px bg-[#333333]" />
            {runtime?.setup_command && <button onClick={runSetup} disabled={setupRunning} className="flex h-6 shrink-0 items-center gap-1.5 rounded border border-[#333333] px-2.5 text-[10px] font-medium text-[#cccccc] hover:bg-[#2a2d2e] hover:text-white disabled:opacity-50">{setupRunning ? <Loader2 className="h-3 w-3 animate-spin text-white" /> : <Wrench className="h-3 w-3 text-[#cccccc]" />}<span className="truncate">Setup</span></button>}
            {previewPending && <span className="shrink-0 rounded border border-[#2f4f78] bg-[#10263e] px-2 py-0.5 text-[10px] text-[#8ec7ff]">Waiting for preview...</span>}
            {runtime?.status?.running ? <button onClick={stopProject} className="flex h-6 shrink-0 items-center gap-1.5 rounded bg-[#801c1c] px-2.5 text-[10px] font-medium text-white hover:bg-[#a12323]"><Square className="h-3 w-3 fill-white" /><span className="truncate">Stop Project</span></button> : <button onClick={runProject} disabled={runtimeLoading || !runtime?.run_command} className="flex h-6 shrink-0 items-center gap-1.5 rounded border border-[#2a6834] bg-[#1e4c25] px-2.5 text-[10px] font-medium text-white hover:bg-[#265e2f] disabled:opacity-50">{runtimeLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Play className="h-3 w-3 fill-emerald-400" />}<span className="truncate">{runtime?.run_command ? 'Run Project' : 'No Run Command'}</span></button>}
          </div>
        </div>

        <div className="relative flex-1 min-h-0 min-w-0 bg-[#1e1e1e]">
          {activeEditorTab === 'code' && <div className="absolute inset-0 flex min-h-0 min-w-0 flex-col"><div className="flex h-6 items-center border-b border-[#2d2d2d] bg-[#1e1e1e] px-4 text-[10px] text-[#858585]">{selectedFile ? selectedFile.replace(/\\/g, '/') : 'Select a file to begin'}</div><div className="relative flex-1 min-h-0 min-w-0">{selectedFile ? <><CodeEditor language={getLanguage(selectedFile)} value={fileContent} onChange={(value) => setFileContent(value ?? '')} /><button onClick={saveFile} disabled={saving} className="absolute bottom-4 right-6 z-10 flex items-center gap-2 rounded bg-[#007acc] px-4 py-2 text-xs font-medium text-white hover:bg-[#0062a3] disabled:opacity-50">{saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />} {saving ? 'Saving...' : 'Save File'}</button></> : <div className="absolute inset-0 flex items-center justify-center pointer-events-none"><img src="/logo.png" alt="" className="h-48 w-48 grayscale opacity-[0.03]" /></div>}</div></div>}
          {activeEditorTab === 'preview' && runtime?.status?.running && previewUrl && previewAvailable && <div className="absolute inset-0 flex min-h-0 min-w-0 flex-col bg-white"><div className="flex h-8 items-center gap-2 border-b border-[#dddddd] bg-[#f3f3f3] px-3"><button className="flex items-center gap-1 rounded border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-mono text-slate-500 shadow-sm hover:bg-slate-50" onClick={() => window.open(previewUrl, '_blank')}><Globe className="h-3 w-3 text-blue-500" />{previewUrl.replace(/^https?:\/\//, '')}</button><button onClick={() => setPreviewRefreshKey((current) => current + 1)} className="rounded p-1 text-slate-500 hover:bg-slate-200"><RefreshCw className="h-3.5 w-3.5" /></button></div><iframe key={`${runtime.process_id}-${previewRefreshKey}`} src={previewUrl} className="h-full w-full border-0 bg-white" title="Live Preview" /></div>}
          {activeEditorTab === 'preview' && runtime?.status?.running && previewUrl && !previewAvailable && <div className="absolute inset-0 flex min-h-0 min-w-0 flex-col items-center justify-center gap-4 bg-[#111827] px-6 text-center text-white"><Loader2 className="h-8 w-8 animate-spin text-slate-300" /><div><p className="text-sm font-medium">Preview is still starting</p><p className="mt-2 max-w-md text-xs leading-6 text-slate-400">{runtime?.preview_error || 'The local server has not responded yet. Keep the project running for a moment and it will become available automatically.'}</p></div></div>}
        </div>

        {showBottomPanel && <div className="flex h-64 min-h-0 shrink-0 flex-col border-t border-[#333333] bg-[#1e1e1e]"><div className="relative flex h-8 items-center justify-between border-b border-[#2d2d2d] bg-[#1e1e1e] px-4"><div className="flex h-full gap-4"><button onClick={() => setActiveBottomTab('terminal')} className={`flex h-full items-center border-b-[2px] text-[10px] font-medium uppercase tracking-wide ${activeBottomTab === 'terminal' ? 'border-[#007acc] text-white' : 'border-transparent text-[#858585] hover:text-[#cccccc]'}`}><TerminalSquare className="mr-1.5 h-3.5 w-3.5" />Terminal</button><button onClick={() => setActiveBottomTab('output')} className={`flex h-full items-center border-b-[2px] text-[10px] font-medium uppercase tracking-wide ${activeBottomTab === 'output' ? 'border-[#007acc] text-white' : 'border-transparent text-[#858585] hover:text-[#cccccc]'}`}><Play className="mr-1.5 h-3.5 w-3.5" />App Output</button></div><button onClick={() => setShowBottomPanel(false)} className="rounded p-1 text-[#858585] hover:bg-[#333333] hover:text-white"><X className="h-3.5 w-3.5" /></button></div><div className="relative flex-1 min-h-0 bg-[#1e1e1e]">{activeBottomTab === 'terminal' ? <div className="absolute inset-0 p-1"><Terminal ref={terminalRef} onInput={termInput} /></div> : <div className="absolute inset-0 overflow-y-auto p-4 text-[12px] leading-relaxed text-[#cccccc] selection:bg-[#264f78]"><pre className="whitespace-pre-wrap font-mono">{runtimeOutput || (!runtime?.status?.running ? <span className="italic text-[#858585]">Run the project to stream output here...</span> : '')}{setupOutput && `\n\n--- Setup Output ---\n${setupOutput}`}</pre></div>}</div></div>}

        <div className="z-20 flex h-5 shrink-0 items-center justify-between bg-[#007acc] px-3 text-[10px] text-white">
          <div className="flex items-center gap-3"><span className="flex items-center gap-1 rounded px-1 hover:bg-white/20"><Wrench className="h-3 w-3" />DevHub IDE</span>{selectedFile && <span>{getLanguage(selectedFile).toUpperCase()}</span>}{runtime?.status?.running && previewUrl && <span className="flex items-center gap-1 px-1"><span className="h-1.5 w-1.5 rounded-full bg-green-300 animate-pulse" />Port {new URL(previewUrl).port}</span>}</div>
          <div className="flex items-center gap-3">{!showBottomPanel && <button onClick={() => { setShowBottomPanel(true); setActiveBottomTab('terminal'); }} className="flex items-center gap-1 rounded px-1 hover:bg-white/20"><TerminalSquare className="h-3 w-3" />Layout: Bottom Panel Hidden</button>}</div>
        </div>
      </div>

      <div className="pointer-events-none fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3">
        <ProjectChatPanel
          projectId={projectId}
          mode="floating"
          selectedFile={selectedFile}
          fileContent={fileContent}
          treeNodes={treeNodes}
          onCodeApplied={handleCodeApplied}
          onToggleChat={setChatOpen}
          chatOpen={chatOpen}
        />

        <button
          type="button"
          onClick={() => setChatOpen((current) => !current)}
          className={`pointer-events-auto flex items-center justify-center rounded-full border border-white/90 bg-white text-slate-900 shadow-[0_18px_48px_rgba(15,23,42,0.22)] transition-all hover:scale-105 hover:bg-slate-50 hover:shadow-[0_24px_56px_rgba(15,23,42,0.28)] ${chatOpen ? 'h-12 w-12' : 'h-14 w-14'}`}
        >
          {chatOpen ? <X className="h-5 w-5" /> : <Bot className="h-6 w-6" />}
        </button>
      </div>
    </div>
  );
}
