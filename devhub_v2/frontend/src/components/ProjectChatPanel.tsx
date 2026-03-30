import { useEffect, useRef, useState } from 'react';
import { Bot, ChevronDown, FileText, Loader2, MessageSquarePlus, PanelLeftClose, PanelRightClose, Send, Sparkles, X } from 'lucide-react';

const API = 'http://localhost:8000/api';

type MentionItem = {
  type: 'special' | 'file' | 'folder';
  value: string;
};

type MentionOption = MentionItem & {
  label: string;
};

type ChatMessageRecord = {
  id?: string | number;
  role: 'user' | 'assistant';
  content: string;
  metadata?: any;
  created_at?: string;
  session_id?: string | null;
};

type ChatSession = {
  session_id: string;
  title: string;
  updated_at?: string | null;
  message_count: number;
  legacy?: boolean;
};

export type FileNodeObj = {
  name: string;
  type: 'directory' | 'file';
  path: string;
  children?: FileNodeObj[];
  loaded?: boolean;
};

type Props = {
  projectId: string;
  mode?: 'floating' | 'standalone';
  
  // Context passed by Workspace
  selectedFile?: string | null;
  fileContent?: string;
  treeNodes?: FileNodeObj[];
  
  // Callbacks
  onCodeApplied?: (appliedFiles: string[]) => void;
  onToggleChat?: (open: boolean) => void;
  chatOpen?: boolean;
};

const CHAT_SPECIAL_MENTIONS: MentionOption[] = [
  { type: 'special', value: 'codebase', label: '@codebase' },
  { type: 'special', value: 'currentFile', label: '@currentFile' },
  { type: 'special', value: 'readme', label: '@readme' },
  { type: 'special', value: 'rules', label: '@rules' },
  { type: 'special', value: 'terminal', label: '@terminal' },
  { type: 'special', value: 'conversation', label: '@conversation' },
];

const flattenTreeNodes = (nodes: FileNodeObj[], max = 240): MentionOption[] => {
  const items: MentionOption[] = [];
  const visit = (node: FileNodeObj) => {
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

const renderInlineMarkdown = (text: string) => {
  const nodes: any[] = [];
  const pattern = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\([^)]+\))/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(<span key={`text-${key++}`}>{text.slice(lastIndex, match.index)}</span>);
    }
    const token = match[0];
    if (token.startsWith('`') && token.endsWith('`')) {
      nodes.push(<code key={`code-${key++}`} className="rounded bg-black/5 px-1.5 py-0.5 font-mono text-[0.95em] text-slate-800">{token.slice(1, -1)}</code>);
    } else if (token.startsWith('**') && token.endsWith('**')) {
      nodes.push(<strong key={`strong-${key++}`} className="font-semibold text-slate-900">{token.slice(2, -2)}</strong>);
    } else if (token.startsWith('*') && token.endsWith('*')) {
      nodes.push(<em key={`em-${key++}`} className="italic">{token.slice(1, -1)}</em>);
    } else {
      const linkMatch = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      if (linkMatch) {
        nodes.push(
          <a
            key={`link-${key++}`}
            href={linkMatch[2]}
            target="_blank"
            rel="noreferrer"
            className="text-blue-700 underline decoration-blue-200 underline-offset-2 hover:text-blue-800"
          >
            {linkMatch[1]}
          </a>
        );
      } else {
        nodes.push(<span key={`fallback-${key++}`}>{token}</span>);
      }
    }
    lastIndex = pattern.lastIndex;
  }

  if (lastIndex < text.length) {
    nodes.push(<span key={`tail-${key++}`}>{text.slice(lastIndex)}</span>);
  }

  return nodes;
};

