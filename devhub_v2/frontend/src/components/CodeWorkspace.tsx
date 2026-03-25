import { useEffect, useRef, useState } from 'react';
import { Bot, ChevronDown, ChevronRight, Code2, FileText, Folder, FolderOpen, FolderTree, Globe, Loader2, PanelLeftClose, PanelRightClose, Play, RefreshCw, Save, Search, Send, Sparkles, Square, TerminalSquare, Wrench, X } from 'lucide-react';

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

type MentionItem = {
  type: 'special' | 'file' | 'folder';
  value: string;
};

type MentionOption = MentionItem & {
  label: string;
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

const CHAT_SPECIAL_MENTIONS: MentionOption[] = [
  { type: 'special', value: 'codebase', label: '@codebase' },
  { type: 'special', value: 'currentFile', label: '@currentFile' },
  { type: 'special', value: 'readme', label: '@readme' },
  { type: 'special', value: 'rules', label: '@rules' },
  { type: 'special', value: 'terminal', label: '@terminal' },
  { type: 'special', value: 'conversation', label: '@conversation' },
];

const flattenTreeNodes = (nodes: FileNode[], max = 240): MentionOption[] => {
  const items: MentionOption[] = [];
  const visit = (node: FileNode) => {
    if (items.length >= max) return;
    items.push({
      type: node.type === 'directory' ? 'folder' : 'file',
      value: node.path,
      label: `@${node.path}`,
    });
    if (node.type === 'directory' && node.children?.length) {
      node.children.forEach(visit);
    }
  };
  nodes.forEach(visit);
  return items;
};

const currentMentionQuery = (value: string) => {
  const match = value.match(/@([^\s@]*)$/);
  return match ? match[1] : null;
};

export default function CodeWorkspace({ workspaceId, projectId, projectPath, onProjectChanged }: Props) {
  const [activeSidePanel, setActiveSidePanel] = useState<'files' | 'search'>('files');
  const [showSidePanel, setShowSidePanel] = useState(true);
  const [showBottomPanel, setShowBottomPanel] = useState(true);
  const [activeBottomTab, setActiveBottomTab] = useState<'terminal' | 'output'>('terminal');
  const [activeEditorTab, setActiveEditorTab] = useState<'code' | 'preview'>('code');
  const [chatOpen, setChatOpen] = useState(false);
  const [chatExpanded, setChatExpanded] = useState(false);
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
  const [chatMessages, setChatMessages] = useState<any[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatSending, setChatSending] = useState(false);
  const [contextMentions, setContextMentions] = useState<MentionItem[]>([]);
  const terminalRef = useRef<any>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const socketsRef = useRef<Record<string, WebSocket>>({});
  const inferredPort = getPort(runtime?.run_command);
  const previewUrl = runtime?.preview_url || (inferredPort ? `http://127.0.0.1:${inferredPort}` : null);
  const previewAvailable = Boolean(runtime?.status?.running && previewUrl && runtime?.ready);
  const previewPending = Boolean(runtime?.status?.running && previewUrl && runtime?.ready === false);
  const rootLabel = projectPath?.split(/[\\/]/).pop() || 'PROJECT';
  const mentionQuery = currentMentionQuery(chatInput);
  const mentionOptions = [...CHAT_SPECIAL_MENTIONS, ...flattenTreeNodes(treeNodes)]
    .filter((item, index, source) => index === source.findIndex((candidate) => candidate.type === item.type && candidate.value === item.value))
    .filter((item) => !mentionQuery || item.label.toLowerCase().includes(`@${mentionQuery.toLowerCase()}`))
    .slice(0, 12);

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

  const fetchChatHistory = () => {
    fetch(`${API}/projects/${projectId}/chat/`).then((r) => r.json()).then((data) => setChatMessages(data.messages ?? []));
  };

  const insertMention = (item: MentionOption) => {
    const nextMention = { type: item.type, value: item.value };
    setContextMentions((current) => (
      current.some((entry) => entry.type === nextMention.type && entry.value === nextMention.value)
        ? current
        : [...current, nextMention]
    ));
    setChatInput((current) => {
      const token = `@${item.value}`;
      if (/@([^\s@]*)$/.test(current)) {
        return current.replace(/@([^\s@]*)$/, `${token} `);
      }
      return `${current}${current && !current.endsWith(' ') ? ' ' : ''}${token} `;
    });
  };

  const removeMention = (item: MentionItem) => {
    setContextMentions((current) => current.filter((entry) => !(entry.type === item.type && entry.value === item.value)));
  };

  const renderTrace = (trace: any) => {
    if (!trace || typeof trace !== 'object') return null;
    const contextItems = Array.isArray(trace.context_mentions) ? trace.context_mentions : [];
    const filesAccessed = Array.isArray(trace.files_accessed) ? trace.files_accessed : [];
    const commandsRan = Array.isArray(trace.commands_ran) ? trace.commands_ran : [];
    const semanticHits = Array.isArray(trace.semantic_hits) ? trace.semantic_hits : [];
    const appliedFiles = Array.isArray(trace.applied_files) ? trace.applied_files : [];
    return (
      <div className="mt-3 ml-8 space-y-3 rounded-2xl border border-black/5 bg-[#f8f9fb] p-3 text-[11px] text-slate-600">
        {trace.approach && (
          <div>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">Approach</p>
            <p className="leading-6 text-slate-600">{trace.approach}</p>
          </div>
        )}
        {contextItems.length > 0 && (
          <div>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">Context</p>
            <div className="flex flex-wrap gap-1.5">
              {contextItems.map((item: any, index: number) => (
                <span key={`${item.type || 'mention'}-${item.value || index}`} className="rounded-full border border-black/5 bg-white px-2 py-1 text-[10px] font-medium text-slate-600 shadow-sm">
                  @{item.value || item.type || 'context'}
                </span>
              ))}
            </div>
          </div>
        )}
        {filesAccessed.length > 0 && (
          <div>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">Files Accessed</p>
            <div className="space-y-1.5">
              {filesAccessed.slice(0, 10).map((item: any, index: number) => (
                <div key={`${item.path || 'file'}-${index}`} className="rounded-xl bg-white px-2.5 py-2 border border-black/5">
                  <code className="block break-all text-[10px] font-medium text-blue-600">{item.path || 'unknown file'}</code>
                  {item.reason && <p className="mt-1 text-slate-500">{item.reason}</p>}
                </div>
              ))}
            </div>
          </div>
        )}
        {commandsRan.length > 0 && (
          <div>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">Commands Ran</p>
            <div className="space-y-1.5">
              {commandsRan.slice(0, 8).map((item: any, index: number) => (
                <div key={`${item.command || 'command'}-${index}`} className="rounded-xl bg-slate-900 px-2.5 py-2">
                  <code className="block whitespace-pre-wrap break-words text-[10px] text-emerald-300">{item.command || 'unknown command'}</code>
                  {item.detail && <p className="mt-1 text-slate-400">{item.detail}</p>}
                </div>
              ))}
            </div>
          </div>
        )}
        {semanticHits.length > 0 && (
          <div>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">Semantic Hits</p>
            <div className="space-y-1.5">
              {semanticHits.slice(0, 8).map((item: any, index: number) => (
                <div key={`${item.path || 'hit'}-${index}`} className="rounded-xl bg-white px-2.5 py-2 border border-black/5">
                  <code className="block break-all text-[10px] font-medium text-blue-600">{item.path || 'unknown'}</code>
                  {item.symbol && <p className="mt-1 text-slate-500">Symbol: {item.symbol}</p>}
                </div>
              ))}
            </div>
          </div>
        )}
        {appliedFiles.length > 0 && (
          <div>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">Applied Files</p>
            <div className="flex flex-wrap gap-1.5">
              {appliedFiles.map((item: string) => (
                <span key={item} className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1 text-[10px] font-medium text-emerald-700">{item}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  useEffect(() => {
    if (!workspaceId) return;
    refreshTree();
    fetchRuntime();
    fetchChatHistory();
  }, [workspaceId, projectId]);

  useEffect(() => chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }), [chatMessages, chatOpen]);

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

  const sendChat = async () => {
    if (!chatInput.trim() || chatSending) return;
    const content = chatInput.trim();
    setChatInput('');
    setChatSending(true);
    setChatMessages((current) => [...current, { role: 'user', content, metadata: { context_mentions: contextMentions, selected_file: selectedFile } }]);
    try {
      const response = await fetch(`${API}/projects/${projectId}/chat/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content,
          selected_file: selectedFile,
          selected_content: selectedFile ? fileContent : '',
          context_mentions: contextMentions,
        }),
      });
      const data = await response.json();
      setChatMessages((current) => [...current, { role: 'assistant', content: data.assistant_message ?? 'No response.', metadata: data.trace ?? {} }]);
      if (data.applied_changes?.applied_files?.length) {
        await refreshTree();
        fetchRuntime();
        onProjectChanged?.();
        if (selectedFile && data.applied_changes.applied_files.includes(selectedFile)) {
          loadFile(selectedFile);
        } else {
          loadFile(data.applied_changes.applied_files[0]);
        }
        if (runtime?.status?.running) setPreviewRefreshKey((current) => current + 1);
      }
    } catch {
      setChatMessages((current) => [...current, { role: 'assistant', content: 'Connection failed.', metadata: { error: 'connection_failed' } }]);
    } finally {
      setChatSending(false);
    }
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
        {chatOpen && (
          <div
            className={`pointer-events-auto flex flex-col overflow-hidden border border-black/10 bg-white shadow-[0_24px_80px_rgba(15,23,42,0.18)] ${chatExpanded ? 'fixed inset-4 z-50 rounded-[28px]' : 'rounded-[24px]'}`}
            style={chatExpanded ? undefined : { width: 480, height: 600, resize: 'both', minWidth: 360, minHeight: 400, maxWidth: '92vw', maxHeight: '80vh' }}
          >
            <div className="flex items-center justify-between gap-3 border-b border-black/5 bg-[linear-gradient(180deg,#ffffff,#f8fafc)] px-5 py-3.5">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-black shadow-sm">
                  <Sparkles className="h-4 w-4 text-white" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">Workspace Chat</h3>
                  <p className="text-[10px] text-slate-400">Ask about files, architecture, or anything in this project</p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setChatExpanded((c) => !c)}
                  className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                  title={chatExpanded ? 'Minimize' : 'Expand'}
                >
                  {chatExpanded ? <PanelLeftClose className="h-4 w-4" /> : <PanelRightClose className="h-4 w-4" />}
                </button>
                <button
                  type="button"
                  onClick={() => setChatOpen(false)}
                  className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>

            <div className="border-b border-black/5 bg-[#fbfcfe] px-5 py-3">
              <div className="flex flex-wrap gap-2">
                {CHAT_SPECIAL_MENTIONS.slice(0, 6).map((item) => (
                  <button
                    key={item.value}
                    type="button"
                    onClick={() => insertMention(item)}
                    className="rounded-full border border-black/5 bg-white px-3 py-1.5 text-[11px] font-medium text-slate-600 shadow-[0_2px_8px_rgba(15,23,42,0.04)] transition hover:bg-slate-50 hover:text-slate-900"
                  >
                    {item.label}
                  </button>
                ))}
              </div>
              {selectedFile && (
                <div className="mt-2.5 flex items-center gap-1.5 text-[11px] text-slate-500">
                  <FileText className="h-3 w-3" />
                  Current file: <span className="font-medium text-slate-700">{selectedFile}</span>
                </div>
              )}
            </div>

            <div className="flex-1 min-h-0 overflow-x-hidden overflow-y-auto px-5 py-4 bg-[#fafbfc]">
              <div className="space-y-5">
                {chatMessages.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 mb-4">
                      <Bot className="h-7 w-7 text-slate-300" />
                    </div>
                    <p className="text-sm font-medium text-slate-400">Ask anything about this codebase</p>
                    <p className="mt-1 text-xs text-slate-300">Use @codebase for full project analysis</p>
                  </div>
                )}
                {chatMessages.map((message, index) => (
                  <div key={index} className={message.role === 'user'
                    ? 'ml-8 rounded-2xl bg-black px-4 py-3 text-[13px] leading-relaxed text-white shadow-[0_10px_24px_rgba(15,23,42,0.12)]'
                    : 'pr-4'
                  }>
                    {message.role === 'assistant' && (
                      <div className="mb-2 flex items-center gap-2">
                        <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-black">
                          <Bot className="h-3.5 w-3.5 text-white" />
                        </div>
                        <span className="text-xs font-semibold text-slate-900">DevHub</span>
                      </div>
                    )}
                    <div className={`whitespace-pre-wrap break-words ${message.role === 'assistant' ? 'text-[13px] leading-7 text-slate-700 pl-8' : 'leading-relaxed'}`}>{message.content}</div>
                    {message.role === 'assistant' && renderTrace(message.metadata)}
                  </div>
                ))}
                {chatSending && (
                  <div className="flex items-center gap-2.5 pl-8 text-sm text-slate-400">
                    <Loader2 className="h-4 w-4 animate-spin text-slate-500" />
                    Analyzing codebase...
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>
            </div>

            <div className="border-t border-black/5 bg-white p-4">
              {contextMentions.length > 0 && (
                <div className="mb-3 flex flex-wrap gap-1.5">
                  {contextMentions.map((item) => (
                    <button
                      key={`${item.type}-${item.value}`}
                      type="button"
                      onClick={() => removeMention(item)}
                      className="rounded-full border border-blue-100 bg-blue-50 px-2.5 py-1 text-[11px] font-medium text-blue-700 hover:bg-blue-100"
                    >
                      @{item.value} ×
                    </button>
                  ))}
                </div>
              )}
              <div className="relative flex min-w-0">
                <textarea
                  value={chatInput}
                  onChange={(event) => setChatInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                      event.preventDefault();
                      sendChat();
                    }
                  }}
                  placeholder="Ask with @codebase, @readme, or @src/App.tsx ..."
                  className="min-h-[80px] w-full resize-none rounded-2xl border border-black/8 bg-[#f8f9fb] py-3 pl-4 pr-12 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition focus:border-black/15 focus:bg-white focus:shadow-[0_4px_16px_rgba(15,23,42,0.06)]"
                  rows={3}
                />
                <button onClick={sendChat} disabled={!chatInput.trim() || chatSending} className="absolute bottom-2.5 right-2.5 rounded-xl bg-black p-2.5 text-white shadow-sm transition hover:bg-slate-800 disabled:opacity-30">
                  <Send className="h-4 w-4" />
                </button>
                {mentionQuery !== null && mentionOptions.length > 0 && (
                  <div className="absolute bottom-[calc(100%+8px)] left-0 right-0 max-h-56 overflow-y-auto rounded-2xl border border-black/8 bg-white p-2 shadow-[0_16px_48px_rgba(15,23,42,0.14)]">
                    {mentionOptions.map((item) => (
                      <button
                        key={`${item.type}-${item.value}`}
                        type="button"
                        onClick={() => insertMention(item)}
                        className="flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left text-[12px] text-slate-700 hover:bg-slate-50"
                      >
                        <span className="truncate font-medium">{item.label}</span>
                        <span className="ml-3 shrink-0 text-[10px] text-slate-400">{item.type}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        <button
          type="button"
          onClick={() => setChatOpen((current) => !current)}
          className={`pointer-events-auto flex items-center justify-center rounded-full border border-black/10 bg-black text-white shadow-[0_18px_48px_rgba(15,23,42,0.25)] transition-all hover:shadow-[0_24px_56px_rgba(15,23,42,0.3)] hover:scale-105 ${chatOpen ? 'h-12 w-12' : 'h-14 w-14'}`}
        >
          {chatOpen ? <X className="h-5 w-5" /> : <Bot className="h-6 w-6" />}
        </button>
      </div>
    </div>
  );
}
