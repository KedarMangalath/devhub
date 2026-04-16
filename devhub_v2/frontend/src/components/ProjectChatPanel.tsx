import { useEffect, useRef, useState } from 'react';
import { Bot, ChevronDown, Clock, FileText, ImagePlus, Loader2, MessageSquarePlus, PanelLeftClose, PanelRightClose, RotateCcw, Send, Sparkles, Terminal, Wrench, X, Zap } from 'lucide-react';

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

type ChatBehaviorMode = 'ask' | 'edit' | 'agent';

type ChatImageAttachment = {
  name: string;
  mime_type: string;
  data_url: string;
  size_bytes?: number;
};

const CHAT_MODE_META: Record<ChatBehaviorMode, { label: string; helper: string; placeholder: string }> = {
  ask: {
    label: 'Ask',
    helper: 'Answer only. No file edits or sandbox actions.',
    placeholder: 'Ask about @codebase, @readme, or a selected file...',
  },
  edit: {
    label: 'Edit',
    helper: 'Apply code changes directly to the workspace files.',
    placeholder: 'Describe the code change you want applied to this project...',
  },
  agent: {
    label: 'Agent',
    helper: 'Execution-first mode. Applies code changes by default, and can run setup, restart the app, and use the sandbox.',
    placeholder: 'Tell the agent what to build, edit, run, migrate, or restart...',
  },
};

export type FileNodeObj = {
  name: string;
  type: 'directory' | 'file';
  path: string;
  children?: FileNodeObj[];
  loaded?: boolean;
};

export type CoderCustomizationSkill = {
  name: string;
  slug: string;
  description: string;
  path: string;
};

export type CoderCustomizationPromptOverride = {
  name: string;
  path: string;
  summary: string;
};

export type CoderCustomization = {
  available?: boolean;
  meta_root?: string;
  meta_path?: string;
  summary?: string;
  skills?: CoderCustomizationSkill[];
  prompt_overrides?: CoderCustomizationPromptOverride[];
  slash_commands?: string[];
  suggested_files?: string[];
  can_bootstrap?: boolean;
};