const renderMarkdownMessage = (content: string) => {
  const normalized = String(content || '').replace(/\r\n/g, '\n');
  const lines = normalized.split('\n');
  const blocks: any[] = [];
  let paragraph: string[] = [];
  let listItems: string[] = [];
  let codeLines: string[] = [];
  let inCode = false;
  let codeFence = '';

  const flushParagraph = () => {
    if (!paragraph.length) return;
    blocks.push(
      <p key={`p-${blocks.length}`} className="whitespace-pre-wrap break-words">
        {renderInlineMarkdown(paragraph.join(' '))}
      </p>
    );
    paragraph = [];
  };

  const flushList = () => {
    if (!listItems.length) return;
    blocks.push(
      <ul key={`ul-${blocks.length}`} className="list-disc space-y-1 pl-5">
        {listItems.map((item, index) => (
          <li key={`li-${index}`}>{renderInlineMarkdown(item)}</li>
        ))}
      </ul>
    );
    listItems = [];
  };

  const flushCode = () => {
    if (!codeLines.length && !codeFence) return;
    blocks.push(
      <pre key={`pre-${blocks.length}`} className="overflow-x-auto rounded-2xl bg-[#111827] px-4 py-3 text-[12px] leading-6 text-slate-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
        <code>{codeLines.join('\n')}</code>
      </pre>
    );
    codeLines = [];
    codeFence = '';
  };

  for (const rawLine of lines) {
    const line = rawLine ?? '';
    const trimmed = line.trim();

    if (trimmed.startsWith('```')) {
      if (inCode) {
        flushCode();
        inCode = false;
      } else {
        flushParagraph();
        flushList();
        inCode = true;
        codeFence = trimmed.slice(3).trim();
      }
      continue;
    }

    if (inCode) {
      codeLines.push(line);
      continue;
    }

    if (!trimmed) {
      flushParagraph();
      flushList();
      continue;
    }

    const headingMatch = trimmed.match(/^(#{1,3})\s+(.*)$/);
    if (headingMatch) {
      flushParagraph();
      flushList();
      const level = headingMatch[1].length;
      const text = headingMatch[2];
      const className = level === 1
        ? 'text-xl font-semibold text-slate-900'
        : level === 2
          ? 'text-lg font-semibold text-slate-900'
          : 'text-base font-semibold text-slate-900';
      blocks.push(
        <div key={`h-${blocks.length}`} className={className}>
          {renderInlineMarkdown(text)}
        </div>
      );
      continue;
    }

    const listMatch = trimmed.match(/^[-*]\s+(.*)$/);
    if (listMatch) {
      flushParagraph();
      listItems.push(listMatch[1]);
      continue;
    }

    paragraph.push(trimmed);
  }

  if (inCode) flushCode();
  flushParagraph();
  flushList();

  return <div className="space-y-3">{blocks}</div>;
};

export default function ProjectChatPanel({ projectId, mode = 'floating', selectedFile, fileContent, treeNodes = [], onCodeApplied, onToggleChat, chatOpen = true }: Props) {
  const [chatExpanded, setChatExpanded] = useState(false);
  const [chatMessages, setChatMessages] = useState<any[]>([]);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [activeChatSessionId, setActiveChatSessionId] = useState<string | null>(null);
  const [chatInput, setChatInput] = useState('');
  const [chatSending, setChatSending] = useState(false);
  const [contextMentions, setContextMentions] = useState<MentionItem[]>([]);
  const [showSessions, setShowSessions] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const mentionQuery = currentMentionQuery(chatInput);
  const mentionOptions = [...CHAT_SPECIAL_MENTIONS, ...flattenTreeNodes(treeNodes)]
    .filter((item, index, source) => index === source.findIndex((candidate) => candidate.type === item.type && candidate.value === item.value))
    .filter((item) => !mentionQuery || item.label.toLowerCase().includes(`@${mentionQuery.toLowerCase()}`))
    .slice(0, 12);

  const fetchChatHistory = async (sessionId?: string | null) => {
    const query = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : '';
    const response = await fetch(`${API}/projects/${projectId}/chat/${query}`);
    const data = await response.json();
    setChatSessions(data.sessions ?? []);
    setActiveChatSessionId(data.active_session_id ?? sessionId ?? null);
    setChatMessages(data.messages ?? []);
  };

  useEffect(() => {
    if (projectId && (chatOpen || mode === 'standalone')) {
      fetchChatHistory(activeChatSessionId);
    }
  }, [projectId, chatOpen, mode]);

  useEffect(() => {
    if (chatOpen || mode === 'standalone') {
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatMessages, chatOpen, mode]);

  const startNewChat = () => {
    setActiveChatSessionId(null);
    setChatMessages([]);
    setChatInput('');
    setContextMentions([]);
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
    const traceSummary = [
      filesAccessed.length ? `${filesAccessed.length} files` : '',
      commandsRan.length ? `${commandsRan.length} commands` : '',
      semanticHits.length ? `${semanticHits.length} hits` : '',
      appliedFiles.length ? `${appliedFiles.length} edits` : '',
    ].filter(Boolean).join(' • ');
    
    return (
      <details className="mt-3 ml-7 rounded-2xl border border-slate-100 bg-white text-[11px] text-slate-500 hover:border-slate-200 transition-colors shadow-sm w-fit min-w-[200px] max-w-full">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-3.5 py-2.5 font-medium tracking-wide">
          <span className="uppercase tracking-[0.16em] text-[10px] text-slate-400">Trace Logs</span>
          <span className="truncate text-[10px] text-slate-400">{traceSummary || 'View reasoning'}</span>
        </summary>
        <div className="space-y-2 border-t border-slate-100 px-3 py-3 bg-slate-50/50 rounded-b-2xl">
          {trace.approach && (
            <div className="rounded-xl border border-white bg-white px-3 py-2.5 leading-relaxed text-slate-600 shadow-sm">
              {trace.approach}
            </div>
          )}
          {contextItems.length > 0 && (
            <details className="rounded-xl border border-white bg-white px-3 py-2.5 shadow-sm">
              <summary className="cursor-pointer list-none text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                Context • {contextItems.length}
              </summary>
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                {contextItems.map((item: any, index: number) => (
                  <span key={`${item.type || 'mention'}-${item.value || index}`} className="rounded-full border border-slate-100 bg-slate-50 px-2.5 py-1 text-[10px] font-medium text-slate-600">
                    @{item.value || item.type || 'context'}
                  </span>
                ))}
              </div>
            </details>
          )}
          {filesAccessed.length > 0 && (
            <details className="rounded-xl border border-white bg-white px-3 py-2.5 shadow-sm">
              <summary className="cursor-pointer list-none text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                Files Accessed • {filesAccessed.length}
              </summary>
              <div className="mt-2.5 space-y-1.5">
                {filesAccessed.slice(0, 10).map((item: any, index: number) => (
                  <div key={`${item.path || 'file'}-${index}`} className="rounded-lg border border-slate-100 bg-slate-50 px-2.5 py-2">
                    <code className="block break-all text-[10px] font-medium text-slate-700">{item.path || 'unknown file'}</code>
                    {item.reason && <p className="mt-1 text-[10px] leading-5 text-slate-500">{item.reason}</p>}
                  </div>
                ))}
              </div>
            </details>
          )}
          {commandsRan.length > 0 && (
            <details className="rounded-xl border border-white bg-white px-3 py-2.5 shadow-sm">
              <summary className="cursor-pointer list-none text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                Commands Ran • {commandsRan.length}
              </summary>
              <div className="mt-2.5 space-y-1.5">
                {commandsRan.slice(0, 8).map((item: any, index: number) => (
                  <div key={`${item.command || 'command'}-${index}`} className="rounded-lg bg-slate-800 px-2.5 py-2 text-slate-100">
                    <code className="block whitespace-pre-wrap break-words text-[10px] text-emerald-300">{item.command || 'unknown command'}</code>
                    {item.detail && <p className="mt-1 text-[10px] leading-5 text-slate-400">{item.detail}</p>}
                  </div>
                ))}
              </div>
            </details>
          )}
          {semanticHits.length > 0 && (
            <details className="rounded-xl border border-white bg-white px-3 py-2.5 shadow-sm">
              <summary className="cursor-pointer list-none text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                Search Hits • {semanticHits.length}
              </summary>
              <div className="mt-2.5 space-y-1.5">
                {semanticHits.slice(0, 8).map((item: any, index: number) => (
                  <div key={`${item.path || 'hit'}-${index}`} className="rounded-lg border border-slate-100 bg-slate-50 px-2.5 py-2">
                    <code className="block break-all text-[10px] font-medium text-slate-700">{item.path || 'unknown'}</code>
                    {item.symbol && <p className="mt-1 text-[10px] leading-5 text-slate-500">Symbol: {item.symbol}</p>}
                  </div>
                ))}
              </div>
            </details>
          )}
          {appliedFiles.length > 0 && (
            <details className="rounded-xl border border-white bg-white px-3 py-2.5 shadow-sm">
              <summary className="cursor-pointer list-none text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                Edits Applied • {appliedFiles.length}
              </summary>
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                {appliedFiles.map((item: string) => (
                  <span key={item} className="rounded-full bg-emerald-50 px-2.5 py-1 text-[10px] font-medium text-emerald-700 border border-emerald-100">{item}</span>
                ))}
              </div>
            </details>
          )}
        </div>
      </details>
    );
  };

  const sendChat = async () => {
    if (!chatInput.trim() || chatSending) return;
    const content = chatInput.trim();
    setChatInput('');
    setChatSending(true);
    setChatMessages((current) => [...current, { role: 'user', content, metadata: { context_mentions: contextMentions, selected_file: selectedFile }, session_id: activeChatSessionId }]);
    
    try {
      const response = await fetch(`${API}/projects/${projectId}/chat/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content,
          session_id: activeChatSessionId,
          selected_file: selectedFile,
          selected_content: selectedFile ? fileContent : '',
          context_mentions: contextMentions,
        }),
      });
      const data = await response.json();
      setActiveChatSessionId(data.session_id ?? activeChatSessionId ?? null);
      setChatSessions(data.sessions ?? []);
      setChatMessages((current) => [...current, { role: 'assistant', content: data.assistant_message ?? 'No response.', metadata: data.trace ?? {}, session_id: data.session_id ?? activeChatSessionId }]);
      
      if (data.applied_changes?.applied_files?.length && onCodeApplied) {
        onCodeApplied(data.applied_changes.applied_files);
      }
    } catch {
      setChatMessages((current) => [...current, { role: 'assistant', content: 'Connection failed.', metadata: { error: 'connection_failed' } }]);
    } finally {
      setChatSending(false);
    }
  };

  if (!chatOpen && mode === 'floating') {
    return null;
  }

  const wrapperClasses = mode === 'standalone'
    ? "flex flex-col h-full w-full bg-white text-slate-900" 
    : `pointer-events-auto flex flex-col overflow-hidden border border-slate-200/60 bg-white shadow-2xl ${chatExpanded ? 'fixed inset-4 z-50 rounded-3xl' : 'rounded-2xl'}`;

  const wrapperStyles = mode === 'standalone'
    ? undefined
    : (chatExpanded ? undefined : { width: 440, height: 600, resize: 'both' as const, minWidth: 360, minHeight: 400, maxWidth: '92vw', maxHeight: '80vh' });

  return (
    <div className={wrapperClasses} style={wrapperStyles}>
      {/* Header */}
      {mode === 'floating' && (
        <div className="flex items-center justify-between gap-3 px-5 py-3 shrink-0 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-black shadow-sm">
              <Sparkles className="h-3.5 w-3.5 text-white" />
            </div>
            <h3 className="text-[13px] font-medium text-slate-900">Workspace Chat</h3>
          </div>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setChatExpanded((c) => !c)}
              className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-900"
              title={chatExpanded ? 'Minimize' : 'Expand'}
            >
              {chatExpanded ? <PanelLeftClose className="h-4 w-4" /> : <PanelRightClose className="h-4 w-4" />}
            </button>
            <button
              type="button"
              onClick={() => onToggleChat?.(false)}
              className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-900"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Toolbar */}
      <div className={`relative flex items-center gap-2.5 px-5 py-3 shrink-0 ${mode === 'standalone' ? 'pt-8 pb-4' : ''}`}>
        {/* We only show title on standalone mode in the top bar to keep it anchored if they want */}
        {mode === 'standalone' && (
          <div className="flex items-center gap-2.5 mr-4 border-r border-slate-200 pr-5">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-black shadow-sm">
              <Sparkles className="h-3.5 w-3.5 text-white" />
            </div>
            <h3 className="text-sm font-semibold text-slate-900">Chat</h3>
          </div>
        )}

        <button
          type="button"
          onClick={startNewChat}
          className="flex items-center gap-2 rounded-lg bg-black px-3 py-1.5 text-xs font-medium text-white shadow-sm transition hover:bg-slate-800"
        >
          <MessageSquarePlus className="h-3.5 w-3.5" />
          New Chat
        </button>
        
        <div className="relative">
          <button
            type="button"
            onClick={() => setShowSessions(!showSessions)}
            className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 transition"
          >
            History <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
          </button>
          {showSessions && chatSessions.length > 0 && (
            <div className="absolute top-full mt-1.5 left-0 z-10 w-48 rounded-xl border border-slate-150 bg-white p-1.5 shadow-lg">
              <div className="max-h-60 overflow-y-auto hidden-scrollbar">
                {chatSessions.map((session) => {
                  const isActive = activeChatSessionId === session.session_id;
                  return (
                    <button
                      key={session.session_id}
                      type="button"
                      onClick={() => { fetchChatHistory(session.session_id); setShowSessions(false); }}
                      className={`block w-full truncate rounded-md px-2.5 py-2 text-left text-[11px] font-medium ${isActive ? 'bg-slate-100 text-slate-900' : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'}`}
                      title={session.title}
                    >
                      {session.title}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
        
        <div className="flex-1" />
        
        {selectedFile && mode !== 'floating' && (
          <div className="flex items-center gap-1.5 text-[11px] text-slate-500">
            <FileText className="h-3.5 w-3.5" />
            <span className="font-medium text-slate-700">{selectedFile.split(/[\\/]/).pop()}</span>
          </div>
        )}
      </div>

      {/* Messages */}
      <div className={`flex-1 min-h-0 overflow-x-hidden overflow-y-auto bg-white ${mode === 'standalone' ? 'px-8 sm:px-12 lg:px-24 xl:px-40' : 'px-5'} py-4`}>
        <div className="space-y-6 max-w-3xl mx-auto w-full">
          {chatMessages.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-50 mb-3 border border-slate-100">
                <Bot className="h-6 w-6 text-slate-300" />
              </div>
              <p className="text-sm font-medium text-slate-500">How can I help you today?</p>
              <p className="mt-1 text-xs text-slate-400">Ask about architecture, features, or debug code</p>
            </div>
          )}
          {chatMessages.map((message: ChatMessageRecord, index) => (
            <div key={message.id ?? `${message.role}-${index}`} className={message.role === 'user'
              ? 'ml-auto max-w-[85%] rounded-[20px] bg-[#f4f4f5] border border-slate-200/50 px-5 py-3.5 text-[13px] leading-relaxed text-slate-900 shadow-sm'
              : 'pr-4 w-full text-[14px] leading-relaxed text-slate-800'
            }>
              {message.role === 'assistant' && (
                <div className="mb-2 flex items-center gap-2">
                  <div className="flex h-5 w-5 items-center justify-center rounded bg-black text-white">
                    <Sparkles className="h-3 w-3" />
                  </div>
                  <span className="text-xs font-semibold text-slate-900">DevHub</span>
                </div>
              )}
              <div className={`${message.role === 'assistant' ? 'pl-7' : 'whitespace-pre-wrap break-words'}`}>
                {message.role === 'assistant' ? renderMarkdownMessage(message.content) : message.content}
              </div>
              {message.role === 'assistant' && renderTrace(message.metadata)}
            </div>
          ))}
          {chatSending && (
            <div className="flex items-center gap-2.5 pl-7 text-sm text-slate-400 font-medium">
              <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
              Thinking...
            </div>
          )}
          <div ref={chatEndRef} />
        </div>
      </div>

      {/* Input */}
      <div className={`shrink-0 bg-white ${mode === 'standalone' ? 'px-8 sm:px-12 lg:px-24 xl:px-40 pb-8' : 'px-5 pb-5'} pt-2`}>
        <div className="max-w-3xl mx-auto w-full">
          {contextMentions.length > 0 && (
            <div className="mb-2.5 flex flex-wrap gap-1.5">
              {contextMentions.map((item) => (
                <button
                  key={`${item.type}-${item.value}`}
                  type="button"
                  onClick={() => removeMention(item)}
                  className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-medium text-slate-600 shadow-sm hover:bg-slate-50 transition"
                >
                  @{item.value} <X className="inline h-3 w-3 opacity-50 ml-0.5" />
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
              className="min-h-[56px] w-full resize-none rounded-[20px] border border-slate-200 bg-[#fbfbfc] py-4 pl-4 pr-12 text-[13px] text-slate-900 placeholder:text-slate-400 shadow-sm outline-none transition-all placeholder:font-light focus:border-slate-300 focus:bg-white focus:shadow-[0_4px_24px_rgba(15,23,42,0.06)]"
              rows={2}
            />
            <button onClick={sendChat} disabled={!chatInput.trim() || chatSending} className="absolute bottom-2 right-2 flex h-10 w-10 items-center justify-center rounded-2xl bg-black text-white shadow-sm transition hover:bg-slate-800 disabled:opacity-30">
              <Send className="h-4 w-4" />
            </button>
            {mentionQuery !== null && mentionOptions.length > 0 && (
              <div className="absolute bottom-[calc(100%+8px)] left-0 right-0 max-h-56 overflow-y-auto rounded-2xl border border-slate-200 bg-white p-1.5 shadow-lg">
                {mentionOptions.map((item) => (
                  <button
                    key={`${item.type}-${item.value}`}
                    type="button"
                    onClick={() => insertMention(item)}
                    className="flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-xs text-slate-700 hover:bg-slate-50"
                  >
                    <span className="truncate font-medium">{item.label}</span>
                    <span className="ml-3 shrink-0 text-[10px] text-slate-400 capitalize">{item.type}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          
          <div className="mt-3 flex items-center justify-between text-[10.5px] font-medium text-slate-400">
            <div className="flex gap-3">
              {CHAT_SPECIAL_MENTIONS.slice(0, 3).map((item) => (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => insertMention(item)}
                  className="hover:text-slate-600 transition-colors"
                >
                  {item.label}
                </button>
              ))}
            </div>
            <span>DevHub AI Assistant</span>
          </div>
        </div>
      </div>
    </div>
  );
}