type Props = {
  projectId: string;
  mode?: 'floating' | 'standalone' | 'workspace';
  
  // Context passed by Workspace
  selectedFile?: string | null;
  fileContent?: string;
  treeNodes?: FileNodeObj[];
  coderCustomization?: CoderCustomization | null;
  
  // Callbacks
  onCodeApplied?: (appliedFiles: string[]) => void;
  onAgentAction?: (actions: any[]) => void;
  onCustomizationChanged?: () => void;
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

const MAX_CHAT_ATTACHMENTS = 3;
const MAX_CHAT_ATTACHMENT_BYTES = 4 * 1024 * 1024;
const SUPPORTED_CHAT_ATTACHMENT_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp', 'image/gif']);

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

const currentSlashSkillQuery = (value: string) => {
  const trimmed = String(value || '').trimStart();
  const match = trimmed.match(/^\/([^\s/]*)$/);
  return match ? match[1] : null;
};

const skillCommandLabel = (skill: CoderCustomizationSkill) => {
  const base = String(skill.slug || skill.name || '').trim();
  return base ? `/${base}` : '/skill';
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

const readFileAsDataUrl = (file: File) => new Promise<string>((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => resolve(String(reader.result || ''));
  reader.onerror = () => reject(reader.error || new Error(`Unable to read ${file.name}`));
  reader.readAsDataURL(file);
});

const normalizeMessageAttachments = (metadata: any): ChatImageAttachment[] => {
  const attachments = Array.isArray(metadata?.attachments) ? metadata.attachments : [];
  return attachments
    .filter((item: any) => item && typeof item === 'object' && typeof item.data_url === 'string')
    .map((item: any) => ({
      name: String(item.name || 'image'),
      mime_type: String(item.mime_type || item.mimeType || 'image/png'),
      data_url: String(item.data_url || item.dataUrl || ''),
      size_bytes: Number.isFinite(Number(item.size_bytes ?? item.sizeBytes)) ? Number(item.size_bytes ?? item.sizeBytes) : undefined,
    }));
};

export default function ProjectChatPanel({ projectId, mode = 'floating', selectedFile, fileContent, treeNodes = [], coderCustomization, onCodeApplied, onAgentAction, onCustomizationChanged, onToggleChat, chatOpen = true }: Props) {
  const [chatExpanded, setChatExpanded] = useState(false);
  const [chatMessages, setChatMessages] = useState<any[]>([]);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [activeChatSessionId, setActiveChatSessionId] = useState<string | null>(null);
  const [chatInput, setChatInput] = useState('');
  const [chatAttachments, setChatAttachments] = useState<ChatImageAttachment[]>([]);
  const [chatSending, setChatSending] = useState(false);
  const [undoingChangesetId, setUndoingChangesetId] = useState<string | null>(null);
  const [attachmentError, setAttachmentError] = useState('');
  const [contextMentions, setContextMentions] = useState<MentionItem[]>([]);
  const [showSessions, setShowSessions] = useState(false);
  const [bootstrappingKit, setBootstrappingKit] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const attachmentInputRef = useRef<HTMLInputElement>(null);
  const wasChatOpenRef = useRef(false);
  const [chatBehaviorMode, setChatBehaviorMode] = useState<ChatBehaviorMode>(() => (mode === 'workspace' ? 'agent' : 'ask'));

  const mentionQuery = currentMentionQuery(chatInput);
  const slashSkillQuery = currentSlashSkillQuery(chatInput);
  const currentModeMeta = CHAT_MODE_META[chatBehaviorMode];
  const availableSkills = Array.isArray(coderCustomization?.skills) ? coderCustomization.skills : [];
  const promptOverrides = Array.isArray(coderCustomization?.prompt_overrides) ? coderCustomization.prompt_overrides : [];
  const slashCommands = Array.isArray(coderCustomization?.slash_commands) ? coderCustomization.slash_commands : [];
  const suggestedFiles = Array.isArray(coderCustomization?.suggested_files) ? coderCustomization.suggested_files : [];
  const metaPath = String(coderCustomization?.meta_path || '').trim();
  const canBootstrapCustomization = Boolean(coderCustomization?.can_bootstrap);
  const hasCoderCustomization = Boolean(coderCustomization?.available || availableSkills.length || promptOverrides.length);
  const activePlaceholder = (chatBehaviorMode === 'edit' || chatBehaviorMode === 'agent') && availableSkills.length
    ? `Start with ${skillCommandLabel(availableSkills[0])} to apply a project skill, or describe the change directly...`
    : currentModeMeta.placeholder;
  const mentionOptions = [...CHAT_SPECIAL_MENTIONS, ...flattenTreeNodes(treeNodes)]
    .filter((item, index, source) => index === source.findIndex((candidate) => candidate.type === item.type && candidate.value === item.value))
    .filter((item) => !mentionQuery || item.label.toLowerCase().includes(`@${mentionQuery.toLowerCase()}`))
    .slice(0, 12);
  const skillOptions = availableSkills
    .filter((item) => {
      if (slashSkillQuery === null) return false;
      const command = skillCommandLabel(item).toLowerCase();
      const query = slashSkillQuery.toLowerCase();
      return command.includes(`/${query}`) || item.name.toLowerCase().includes(query) || item.description.toLowerCase().includes(query);
    })
    .slice(0, 8);

  const fetchChatHistory = async (sessionId?: string | null, options?: { fresh?: boolean }) => {
    const params = new URLSearchParams();
    if (sessionId) params.set('session_id', sessionId);
    if (options?.fresh) params.set('fresh', '1');
    const query = params.toString() ? `?${params.toString()}` : '';
    const response = await fetch(`${API}/projects/${projectId}/chat/${query}`);
    const data = await response.json();
    setChatSessions(data.sessions ?? []);
    setActiveChatSessionId(data.active_session_id ?? sessionId ?? null);
    setChatMessages(data.messages ?? []);
  };

  useEffect(() => {
    const isVisible = chatOpen || mode === 'standalone';
    const justOpened = isVisible && !wasChatOpenRef.current;
    if (projectId && isVisible) {
      void fetchChatHistory(null, { fresh: justOpened || !activeChatSessionId });
    }
    wasChatOpenRef.current = isVisible;
  }, [projectId, chatOpen, mode]);

  useEffect(() => {
    if (chatOpen || mode === 'standalone') {
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatMessages, chatOpen, mode]);

  useEffect(() => {
    const storageKey = `devhub.chat.behavior.${mode}`;
    const stored = window.localStorage.getItem(storageKey);
    if (stored === 'ask' || stored === 'edit' || stored === 'agent') {
      setChatBehaviorMode(stored);
      return;
    }
    setChatBehaviorMode(mode === 'workspace' ? 'agent' : 'ask');
  }, [mode]);

  useEffect(() => {
    window.localStorage.setItem(`devhub.chat.behavior.${mode}`, chatBehaviorMode);
  }, [chatBehaviorMode, mode]);

  const startNewChat = () => {
    setActiveChatSessionId(null);
    setChatMessages([]);
    setChatInput('');
    setChatAttachments([]);
    setAttachmentError('');
    setContextMentions([]);
    setShowSessions(false);
    if (projectId) {
      void fetchChatHistory(null, { fresh: true });
    }
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

  const insertSkillShortcut = (skill: CoderCustomizationSkill) => {
    const command = skillCommandLabel(skill);
    setChatInput((current) => {
      const leadingWhitespace = current.match(/^\s*/)?.[0] ?? '';
      const trimmed = current.trimStart();
      if (!trimmed) {
        return `${command} `;
      }
      if (/^\/[^\s/]*$/.test(trimmed)) {
        return `${leadingWhitespace}${command} `;
      }
      if (/^\/[^\s/]+(?:\s.*)?$/.test(trimmed)) {
        const remainder = trimmed.replace(/^\/[^\s/]+/, '').trimStart();
        return `${leadingWhitespace}${command}${remainder ? ` ${remainder}` : ' '}`;
      }
      return `${leadingWhitespace}${command} ${trimmed}`;
    });
  };

  const bootstrapCustomization = async () => {
    if (bootstrappingKit) return;
    setBootstrappingKit(true);
    try {
      const response = await fetch(`${API}/projects/${projectId}/coder-customization/bootstrap/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await response.json();
      if (!response.ok || data?.error) {
        throw new Error(data?.error || 'Unable to enable the project kit.');
      }
      await onCustomizationChanged?.();
      setChatMessages((current) => [
        ...current,
        {
          role: 'assistant',
          content: `Enabled the project kit in ${data?.coder_customization?.meta_root || '.devhub'}. You can now use slash skills like ${(data?.coder_customization?.slash_commands || []).join(', ') || '/debugging'}.`,
          metadata: {
            approach: 'Seeded starter prompt overrides and skills for the current project so coder customization is now visible and usable.',
            workspace_actions: [
              {
                type: 'project_kit_bootstrap',
                status: 'completed',
                detail: `Created ${(data?.created || []).length} customization files.`,
              },
            ],
          },
        },
      ]);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to enable the project kit.';
      setChatMessages((current) => [
        ...current,
        { role: 'assistant', content: message, metadata: { error: 'project_kit_bootstrap_failed' } },
      ]);
    } finally {
      setBootstrappingKit(false);
    }
  };

  const attachImages = async (fileList: FileList | null) => {
    if (!fileList?.length) return;
    const existing = chatAttachments.length;
    const availableSlots = MAX_CHAT_ATTACHMENTS - existing;

    if (availableSlots <= 0) {
      setAttachmentError(`You can attach up to ${MAX_CHAT_ATTACHMENTS} images per message.`);
      if (attachmentInputRef.current) attachmentInputRef.current.value = '';
      return;
    }

    const files = Array.from(fileList);
    const acceptedFiles = files.filter((file) => SUPPORTED_CHAT_ATTACHMENT_TYPES.has(file.type));
    const oversizedFiles = acceptedFiles.filter((file) => file.size > MAX_CHAT_ATTACHMENT_BYTES);
    const filesToRead = acceptedFiles.filter((file) => file.size <= MAX_CHAT_ATTACHMENT_BYTES).slice(0, availableSlots);

    try {
      const loaded = await Promise.all(
        filesToRead.map(async (file) => ({
          name: file.name,
          mime_type: file.type,
          size_bytes: file.size,
          data_url: await readFileAsDataUrl(file),
        })),
      );
      setChatAttachments((current) => [...current, ...loaded]);

      const invalidTypeCount = files.length - acceptedFiles.length;
      if (oversizedFiles.length > 0) {
        setAttachmentError('Each image must be 4 MB or smaller.');
      } else if (invalidTypeCount > 0) {
        setAttachmentError('Only PNG, JPEG, WEBP, and GIF images are supported.');
      } else if (files.length > filesToRead.length) {
        setAttachmentError(`Only the first ${availableSlots} additional image${availableSlots === 1 ? '' : 's'} were attached.`);
      } else {
        setAttachmentError('');
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to attach those images.';
      setAttachmentError(message);
    } finally {
      if (attachmentInputRef.current) attachmentInputRef.current.value = '';
    }
  };

  const removeChatAttachment = (target: ChatImageAttachment) => {
    setChatAttachments((current) => current.filter((item) => item.data_url !== target.data_url));
    setAttachmentError('');
  };

  const undoMetaFromTrace = (trace: any) => {
    if (!trace || typeof trace !== 'object') return null;
    const undo = trace.undo && typeof trace.undo === 'object' ? trace.undo : null;
    const changesetId = String(trace.changeset_id || undo?.changeset_id || '').trim();
    if (!undo || !changesetId) return null;
    return {
      available: Boolean(undo?.available),
      changesetId,
      label: String(undo?.label || 'Undo'),
    };
  };

  const undoChatExecution = async (changesetId: string) => {
    const normalizedId = String(changesetId || '').trim();
    if (!normalizedId || undoingChangesetId) return;
    setUndoingChangesetId(normalizedId);

    try {
      const response = await fetch(`${API}/projects/${projectId}/chat/undo/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          changeset_id: normalizedId,
          session_id: activeChatSessionId,
        }),
      });
      const data = await response.json();
      if (!response.ok || data?.error) {
        throw new Error(data?.error || 'Unable to undo that change.');
      }

      setActiveChatSessionId(data.session_id ?? activeChatSessionId ?? null);
      setChatSessions(data.sessions ?? []);
      setChatMessages((current) => {
        const updated = current.map((message) => {
          if (message.role !== 'assistant' || !message.metadata || typeof message.metadata !== 'object') {
            return message;
          }
          const metadata = { ...message.metadata };
          const undo = metadata.undo && typeof metadata.undo === 'object' ? { ...metadata.undo } : null;
          const messageChangesetId = String(metadata.changeset_id || undo?.changeset_id || '').trim();
          if (messageChangesetId !== normalizedId) {
            return message;
          }
          metadata.undo_available = false;
          metadata.undo = {
            ...(undo || {}),
            available: false,
            changeset_id: normalizedId,
          };
          return { ...message, metadata };
        });
        return [
          ...updated,
          {
            role: 'assistant',
            content: data.assistant_message ?? 'Undo completed.',
            metadata: data.trace ?? {},
            session_id: data.session_id ?? activeChatSessionId,
          },
        ];
      });

      if (data.applied_changes?.applied_files?.length && onCodeApplied) {
        onCodeApplied(data.applied_changes.applied_files);
      }
      if (data.workspace_actions?.length && onAgentAction) {
        onAgentAction(data.workspace_actions);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to undo that change.';
      setChatMessages((current) => [...current, { role: 'assistant', content: message, metadata: { error: 'undo_failed' } }]);
    } finally {
      setUndoingChangesetId(null);
    }
  };

  const renderTrace = (trace: any) => {
    if (!trace || typeof trace !== 'object') return null;
    const contextItems = Array.isArray(trace.context_mentions) ? trace.context_mentions : [];
    const filesAccessed = Array.isArray(trace.files_accessed) ? trace.files_accessed : [];
    const commandsRan = Array.isArray(trace.commands_ran) ? trace.commands_ran : [];
    const semanticHits = Array.isArray(trace.semantic_hits) ? trace.semantic_hits : [];
    const appliedFiles = Array.isArray(trace.applied_files) ? trace.applied_files : [];
    const workspaceActions = Array.isArray(trace.workspace_actions) ? trace.workspace_actions : [];
    const plan = trace.plan && typeof trace.plan === 'object' ? trace.plan : null;
    const review = trace.review && typeof trace.review === 'object' ? trace.review : null;
    const planObjective = typeof plan?.objective === 'string' ? plan.objective.trim() : '';
    const planSteps = Array.isArray(plan?.implementation_steps) ? plan.implementation_steps.filter(Boolean) : [];
    const planFiles = Array.isArray(plan?.relevant_files) ? plan.relevant_files.filter(Boolean) : [];
    const planCommands = Array.isArray(plan?.validation_commands) ? plan.validation_commands.filter(Boolean) : [];
    const reviewSummary = typeof review?.summary === 'string' ? review.summary.trim() : '';
    const reviewIssues = Array.isArray(review?.issues) ? review.issues.filter(Boolean) : [];
    const reviewScore = Number.isFinite(Number(review?.score)) ? Number(review.score) : null;
    const reviewApproved = Boolean(review?.approved);
    const traceMode = typeof trace.chat_mode === 'string' ? trace.chat_mode : '';
    const undoMeta = undoMetaFromTrace(trace);
    const undoBusy = undoingChangesetId === undoMeta?.changesetId;
    const traceSummary = [
      traceMode ? traceMode : '',
      filesAccessed.length ? `${filesAccessed.length} files` : '',
      commandsRan.length ? `${commandsRan.length} commands` : '',
      workspaceActions.length ? `${workspaceActions.length} actions` : '',
      semanticHits.length ? `${semanticHits.length} hits` : '',
      appliedFiles.length ? `${appliedFiles.length} edits` : '',
    ].filter(Boolean).join(' | ');
    
    return (
      <>
        {(planObjective || planSteps.length || planFiles.length || planCommands.length) && (
          <div className={`mt-3 ml-7 rounded-2xl border px-3.5 py-3 shadow-sm ${isWorkspaceMode ? 'border-[#2a2a2a] bg-[#101010] text-[#dbe4ee]' : 'border-slate-200 bg-white text-slate-700'}`}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className={`text-[10px] font-semibold uppercase tracking-[0.16em] ${isWorkspaceMode ? 'text-[#64748b]' : 'text-slate-400'}`}>Implementation Plan</p>
                {planObjective && <p className={`mt-1 text-[12px] leading-6 ${isWorkspaceMode ? 'text-[#cbd5e1]' : 'text-slate-600'}`}>{planObjective}</p>}
              </div>
              <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${isWorkspaceMode ? 'bg-blue-500/15 text-blue-200' : 'bg-blue-50 text-blue-700'}`}>
                {planSteps.length || planFiles.length} items
              </span>
            </div>
            {planFiles.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {planFiles.slice(0, 6).map((file: string) => (
                  <span key={file} className={`rounded-full px-2.5 py-1 text-[10px] font-medium ${isWorkspaceMode ? 'border border-white/10 bg-white/5 text-[#cbd5e1]' : 'border border-slate-200 bg-slate-50 text-slate-600'}`}>
                    {file}
                  </span>
                ))}
              </div>
            )}
            {planSteps.length > 0 && (
              <div className="mt-3 space-y-1.5">
                {planSteps.slice(0, 4).map((step: string, index: number) => (
                  <div key={`${step}-${index}`} className={`rounded-xl px-3 py-2 text-[11px] leading-5 ${isWorkspaceMode ? 'bg-white/5 text-[#dbe4ee]' : 'bg-slate-50 text-slate-600'}`}>
                    <span className={`mr-2 inline-flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-semibold ${isWorkspaceMode ? 'bg-white/10 text-white' : 'bg-white text-slate-500 shadow-sm'}`}>{index + 1}</span>
                    {step}
                  </div>
                ))}
              </div>
            )}
            {planCommands.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {planCommands.slice(0, 3).map((command: string) => (
                  <code key={command} className={`rounded-lg px-2.5 py-1.5 text-[10px] ${isWorkspaceMode ? 'bg-[#0b1220] text-emerald-300' : 'bg-slate-900 text-emerald-300'}`}>{command}</code>
                ))}
              </div>
            )}
          </div>
        )}
        {(reviewSummary || reviewIssues.length || reviewScore !== null) && (
          <div className={`mt-3 ml-7 rounded-2xl border px-3.5 py-3 shadow-sm ${isWorkspaceMode ? 'border-[#2a2a2a] bg-[#101010] text-[#dbe4ee]' : 'border-slate-200 bg-white text-slate-700'}`}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className={`text-[10px] font-semibold uppercase tracking-[0.16em] ${isWorkspaceMode ? 'text-[#64748b]' : 'text-slate-400'}`}>Review Result</p>
                {reviewSummary && <p className={`mt-1 text-[12px] leading-6 ${isWorkspaceMode ? 'text-[#cbd5e1]' : 'text-slate-600'}`}>{reviewSummary}</p>}
              </div>
              <div className="flex items-center gap-2">
                {reviewScore !== null && (
                  <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${reviewApproved ? (isWorkspaceMode ? 'bg-emerald-500/15 text-emerald-200' : 'bg-emerald-50 text-emerald-700') : (isWorkspaceMode ? 'bg-amber-500/15 text-amber-200' : 'bg-amber-50 text-amber-700')}`}>
                    Score {reviewScore}
                  </span>
                )}
                <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${reviewApproved ? (isWorkspaceMode ? 'bg-emerald-500/15 text-emerald-200' : 'bg-emerald-50 text-emerald-700') : (isWorkspaceMode ? 'bg-rose-500/15 text-rose-200' : 'bg-rose-50 text-rose-700')}`}>
                  {reviewApproved ? 'Approved' : 'Needs work'}
                </span>
              </div>
            </div>
            {reviewIssues.length > 0 && (
              <div className="mt-3 space-y-2">
                {reviewIssues.slice(0, 3).map((issue: any, index: number) => (
                  <div key={`${issue.file || 'issue'}-${index}`} className={`rounded-xl px-3 py-2.5 text-[11px] leading-5 ${isWorkspaceMode ? 'bg-white/5 text-[#dbe4ee]' : 'bg-slate-50 text-slate-600'}`}>
                    <div className="flex items-center justify-between gap-3">
                      <span className={`font-semibold uppercase tracking-[0.12em] ${isWorkspaceMode ? 'text-[#94a3b8]' : 'text-slate-400'}`}>{issue.severity || 'issue'}</span>
                      {issue.file && <code className={`truncate text-[10px] ${isWorkspaceMode ? 'text-[#cbd5e1]' : 'text-slate-500'}`}>{issue.file}</code>}
                    </div>
                    {issue.description && <p className="mt-1">{issue.description}</p>}
                    {issue.suggestion && <p className={`mt-1 ${isWorkspaceMode ? 'text-[#94a3b8]' : 'text-slate-500'}`}>{issue.suggestion}</p>}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        {undoMeta?.available && (
          <div className={`mt-3 ml-7 flex items-center justify-between gap-3 rounded-2xl border px-3.5 py-3 shadow-sm ${isWorkspaceMode ? 'border-[#2a2a2a] bg-[#101010] text-[#dbe4ee]' : 'border-slate-200 bg-white text-slate-700'}`}>
            <div>
              <p className={`text-[10px] font-semibold uppercase tracking-[0.16em] ${isWorkspaceMode ? 'text-[#64748b]' : 'text-slate-400'}`}>Checkpoint</p>
              <p className={`mt-1 text-[12px] leading-6 ${isWorkspaceMode ? 'text-[#cbd5e1]' : 'text-slate-600'}`}>
                Restore the workspace to the snapshot captured before this execution.
              </p>
            </div>
            <button
              type="button"
              onClick={() => { void undoChatExecution(undoMeta.changesetId); }}
              disabled={undoBusy}
              className={`inline-flex items-center gap-2 rounded-xl px-3 py-2 text-[11px] font-semibold transition disabled:opacity-50 ${isWorkspaceMode ? 'border border-white/10 bg-white/10 text-white hover:bg-white/15' : 'border border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100'}`}
            >
              {undoBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
              {undoBusy ? 'Restoring...' : undoMeta.label}
            </button>
          </div>
        )}
        {/* ── Tool Events Timeline (from new QueryEngine) ── */}
        {Array.isArray(trace.tool_events) && trace.tool_events.length > 0 && (
          <div className={`mt-3 ml-7 rounded-2xl border px-3.5 py-3 shadow-sm ${isWorkspaceMode ? 'border-[#2a2a2a] bg-[#101010] text-[#dbe4ee]' : 'border-slate-200 bg-white text-slate-700'}`}>
            <div className="flex items-center justify-between gap-3 mb-3">
              <div className="flex items-center gap-2">
                <Zap className={`h-3.5 w-3.5 ${isWorkspaceMode ? 'text-amber-300' : 'text-amber-500'}`} />
                <p className={`text-[10px] font-semibold uppercase tracking-[0.16em] ${isWorkspaceMode ? 'text-[#64748b]' : 'text-slate-400'}`}>Agent Tool Execution</p>
              </div>
              <div className="flex items-center gap-2">
                {typeof trace.turns_used === 'number' && (
                  <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold ${isWorkspaceMode ? 'bg-blue-500/15 text-blue-200' : 'bg-blue-50 text-blue-700'}`}>
                    {trace.turns_used} turns
                  </span>
                )}
                {typeof trace.duration_ms === 'number' && (
                  <span className={`rounded-full px-2.5 py-1 text-[10px] font-medium ${isWorkspaceMode ? 'bg-white/10 text-[#94a3b8]' : 'bg-slate-100 text-slate-500'}`}>
                    <Clock className="inline h-3 w-3 mr-1 -mt-px" />
                    {trace.duration_ms > 1000 ? `${(trace.duration_ms / 1000).toFixed(1)}s` : `${trace.duration_ms}ms`}
                  </span>
                )}
                {trace.compacted && (
                  <span className={`rounded-full px-2.5 py-1 text-[10px] font-medium ${isWorkspaceMode ? 'bg-purple-500/15 text-purple-200' : 'bg-purple-50 text-purple-700'}`}>
                    compacted
                  </span>
                )}
              </div>
            </div>
            <div className="space-y-1">
              {trace.tool_events.filter((ev: any) => ev.type === 'tool_end').map((ev: any, idx: number) => (
                <div key={idx} className={`flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 ${isWorkspaceMode ? 'bg-white/5' : 'bg-slate-50'}`}>
                  <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-md ${ev.success ? (isWorkspaceMode ? 'bg-emerald-500/20 text-emerald-300' : 'bg-emerald-100 text-emerald-600') : (isWorkspaceMode ? 'bg-rose-500/20 text-rose-300' : 'bg-rose-100 text-rose-600')}`}>
                    {ev.tool === 'bash' ? <Terminal className="h-3 w-3" /> : <Wrench className="h-3 w-3" />}
                  </span>
                  <span className={`text-[11px] font-semibold ${isWorkspaceMode ? 'text-white' : 'text-slate-800'}`}>{ev.tool}</span>
                  <span className={`flex-1 truncate text-[10px] ${isWorkspaceMode ? 'text-[#94a3b8]' : 'text-slate-400'}`}>{ev.preview?.slice(0, 80)}</span>
                  <span className={`shrink-0 text-[10px] font-medium ${ev.success ? (isWorkspaceMode ? 'text-emerald-300' : 'text-emerald-600') : (isWorkspaceMode ? 'text-rose-300' : 'text-rose-600')}`}>
                    {ev.success ? '✓' : '✗'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
        <details className={`mt-3 ml-7 rounded-2xl border text-[11px] transition-colors shadow-sm w-fit min-w-[200px] max-w-full ${isWorkspaceMode ? 'border-[#2a2a2a] bg-[#101010] text-[#94a3b8] hover:border-[#3a3a3a]' : 'border-slate-100 bg-white text-slate-500 hover:border-slate-200'}`}>
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
          {workspaceActions.length > 0 && (
            <details className="rounded-xl border border-white bg-white px-3 py-2.5 shadow-sm">
              <summary className="cursor-pointer list-none text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                Workspace Actions | {workspaceActions.length}
              </summary>
              <div className="mt-2.5 space-y-1.5">
                {workspaceActions.slice(0, 8).map((item: any, index: number) => (
                  <div key={`${item.type || 'action'}-${index}`} className="rounded-lg border border-slate-100 bg-slate-50 px-2.5 py-2">
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">{item.type || 'action'}</span>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${item.status === 'failed' ? 'bg-rose-100 text-rose-700' : item.status === 'running' ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}`}>
                        {item.status || 'completed'}
                      </span>
                    </div>
                    {item.command && <code className="mt-1 block whitespace-pre-wrap break-words text-[10px] font-medium text-slate-700">{item.command}</code>}
                    {item.detail && <p className="mt-1 text-[10px] leading-5 text-slate-500">{item.detail}</p>}
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
      </>
    );
  };

  const renderImageAttachments = (attachments: ChatImageAttachment[], userRole: 'user' | 'assistant') => {
    if (!attachments.length) return null;
    const containerPadding = userRole === 'assistant' ? 'pl-7' : '';
    return (
      <div className={`${containerPadding} ${userRole === 'assistant' ? 'mb-3' : 'mb-2.5'}`}>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {attachments.map((attachment) => (
            <figure key={`${attachment.name}-${attachment.data_url.slice(-24)}`} className={`overflow-hidden rounded-2xl border ${isWorkspaceMode ? 'border-white/10 bg-white/5' : 'border-slate-200 bg-white shadow-sm'}`}>
              <img
                src={attachment.data_url}
                alt={attachment.name}
                className="h-28 w-full object-cover"
                loading="lazy"
              />
              <figcaption className={`truncate px-2.5 py-2 text-[10px] font-medium ${isWorkspaceMode ? 'text-[#cbd5e1]' : 'text-slate-600'}`} title={attachment.name}>
                {attachment.name}
              </figcaption>
            </figure>
          ))}
        </div>
      </div>
    );
  };

  const sendChat = async () => {
    if ((!chatInput.trim() && chatAttachments.length === 0) || chatSending) return;
    const content = chatInput.trim();
    const pendingAttachments = chatAttachments.map((item) => ({ ...item }));
    setChatInput('');
    setChatAttachments([]);
    setAttachmentError('');
    setChatSending(true);
    setChatMessages((current) => [...current, { role: 'user', content, metadata: { context_mentions: contextMentions, selected_file: selectedFile, chat_mode: chatBehaviorMode, attachments: pendingAttachments }, session_id: activeChatSessionId }]);
    
    try {
      const response = await fetch(`${API}/projects/${projectId}/chat/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content,
          mode: chatBehaviorMode,
          session_id: activeChatSessionId,
          selected_file: selectedFile,
          selected_content: selectedFile ? fileContent : '',
          context_mentions: contextMentions,
          attachments: pendingAttachments,
        }),
      });
      const data = await response.json();
      if (!response.ok || data?.error) {
        throw new Error(data?.error || 'Unable to send that chat message.');
      }
      setActiveChatSessionId(data.session_id ?? activeChatSessionId ?? null);
      setChatSessions(data.sessions ?? []);
      setChatMessages((current) => [...current, { role: 'assistant', content: data.assistant_message ?? 'No response.', metadata: data.trace ?? {}, session_id: data.session_id ?? activeChatSessionId }]);
      
      if (data.applied_changes?.applied_files?.length && onCodeApplied) {
        onCodeApplied(data.applied_changes.applied_files);
      }
      if (data.workspace_actions?.length && onAgentAction) {
        onAgentAction(data.workspace_actions);
      }
    } catch (error) {
      setChatAttachments(pendingAttachments);
      const message = error instanceof Error ? error.message : 'Connection failed.';
      setChatMessages((current) => [...current, { role: 'assistant', content: message, metadata: { error: 'connection_failed' } }]);
    } finally {
      setChatSending(false);
    }
  };

  if (!chatOpen && mode === 'floating') {
    return null;
  }

  const wrapperClasses = mode === 'standalone'
    ? 'flex h-full w-full flex-col bg-white text-slate-900'
    : mode === 'workspace'
      ? 'flex h-full min-h-0 w-[min(28rem,32vw)] min-w-[22rem] max-w-[32rem] shrink-0 flex-col overflow-hidden border-l border-[#333333] bg-[#181818] text-[#e5e7eb]'
      : `pointer-events-auto flex flex-col overflow-hidden border border-slate-200/60 bg-white shadow-2xl ${chatExpanded ? 'fixed inset-4 z-50 rounded-3xl' : 'rounded-2xl'}`;

  const wrapperStyles = mode === 'standalone' || mode === 'workspace'
    ? undefined
    : (chatExpanded ? undefined : { width: 440, height: 600, resize: 'both' as const, minWidth: 360, minHeight: 400, maxWidth: '92vw', maxHeight: '80vh' });

  const isWorkspaceMode = mode === 'workspace';

  return (
    <div className={wrapperClasses} style={wrapperStyles}>
      {/* Header */}
      {(mode === 'floating' || isWorkspaceMode) && (
        <div className={`flex shrink-0 items-center justify-between gap-3 px-5 py-3 ${isWorkspaceMode ? 'border-b border-[#2a2a2a] bg-[#111111]' : 'border-b border-slate-100'}`}>
          <div className="flex items-center gap-2">
            <div className={`flex h-7 w-7 items-center justify-center rounded-lg ${isWorkspaceMode ? 'bg-[#0f172a] ring-1 ring-white/10' : 'bg-black shadow-sm'}`}>
              <Sparkles className="h-3.5 w-3.5 text-white" />
            </div>
            <div>
              <h3 className={`text-[13px] font-medium ${isWorkspaceMode ? 'text-white' : 'text-slate-900'}`}>Coding Agent</h3>
              {isWorkspaceMode && (
                <p className="text-[10px] text-[#9ca3af]">Workspace-aware help, edits, and file context</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-1">
            {mode === 'floating' && (
              <button
                type="button"
                onClick={() => setChatExpanded((c) => !c)}
                className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-900"
                title={chatExpanded ? 'Minimize' : 'Expand'}
              >
                {chatExpanded ? <PanelLeftClose className="h-4 w-4" /> : <PanelRightClose className="h-4 w-4" />}
              </button>
            )}
            <button
              type="button"
              onClick={() => onToggleChat?.(false)}
              className={`rounded-md p-1.5 ${isWorkspaceMode ? 'text-[#9ca3af] hover:bg-white/5 hover:text-white' : 'text-slate-400 hover:bg-slate-100 hover:text-slate-900'}`}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Toolbar */}
      <div className={`relative flex shrink-0 items-center gap-2.5 px-5 py-3 ${mode === 'standalone' ? 'pt-8 pb-4' : ''} ${isWorkspaceMode ? 'border-b border-[#2a2a2a] bg-[#181818]' : ''}`}>
        {/* We only show title on standalone mode in the top bar to keep it anchored if they want */}
        {mode === 'standalone' && (
          <div className="mr-4 flex items-center gap-2.5 border-r border-slate-200 pr-5">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-black shadow-sm">
              <Sparkles className="h-3.5 w-3.5 text-white" />
            </div>
            <h3 className="text-sm font-semibold text-slate-900">Chat</h3>
          </div>
        )}

        <div className={`flex items-center rounded-xl p-1 ${isWorkspaceMode ? 'border border-white/10 bg-[#111111]' : 'border border-slate-200 bg-slate-50/80 shadow-sm'}`}>
          {(Object.entries(CHAT_MODE_META) as [ChatBehaviorMode, (typeof CHAT_MODE_META)[ChatBehaviorMode]][]).map(([value, meta]) => {
            const active = chatBehaviorMode === value;
            return (
              <button
                key={value}
                type="button"
                onClick={() => setChatBehaviorMode(value)}
                className={`rounded-lg px-3 py-1.5 text-[11px] font-semibold transition ${isWorkspaceMode ? (active ? 'bg-white text-black shadow-sm' : 'text-[#94a3b8] hover:bg-white/5 hover:text-white') : (active ? 'bg-black text-white shadow-sm' : 'text-slate-500 hover:bg-white hover:text-slate-900')}`}
                title={meta.helper}
              >
                {meta.label}
              </button>
            );
          })}
        </div>

        <button
          type="button"
          onClick={startNewChat}
          className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition ${isWorkspaceMode ? 'border border-white/10 bg-white/5 text-white hover:bg-white/10' : 'bg-black text-white shadow-sm hover:bg-slate-800'}`}
        >
          <MessageSquarePlus className="h-3.5 w-3.5" />
          New Chat
        </button>
        
        <div className="relative">
          <button
            type="button"
            onClick={() => setShowSessions(!showSessions)}
            className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition ${isWorkspaceMode ? 'border border-white/10 bg-[#111111] text-[#d1d5db] hover:bg-[#1f1f1f]' : 'border border-slate-200 bg-white text-slate-700 shadow-sm hover:bg-slate-50'}`}
          >
            History <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
          </button>
          {showSessions && chatSessions.length > 0 && (
            <div className={`absolute left-0 top-full z-10 mt-1.5 w-48 rounded-xl p-1.5 ${isWorkspaceMode ? 'border border-[#2a2a2a] bg-[#101010] shadow-[0_18px_40px_rgba(0,0,0,0.45)]' : 'border border-slate-150 bg-white shadow-lg'}`}>
              <div className="max-h-60 overflow-y-auto hidden-scrollbar">
                {chatSessions.map((session) => {
                  const isActive = activeChatSessionId === session.session_id;
                  return (
                    <button
                      key={session.session_id}
                      type="button"
                      onClick={() => { fetchChatHistory(session.session_id); setShowSessions(false); }}
                      className={`block w-full truncate rounded-md px-2.5 py-2 text-left text-[11px] font-medium ${isWorkspaceMode ? (isActive ? 'bg-white/10 text-white' : 'text-[#cbd5e1] hover:bg-white/5 hover:text-white') : (isActive ? 'bg-slate-100 text-slate-900' : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900')}`}
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
          <div className={`flex items-center gap-1.5 text-[11px] ${isWorkspaceMode ? 'text-[#94a3b8]' : 'text-slate-500'}`}>
            <FileText className="h-3.5 w-3.5" />
            <span className={`font-medium ${isWorkspaceMode ? 'text-white' : 'text-slate-700'}`}>{selectedFile.split(/[\\/]/).pop()}</span>
          </div>
        )}
      </div>

      {/* Messages */}
      <div className={`flex-1 min-h-0 overflow-x-hidden overflow-y-auto ${isWorkspaceMode ? 'bg-[#181818]' : 'bg-white'} ${mode === 'standalone' ? 'px-8 sm:px-12 lg:px-24 xl:px-40' : 'px-5'} py-4`}>
        <div className="space-y-6 max-w-3xl mx-auto w-full">
          <div className={`rounded-2xl border px-4 py-3 ${isWorkspaceMode ? 'border-white/10 bg-white/[0.03]' : 'border-slate-200 bg-slate-50/80 shadow-sm'}`}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className={`text-[10px] font-semibold uppercase tracking-[0.18em] ${isWorkspaceMode ? 'text-[#64748b]' : 'text-slate-400'}`}>Current Mode</p>
                <p className={`mt-1 text-sm font-medium ${isWorkspaceMode ? 'text-white' : 'text-slate-900'}`}>{currentModeMeta.label}</p>
              </div>
              <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${isWorkspaceMode ? (chatBehaviorMode === 'agent' ? 'bg-blue-500/15 text-blue-200' : chatBehaviorMode === 'edit' ? 'bg-emerald-500/15 text-emerald-200' : 'bg-slate-500/15 text-slate-200') : (chatBehaviorMode === 'agent' ? 'bg-blue-50 text-blue-700' : chatBehaviorMode === 'edit' ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600')}`}>
                {currentModeMeta.label}
              </span>
            </div>
            <p className={`mt-2 text-[12px] leading-6 ${isWorkspaceMode ? 'text-[#94a3b8]' : 'text-slate-500'}`}>{currentModeMeta.helper}</p>
          </div>

          <div className={`rounded-2xl border px-4 py-3 ${isWorkspaceMode ? 'border-[#1f3b63] bg-[linear-gradient(135deg,rgba(15,23,42,0.92),rgba(15,118,110,0.18))]' : 'border-[#dbeafe] bg-[linear-gradient(135deg,#eff6ff,#f8fafc)] shadow-sm'}`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className={`text-[10px] font-semibold uppercase tracking-[0.18em] ${isWorkspaceMode ? 'text-[#7dd3fc]' : 'text-sky-600'}`}>Project Kit</p>
                  <p className={`mt-1 text-sm font-medium ${isWorkspaceMode ? 'text-white' : 'text-slate-900'}`}>
                    {hasCoderCustomization
                      ? `${availableSkills.length} skill${availableSkills.length === 1 ? '' : 's'} and ${promptOverrides.length} prompt override${promptOverrides.length === 1 ? '' : 's'} loaded`
                      : 'No project-specific coder kit is loaded yet'}
                  </p>
                </div>
                <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${isWorkspaceMode ? 'bg-white/10 text-white' : 'bg-white text-slate-600 shadow-sm'}`}>
                  {coderCustomization?.meta_root || '.devhub'}
                </span>
              </div>
              {hasCoderCustomization && coderCustomization?.summary && (
                <p className={`mt-2 text-[12px] leading-6 ${isWorkspaceMode ? 'text-[#cbd5e1]' : 'text-slate-600'}`}>{coderCustomization.summary}</p>
              )}
              {hasCoderCustomization ? (
                <>
                  {availableSkills.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {availableSkills.slice(0, 6).map((skill) => (
                        <button
                          key={skill.path || skill.slug || skill.name}
                          type="button"
                          onClick={() => insertSkillShortcut(skill)}
                          className={`rounded-full px-3 py-1.5 text-[11px] font-medium transition ${isWorkspaceMode ? 'border border-white/10 bg-white/5 text-white hover:bg-white/10' : 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50'}`}
                          title={skill.description}
                        >
                          {skillCommandLabel(skill)}
                        </button>
                      ))}
                    </div>
                  )}
                  {promptOverrides.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {promptOverrides.slice(0, 6).map((item) => (
                        <span key={item.path || item.name} className={`rounded-full px-2.5 py-1 text-[10px] font-medium ${isWorkspaceMode ? 'border border-cyan-500/20 bg-cyan-500/10 text-cyan-100' : 'border border-sky-100 bg-sky-50 text-sky-700'}`} title={item.summary}>
                          {item.name}
                        </span>
                      ))}
                    </div>
                  )}
                  <p className={`mt-3 text-[11px] leading-5 ${isWorkspaceMode ? 'text-[#94a3b8]' : 'text-slate-500'}`}>
                    Start a request with a slash skill like {slashCommands[0] || '/skill'} to apply project-specific instructions before planning and coding.
                  </p>
                </>
              ) : (
                <>
                  <p className={`mt-2 text-[12px] leading-6 ${isWorkspaceMode ? 'text-[#cbd5e1]' : 'text-slate-600'}`}>
                    This project does not have any `.devhub` coder customization files yet, so there are no skill chips to show. Plan and review cards will appear after the first edit or agent response.
                  </p>
                  {metaPath && (
                    <p className={`mt-2 text-[11px] leading-5 ${isWorkspaceMode ? 'text-[#94a3b8]' : 'text-slate-500'}`}>
                      Target folder: <code className={`${isWorkspaceMode ? 'text-white' : 'text-slate-700'}`}>{metaPath}</code>
                    </p>
                  )}
                  {suggestedFiles.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {suggestedFiles.slice(0, 6).map((file) => (
                        <span key={file} className={`rounded-full px-2.5 py-1 text-[10px] font-medium ${isWorkspaceMode ? 'border border-white/10 bg-white/5 text-[#cbd5e1]' : 'border border-slate-200 bg-white text-slate-600'}`}>
                          {file}
                        </span>
                      ))}
                    </div>
                  )}
                  {canBootstrapCustomization && (
                    <button
                      type="button"
                      onClick={() => { void bootstrapCustomization(); }}
                      disabled={bootstrappingKit}
                      className={`mt-3 inline-flex items-center gap-2 rounded-xl px-3 py-2 text-[11px] font-semibold transition disabled:opacity-50 ${isWorkspaceMode ? 'border border-white/10 bg-white/10 text-white hover:bg-white/15' : 'bg-black text-white hover:bg-slate-800'}`}
                    >
                      {bootstrappingKit ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                      {bootstrappingKit ? 'Enabling Project Kit...' : 'Enable Project Kit'}
                    </button>
                  )}
                </>
              )}
            </div>

          {chatMessages.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className={`mb-3 flex h-12 w-12 items-center justify-center rounded-xl border ${isWorkspaceMode ? 'border-white/10 bg-white/5' : 'border-slate-100 bg-slate-50'}`}>
                <Bot className={`h-6 w-6 ${isWorkspaceMode ? 'text-[#64748b]' : 'text-slate-300'}`} />
              </div>
              <p className={`text-sm font-medium ${isWorkspaceMode ? 'text-[#cbd5e1]' : 'text-slate-500'}`}>How can I help you today?</p>
              <p className={`mt-1 text-xs ${isWorkspaceMode ? 'text-[#64748b]' : 'text-slate-400'}`}>{currentModeMeta.helper}</p>
            </div>
          )}
          {chatMessages.map((message: ChatMessageRecord, index) => (
            <div key={message.id ?? `${message.role}-${index}`} className={message.role === 'user'
              ? (isWorkspaceMode
                  ? 'ml-auto max-w-[90%] rounded-2xl border border-[#2f2f2f] bg-[#101010] px-4 py-3 text-[13px] leading-relaxed text-white shadow-[0_12px_30px_rgba(0,0,0,0.28)]'
                  : 'ml-auto max-w-[85%] rounded-[20px] border border-slate-200/50 bg-[#f4f4f5] px-5 py-3.5 text-[13px] leading-relaxed text-slate-900 shadow-sm')
              : (isWorkspaceMode ? 'w-full pr-2 text-[13px] leading-7 text-[#e2e8f0]' : 'pr-4 w-full text-[14px] leading-relaxed text-slate-800')
            }>
              {renderImageAttachments(normalizeMessageAttachments(message.metadata), message.role)}
              {message.role === 'assistant' && (
                <div className="mb-2 flex items-center gap-2">
                  <div className={`flex h-5 w-5 items-center justify-center rounded ${isWorkspaceMode ? 'bg-[#0f172a]' : 'bg-black'} text-white`}>
                    <Sparkles className="h-3 w-3" />
                  </div>
                  <span className={`text-xs font-semibold ${isWorkspaceMode ? 'text-white' : 'text-slate-900'}`}>DevHub</span>
                </div>
              )}
              {message.content && (
                <div className={`${message.role === 'assistant' ? 'pl-7' : 'whitespace-pre-wrap break-words'}`}>
                  {message.role === 'assistant' ? renderMarkdownMessage(message.content) : message.content}
                </div>
              )}
              {message.role === 'assistant' && renderTrace(message.metadata)}
            </div>
          ))}
          {chatSending && (
            <div className={`rounded-2xl border px-4 py-3 ml-7 ${isWorkspaceMode ? 'border-[#2a2a2a] bg-[#101010]' : 'border-slate-200 bg-slate-50/80'}`}>
              <div className="flex items-center gap-2.5">
                <div className={`flex h-6 w-6 items-center justify-center rounded-lg ${isWorkspaceMode ? 'bg-[#0f172a]' : 'bg-black'}`}>
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-white" />
                </div>
                <span className={`text-[13px] font-medium ${isWorkspaceMode ? 'text-white' : 'text-slate-900'}`}>
                  {chatBehaviorMode === 'agent' ? 'Agent is reading, searching, and editing...' : 'Thinking...'}
                </span>
              </div>
              {chatBehaviorMode === 'agent' && (
                <div className={`mt-2 flex items-center gap-3 pl-8 text-[11px] ${isWorkspaceMode ? 'text-[#64748b]' : 'text-slate-400'}`}>
                  <span className="flex items-center gap-1"><Wrench className="h-3 w-3" /> Tools</span>
                  <span className="flex items-center gap-1"><FileText className="h-3 w-3" /> Files</span>
                  <span className="flex items-center gap-1"><Terminal className="h-3 w-3" /> Commands</span>
                  <span className="animate-pulse">●●●</span>
                </div>
              )}
            </div>
          )}
          <div ref={chatEndRef} />
        </div>
      </div>

      {/* Input */}
      <div className={`shrink-0 ${isWorkspaceMode ? 'border-t border-[#2a2a2a] bg-[#111111]' : 'bg-white'} ${mode === 'standalone' ? 'px-8 sm:px-12 lg:px-24 xl:px-40 pb-8' : 'px-5 pb-5'} pt-2`}>
        <div className="max-w-3xl mx-auto w-full">
          {contextMentions.length > 0 && (
            <div className="mb-2.5 flex flex-wrap gap-1.5">
              {contextMentions.map((item) => (
                <button
                  key={`${item.type}-${item.value}`}
                  type="button"
                  onClick={() => removeMention(item)}
                  className={`rounded-full px-3 py-1.5 text-[11px] font-medium transition ${isWorkspaceMode ? 'border border-white/10 bg-white/5 text-[#cbd5e1] hover:bg-white/10' : 'border border-slate-200 bg-white text-slate-600 shadow-sm hover:bg-slate-50'}`}
                >
                  @{item.value} <X className="inline h-3 w-3 opacity-50 ml-0.5" />
                </button>
              ))}
            </div>
          )}
          <input
            ref={attachmentInputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            multiple
            className="hidden"
            onChange={(event) => { void attachImages(event.target.files); }}
          />
          <div className="mb-2 flex items-center justify-between gap-3">
            <button
              type="button"
              onClick={() => attachmentInputRef.current?.click()}
              className={`inline-flex items-center gap-2 rounded-xl px-3 py-2 text-[11px] font-semibold transition ${isWorkspaceMode ? 'border border-white/10 bg-white/5 text-[#dbe4ee] hover:bg-white/10' : 'border border-slate-200 bg-white text-slate-700 shadow-sm hover:bg-slate-50'}`}
            >
              <ImagePlus className="h-3.5 w-3.5" />
              Attach image
            </button>
            <span className={`text-[10px] font-medium ${isWorkspaceMode ? 'text-[#64748b]' : 'text-slate-400'}`}>
              {chatAttachments.length} / {MAX_CHAT_ATTACHMENTS} images
            </span>
          </div>
          {chatAttachments.length > 0 && (
            <div className="mb-2.5 grid grid-cols-2 gap-2 sm:grid-cols-3">
              {chatAttachments.map((attachment) => (
                <div key={`${attachment.name}-${attachment.data_url.slice(-24)}`} className={`relative overflow-hidden rounded-2xl border ${isWorkspaceMode ? 'border-white/10 bg-white/5' : 'border-slate-200 bg-white shadow-sm'}`}>
                  <img src={attachment.data_url} alt={attachment.name} className="h-24 w-full object-cover" />
                  <button
                    type="button"
                    onClick={() => removeChatAttachment(attachment)}
                    className={`absolute right-2 top-2 inline-flex h-7 w-7 items-center justify-center rounded-full ${isWorkspaceMode ? 'bg-black/70 text-white' : 'bg-white/90 text-slate-700 shadow-sm'}`}
                    aria-label={`Remove ${attachment.name}`}
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                  <div className={`truncate px-2.5 py-2 text-[10px] font-medium ${isWorkspaceMode ? 'text-[#cbd5e1]' : 'text-slate-600'}`} title={attachment.name}>
                    {attachment.name}
                  </div>
                </div>
              ))}
            </div>
          )}
          {attachmentError && (
            <p className={`mb-2 text-[11px] ${isWorkspaceMode ? 'text-amber-300' : 'text-amber-700'}`}>{attachmentError}</p>
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
              placeholder={activePlaceholder}
              className={`min-h-[56px] w-full resize-none rounded-[20px] py-4 pl-4 pr-12 text-[13px] outline-none transition-all placeholder:font-light ${isWorkspaceMode ? 'border border-[#2f2f2f] bg-[#181818] text-white placeholder:text-[#64748b] focus:border-[#3b82f6] focus:bg-[#1b1b1b]' : 'border border-slate-200 bg-[#fbfbfc] text-slate-900 placeholder:text-slate-400 shadow-sm focus:border-slate-300 focus:bg-white focus:shadow-[0_4px_24px_rgba(15,23,42,0.06)]'}`}
              rows={2}
            />
            <button onClick={sendChat} disabled={(!chatInput.trim() && chatAttachments.length === 0) || chatSending} className={`absolute bottom-2 right-2 flex h-10 w-10 items-center justify-center rounded-2xl text-white transition disabled:opacity-30 ${isWorkspaceMode ? 'bg-[#2563eb] shadow-[0_10px_24px_rgba(37,99,235,0.35)] hover:bg-[#1d4ed8]' : 'bg-black shadow-sm hover:bg-slate-800'}`}>
              <Send className="h-4 w-4" />
            </button>
            {mentionQuery !== null && mentionOptions.length > 0 && (
              <div className={`absolute bottom-[calc(100%+8px)] left-0 right-0 max-h-56 overflow-y-auto rounded-2xl p-1.5 ${isWorkspaceMode ? 'border border-[#2f2f2f] bg-[#101010] shadow-[0_18px_40px_rgba(0,0,0,0.45)]' : 'border border-slate-200 bg-white shadow-lg'}`}>
                {mentionOptions.map((item) => (
                  <button
                    key={`${item.type}-${item.value}`}
                    type="button"
                    onClick={() => insertMention(item)}
                    className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-xs ${isWorkspaceMode ? 'text-[#d1d5db] hover:bg-white/5' : 'text-slate-700 hover:bg-slate-50'}`}
                  >
                    <span className="truncate font-medium">{item.label}</span>
                    <span className={`ml-3 shrink-0 text-[10px] capitalize ${isWorkspaceMode ? 'text-[#64748b]' : 'text-slate-400'}`}>{item.type}</span>
                  </button>
                ))}
              </div>
            )}
            {mentionQuery === null && slashSkillQuery !== null && skillOptions.length > 0 && (
              <div className={`absolute bottom-[calc(100%+8px)] left-0 right-0 max-h-56 overflow-y-auto rounded-2xl p-1.5 ${isWorkspaceMode ? 'border border-[#2f2f2f] bg-[#101010] shadow-[0_18px_40px_rgba(0,0,0,0.45)]' : 'border border-slate-200 bg-white shadow-lg'}`}>
                {skillOptions.map((skill) => (
                  <button
                    key={skill.path || skill.slug || skill.name}
                    type="button"
                    onClick={() => insertSkillShortcut(skill)}
                    className={`flex w-full items-start justify-between gap-3 rounded-xl px-3 py-2 text-left text-xs ${isWorkspaceMode ? 'text-[#d1d5db] hover:bg-white/5' : 'text-slate-700 hover:bg-slate-50'}`}
                  >
                    <span className="min-w-0">
                      <span className="block truncate font-medium">{skillCommandLabel(skill)}</span>
                      <span className={`mt-0.5 block truncate text-[10px] ${isWorkspaceMode ? 'text-[#64748b]' : 'text-slate-400'}`}>{skill.description}</span>
                    </span>
                    <span className={`shrink-0 text-[10px] ${isWorkspaceMode ? 'text-[#64748b]' : 'text-slate-400'}`}>skill</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          
          <div className={`mt-3 flex items-center justify-between gap-4 text-[10.5px] font-medium ${isWorkspaceMode ? 'text-[#64748b]' : 'text-slate-400'}`}>
            <div className="flex flex-wrap gap-3">
              {CHAT_SPECIAL_MENTIONS.slice(0, 3).map((item) => (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => insertMention(item)}
                  className={`transition-colors ${isWorkspaceMode ? 'hover:text-[#cbd5e1]' : 'hover:text-slate-600'}`}
                >
                  {item.label}
                </button>
              ))}
              {availableSkills.slice(0, 2).map((skill) => (
                <button
                  key={skill.path || skill.slug || skill.name}
                  type="button"
                  onClick={() => insertSkillShortcut(skill)}
                  className={`transition-colors ${isWorkspaceMode ? 'hover:text-[#cbd5e1]' : 'hover:text-slate-600'}`}
                >
                  {skillCommandLabel(skill)}
                </button>
              ))}
            </div>
            <span className="text-right">{currentModeMeta.label} mode | DevHub AI Assistant</span>
          </div>
        </div>
      </div>
    </div>
  );
}
