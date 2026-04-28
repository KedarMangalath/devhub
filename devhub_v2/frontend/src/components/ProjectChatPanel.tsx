import { useEffect, useRef, useState } from 'react';
import { Bot, ChevronDown, Clock, Code2, ImagePlus, Loader2, MessageSquarePlus, PanelLeftClose, PanelRightClose, RotateCcw, Send, Sparkles, X, Zap } from 'lucide-react';
import AgentStepTimeline from './AgentStepTimeline';
import type { AgentStreamEvent } from './AgentStepTimeline';
import SkillsPanel from './SkillsPanel';
import SkillCreatorWizard from './SkillCreatorWizard';

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

type GlobalSkill = {
  name: string;
  slug: string;
  description: string;
  rel_path?: string;
};

type SlashSkillOption = {
  key: string;
  command: string;
  name: string;
  description: string;
  source: 'meta' | 'project' | 'global';
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

export type ExternalAgentRun = {
  id: string;
  title?: string;
  content: string;
  active: boolean;
  events?: AgentStreamEvent[];
  metadata?: any;
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
  runtimeAgentRun?: ExternalAgentRun | null;
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

const renderInlineMarkdown = (text: string, isWorkspaceMode = false) => {
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
      nodes.push(
        <code
          key={`code-${key++}`}
          className={`rounded px-1.5 py-0.5 font-mono text-[0.95em] ${
            isWorkspaceMode ? 'bg-[#1f1a1d] text-[#d4d4d4]' : 'bg-black/5 text-inherit'
          }`}
        >
          {token.slice(1, -1)}
        </code>
      );
    } else if (token.startsWith('**') && token.endsWith('**')) {
      nodes.push(<strong key={`strong-${key++}`} className="font-semibold text-inherit">{token.slice(2, -2)}</strong>);
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
            className="text-[#8c5462] underline decoration-[#d9a4b2]/60 underline-offset-2 hover:text-[#70434f]"
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

const renderMarkdownMessage = (content: string, isWorkspaceMode = false) => {
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
      <p
        key={`p-${blocks.length}`}
        className={`whitespace-pre-wrap break-words ${isWorkspaceMode ? 'text-[#d4d4d4]' : 'text-inherit'}`}
      >
        {renderInlineMarkdown(paragraph.join(' '), isWorkspaceMode)}
      </p>
    );
    paragraph = [];
  };

  const flushList = () => {
    if (!listItems.length) return;
    blocks.push(
      <ul
        key={`ul-${blocks.length}`}
        className={`list-disc space-y-1 pl-5 ${isWorkspaceMode ? 'text-[#d4d4d4]' : 'text-inherit'}`}
      >
        {listItems.map((item, index) => (
          <li key={`li-${index}`}>{renderInlineMarkdown(item, isWorkspaceMode)}</li>
        ))}
      </ul>
    );
    listItems = [];
  };

  const flushCode = () => {
    if (!codeLines.length && !codeFence) return;
    blocks.push(
      <pre
        key={`pre-${blocks.length}`}
        className={`overflow-x-auto rounded-2xl px-4 py-3 text-[12px] leading-6 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] ${
          isWorkspaceMode
            ? 'border border-white/10 bg-[#0b1220] text-[#dbeafe]'
            : 'bg-[#111827] text-slate-100'
        }`}
      >
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
        ? (isWorkspaceMode ? 'text-xl font-semibold text-white' : 'text-xl font-semibold text-slate-900')
        : level === 2
          ? (isWorkspaceMode ? 'text-lg font-semibold text-white' : 'text-lg font-semibold text-slate-900')
          : (isWorkspaceMode ? 'text-base font-semibold text-white' : 'text-base font-semibold text-slate-900');
      blocks.push(
        <div key={`h-${blocks.length}`} className={className}>
          {renderInlineMarkdown(text, isWorkspaceMode)}
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
  return <div className={`space-y-3 ${isWorkspaceMode ? 'text-[#d4d4d4]' : ''}`}>{blocks}</div>;
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

export default function ProjectChatPanel({ projectId, mode = 'floating', selectedFile, fileContent, treeNodes = [], coderCustomization, onCodeApplied, onAgentAction, onCustomizationChanged, onToggleChat, chatOpen = true, runtimeAgentRun = null }: Props) {
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
  const [agentVisible, setAgentVisible] = useState(true);
  const [agentExpanded, setAgentExpanded] = useState(false);
  const [inputFocused, setInputFocused] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const attachmentInputRef = useRef<HTMLInputElement>(null);
  const wasChatOpenRef = useRef(false);
  const [chatBehaviorMode, setChatBehaviorMode] = useState<ChatBehaviorMode>(() => (mode === 'workspace' ? 'agent' : 'ask'));
  const [streamingState, setStreamingState] = useState<{ events: AgentStreamEvent[]; active: boolean } | null>(null);
  const streamAbortRef = useRef<AbortController | null>(null);

  // Global skills state
  const [showSkillsPanel, setShowSkillsPanel] = useState(false);
  const [showSkillCreator, setShowSkillCreator] = useState(false);
  const [pinnedSkillSlugs, setPinnedSkillSlugs] = useState<string[]>([]);
  const [lastActiveSkills, setLastActiveSkills] = useState<string[]>([]);
  const [globalSkills, setGlobalSkills] = useState<GlobalSkill[]>([]);

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
  const firstSlashCommand = availableSkills.length ? skillCommandLabel(availableSkills[0]) : '/skills';
  const activePlaceholder = (chatBehaviorMode === 'edit' || chatBehaviorMode === 'agent')
    ? `Start with ${firstSlashCommand} to apply a skill, or describe the change directly...`
    : currentModeMeta.placeholder;
  const slashOptionPool: SlashSkillOption[] = [
    {
      key: 'skills-catalog',
      command: '/skills',
      name: 'Skills Catalog',
      description: 'List the global and project skills available in this workspace.',
      source: 'meta',
    },
    ...availableSkills.map((skill) => ({
      key: `project:${skill.path || skill.slug || skill.name}`,
      command: skillCommandLabel(skill),
      name: skill.name,
      description: skill.description,
      source: 'project' as const,
    })),
    ...globalSkills.map((skill) => ({
      key: `global:${skill.slug}`,
      command: `/${skill.slug}`,
      name: skill.name,
      description: skill.description,
      source: 'global' as const,
    })),
  ].filter((item, index, source) => index === source.findIndex((candidate) => candidate.command === item.command));
  const mentionOptions = [...CHAT_SPECIAL_MENTIONS, ...flattenTreeNodes(treeNodes)]
    .filter((item, index, source) => index === source.findIndex((candidate) => candidate.type === item.type && candidate.value === item.value))
    .filter((item) => !mentionQuery || item.label.toLowerCase().includes(`@${mentionQuery.toLowerCase()}`))
    .slice(0, 12);
  const skillOptions = slashOptionPool
    .filter((item) => {
      if (slashSkillQuery === null) return false;
      const query = slashSkillQuery.toLowerCase();
      return item.command.toLowerCase().includes(`/${query}`) || item.name.toLowerCase().includes(query) || item.description.toLowerCase().includes(query);
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
    if ((chatOpen || mode === 'standalone') && runtimeAgentRun) {
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [runtimeAgentRun?.id, runtimeAgentRun?.active, runtimeAgentRun?.events?.length, chatOpen, mode]);

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

  useEffect(() => {
    fetch(`${API}/skills/`)
      .then((response) => response.json())
      .then((data) => setGlobalSkills(Array.isArray(data?.skills) ? data.skills : []))
      .catch(() => setGlobalSkills([]));
  }, []);

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

  const insertSlashCommand = (command: string) => {
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

  const insertSkillShortcut = (skill: CoderCustomizationSkill) => {
    insertSlashCommand(skillCommandLabel(skill));
  };

  const pinnedSkillLabel = (slug: string) => globalSkills.find((skill) => skill.slug === slug)?.name || slug;

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
    if (trace.error) return null;
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

    const traceBorder = isWorkspaceMode ? 'border-[#2a2a2a]' : 'border-slate-100';
    const traceShell = isWorkspaceMode ? 'bg-[#101010] text-[#94a3b8] hover:border-[#3a3a3a]' : 'bg-white text-slate-500 hover:border-slate-200';
    const traceSummaryText = isWorkspaceMode ? 'text-[#94a3b8]' : 'text-slate-400';
    const traceBody = isWorkspaceMode ? 'border-white/5 bg-[#0b0b0c]' : 'border-slate-100 bg-slate-50/50';
    const traceCard = isWorkspaceMode ? 'border-white/8 bg-[#151515] text-[#dbe4ee]' : 'border-white bg-white text-slate-600 shadow-sm';
    const traceSubtle = isWorkspaceMode ? 'text-[#cbd5e1]' : 'text-slate-500';
    const traceCode = isWorkspaceMode ? 'text-[#f3f4f6]' : 'text-slate-700';
    const traceChip = isWorkspaceMode ? 'border-white/10 bg-white/5 text-[#dbe4ee]' : 'border-slate-100 bg-slate-50 text-slate-600';
    const traceCommandCard = isWorkspaceMode ? 'bg-[#0f172a] text-slate-100' : 'bg-slate-800 text-slate-100';
    const traceCommandText = isWorkspaceMode ? 'text-[#c7f9cc]' : 'text-emerald-300';
    const traceCommandDetail = isWorkspaceMode ? 'text-[#94a3b8]' : 'text-slate-400';
    const traceSuccessChip = isWorkspaceMode ? 'bg-emerald-500/15 text-emerald-200' : 'bg-emerald-100 text-emerald-700';
    const traceRunningChip = isWorkspaceMode ? 'bg-amber-500/15 text-amber-200' : 'bg-amber-100 text-amber-700';
    const traceFailedChip = isWorkspaceMode ? 'bg-rose-500/15 text-rose-200' : 'bg-rose-100 text-rose-700';
    const traceAppliedFileChip = isWorkspaceMode ? 'border border-emerald-500/15 bg-emerald-500/10 text-emerald-200' : 'border border-emerald-100 bg-emerald-50 text-emerald-700';
    
    return (
      <>
        {(planObjective || planSteps.length > 0 || planFiles.length > 0 || planCommands.length > 0) && (
          <div className={`mt-3 ml-7 rounded-2xl border px-3.5 py-3 shadow-sm ${isWorkspaceMode ? 'border-[#2a2a2a] bg-[#101010] text-[#dbe4ee]' : 'border-slate-200 bg-white text-slate-700'}`}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className={`text-[10px] font-semibold uppercase tracking-[0.16em] ${isWorkspaceMode ? 'text-[#64748b]' : 'text-slate-400'}`}>Implementation Plan</p>
                {planObjective && <p className={`mt-1 text-[12px] leading-6 ${isWorkspaceMode ? 'text-[#cbd5e1]' : 'text-slate-600'}`}>{planObjective}</p>}
              </div>
              <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${isWorkspaceMode ? 'bg-[#70434f]/25 text-[#d9a4b2]' : 'bg-[#f5ecf0] text-[#70434f]'}`}>
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
                  <code key={command} className={`rounded-lg px-2.5 py-1.5 text-[10px] ${isWorkspaceMode ? 'bg-[#1f1a1d] text-[#c7b08a]' : 'bg-slate-900 text-emerald-300'}`}>{command}</code>
                ))}
              </div>
            )}
          </div>
        )}
        {(reviewSummary || reviewIssues.length > 0 || reviewScore !== null) && (
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
        {/* Agent Step Timeline */}
        {Array.isArray(trace.tool_events) && trace.tool_events.length > 0 && (
          <div className="mt-3 ml-7">
            <AgentStepTimeline
              rawEvents={trace.tool_events}
              durationMs={typeof trace.duration_ms === 'number' ? trace.duration_ms : undefined}
              turnsUsed={typeof trace.turns_used === 'number' ? trace.turns_used : undefined}
              compacted={Boolean(trace.compacted)}
              activeSkills={Array.isArray(trace.active_skills) ? trace.active_skills : undefined}
              isWorkspaceMode={isWorkspaceMode}
            />
          </div>
        )}
        {(trace.approach || contextItems.length > 0 || filesAccessed.length > 0 || commandsRan.length > 0 || semanticHits.length > 0 || workspaceActions.length > 0 || appliedFiles.length > 0) && (
        <details className={`mt-3 ml-7 w-fit min-w-[200px] max-w-full rounded-2xl border text-[11px] transition-colors shadow-sm ${traceBorder} ${traceShell}`}>
        <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-3.5 py-2.5 font-medium tracking-wide">
          <span className={`text-[10px] uppercase tracking-[0.16em] ${traceSummaryText}`}>Trace Logs</span>
          <span className={`truncate text-[10px] ${traceSummaryText}`}>{traceSummary || 'View reasoning'}</span>
        </summary>
        <div className={`space-y-2 rounded-b-2xl border-t px-3 py-3 ${traceBody}`}>
          {trace.approach && (
            <div className={`rounded-xl border px-3 py-2.5 leading-relaxed ${traceCard}`}>
              {trace.approach}
            </div>
          )}
          {contextItems.length > 0 && (
            <details className={`rounded-xl border px-3 py-2.5 shadow-sm ${traceCard}`}>
              <summary className={`cursor-pointer list-none text-[10px] font-semibold uppercase tracking-[0.14em] ${traceSummaryText}`}>
                Context • {contextItems.length}
              </summary>
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                {contextItems.map((item: any, index: number) => (
                  <span key={`${item.type || 'mention'}-${item.value || index}`} className={`rounded-full border px-2.5 py-1 text-[10px] font-medium ${traceChip}`}>
                    @{item.value || item.type || 'context'}
                  </span>
                ))}
              </div>
            </details>
          )}
          {filesAccessed.length > 0 && (
            <details className={`rounded-xl border px-3 py-2.5 shadow-sm ${traceCard}`}>
              <summary className={`cursor-pointer list-none text-[10px] font-semibold uppercase tracking-[0.14em] ${traceSummaryText}`}>
                Files Accessed • {filesAccessed.length}
              </summary>
              <div className="mt-2.5 space-y-1.5">
                {filesAccessed.slice(0, 10).map((item: any, index: number) => (
                  <div key={`${item.path || 'file'}-${index}`} className={`rounded-lg border px-2.5 py-2 ${traceChip}`}>
                    <code className={`block break-all text-[10px] font-medium ${traceCode}`}>{item.path || 'unknown file'}</code>
                    {item.reason && <p className={`mt-1 text-[10px] leading-5 ${traceSubtle}`}>{item.reason}</p>}
                  </div>
                ))}
              </div>
            </details>
          )}
          {commandsRan.length > 0 && (
            <details className={`rounded-xl border px-3 py-2.5 shadow-sm ${traceCard}`}>
              <summary className={`cursor-pointer list-none text-[10px] font-semibold uppercase tracking-[0.14em] ${traceSummaryText}`}>
                Commands Ran • {commandsRan.length}
              </summary>
              <div className="mt-2.5 space-y-1.5">
                {commandsRan.slice(0, 8).map((item: any, index: number) => (
                  <div key={`${item.command || 'command'}-${index}`} className={`rounded-lg px-2.5 py-2 ${traceCommandCard}`}>
                    <code className={`block whitespace-pre-wrap break-words text-[10px] ${traceCommandText}`}>{item.command || 'unknown command'}</code>
                    {item.detail && <p className={`mt-1 text-[10px] leading-5 ${traceCommandDetail}`}>{item.detail}</p>}
                  </div>
                ))}
              </div>
            </details>
          )}
          {workspaceActions.length > 0 && (
            <details className={`rounded-xl border px-3 py-2.5 shadow-sm ${traceCard}`}>
              <summary className={`cursor-pointer list-none text-[10px] font-semibold uppercase tracking-[0.14em] ${traceSummaryText}`}>
                Workspace Actions | {workspaceActions.length}
              </summary>
              <div className="mt-2.5 space-y-1.5">
                {workspaceActions.slice(0, 8).map((item: any, index: number) => (
                  <div key={`${item.type || 'action'}-${index}`} className={`rounded-lg border px-2.5 py-2 ${traceChip}`}>
                    <div className="flex items-center justify-between gap-3">
                      <span className={`text-[10px] font-semibold uppercase tracking-[0.12em] ${traceSubtle}`}>{item.type || 'action'}</span>
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                        item.status === 'failed'
                          ? traceFailedChip
                          : item.status === 'running'
                            ? traceRunningChip
                            : traceSuccessChip
                      }`}>
                        {item.status || 'completed'}
                      </span>
                    </div>
                    {item.command && <code className={`mt-1 block whitespace-pre-wrap break-words text-[10px] font-medium ${traceCode}`}>{item.command}</code>}
                    {item.detail && <p className={`mt-1 text-[10px] leading-5 ${traceSubtle}`}>{item.detail}</p>}
                  </div>
                ))}
              </div>
            </details>
          )}
          {semanticHits.length > 0 && (
            <details className={`rounded-xl border px-3 py-2.5 shadow-sm ${traceCard}`}>
              <summary className={`cursor-pointer list-none text-[10px] font-semibold uppercase tracking-[0.14em] ${traceSummaryText}`}>
                Search Hits • {semanticHits.length}
              </summary>
              <div className="mt-2.5 space-y-1.5">
                {semanticHits.slice(0, 8).map((item: any, index: number) => (
                  <div key={`${item.path || 'hit'}-${index}`} className={`rounded-lg border px-2.5 py-2 ${traceChip}`}>
                    <code className={`block break-all text-[10px] font-medium ${traceCode}`}>{item.path || 'unknown'}</code>
                    {item.symbol && <p className={`mt-1 text-[10px] leading-5 ${traceSubtle}`}>Symbol: {item.symbol}</p>}
                  </div>
                ))}
              </div>
            </details>
          )}
          {appliedFiles.length > 0 && (
            <details className={`rounded-xl border px-3 py-2.5 shadow-sm ${traceCard}`}>
              <summary className={`cursor-pointer list-none text-[10px] font-semibold uppercase tracking-[0.14em] ${traceSummaryText}`}>
                Edits Applied • {appliedFiles.length}
              </summary>
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                {appliedFiles.map((item: string) => (
                  <span key={item} className={`rounded-full px-2.5 py-1 text-[10px] font-medium ${traceAppliedFileChip}`}>{item}</span>
                ))}
              </div>
            </details>
          )}
        </div>
        </details>
        )}
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

  const sendAgentStream = async (content: string, pendingAttachments: ChatImageAttachment[]) => {
    const controller = new AbortController();
    streamAbortRef.current = controller;
    setStreamingState({ events: [], active: true });

    try {
      const response = await fetch(`${API}/projects/${projectId}/chat/agent-stream/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({
          content,
          session_id: activeChatSessionId,
          selected_file: selectedFile,
          selected_content: selectedFile ? fileContent : '',
          context_mentions: contextMentions,
          attachments: pendingAttachments,
          active_skills: pinnedSkillSlugs,
        }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`Agent stream failed: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';
        for (const part of parts) {
          if (!part.startsWith('data: ')) continue;
          let event: AgentStreamEvent;
          try {
            event = JSON.parse(part.slice(6)) as AgentStreamEvent;
          } catch {
            continue;
          }
          if (event.type === 'done') {
            setActiveChatSessionId((event as any).session_id ?? activeChatSessionId ?? null);
            if ((event as any).sessions) setChatSessions((event as any).sessions);
            setChatMessages((current) => [
              ...current,
              {
                role: 'assistant',
                content: (event as any).response ?? '',
                metadata: {
                  ...((event as any).trace ?? {}),
                  hit_turn_limit: (event as any).hit_turn_limit ?? false,
                  partial_summary: (event as any).partial_summary ?? null,
                },
                session_id: (event as any).session_id ?? activeChatSessionId,
              },
            ]);
            if (Array.isArray((event as any).active_skills) && (event as any).active_skills.length > 0) {
              setLastActiveSkills((event as any).active_skills);
            } else {
              setLastActiveSkills([]);
            }
            if ((event as any).applied_changes?.applied_files?.length && onCodeApplied) {
              onCodeApplied((event as any).applied_changes.applied_files);
            }
            if ((event as any).workspace_actions?.length && onAgentAction) {
              onAgentAction((event as any).workspace_actions);
            }
            setStreamingState(null);
          } else if (event.type === 'error') {
            setChatMessages((current) => [
              ...current,
              { role: 'assistant', content: `Agent error: ${(event as any).error}`, metadata: { error: 'agent_stream_error' } },
            ]);
            setStreamingState(null);
          } else if (event.type !== 'keepalive') {
            setStreamingState((prev) =>
              prev ? { ...prev, events: [...prev.events, event] } : { events: [event], active: true }
            );
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setChatMessages((current) => [
          ...current,
          { role: 'assistant', content: 'Stream connection failed.', metadata: { error: 'connection_failed' } },
        ]);
      }
      setStreamingState(null);
    }
  };

  const continuePreviousTask = async (partialSummary: string) => {
    if (chatSending || streamingState?.active) return;
    const continuationMessage = `Continue the task. Context from the previous run: ${partialSummary} Pick up exactly where you left off and complete the remaining work.`;
    setChatMessages((current) => [...current, { role: 'user', content: '▶ Continue', metadata: { chat_mode: 'agent', is_continuation: true }, session_id: activeChatSessionId }]);
    setChatSending(false);
    await sendAgentStream(continuationMessage, []);
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

    if (chatBehaviorMode === 'agent') {
      setChatSending(false);
      await sendAgentStream(content, pendingAttachments);
      return;
    }

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
          active_skills: pinnedSkillSlugs,
        }),
      });
      const data = await response.json();
      if (!response.ok || data?.error) {
        throw new Error(data?.error || 'Unable to send that chat message.');
      }
      setActiveChatSessionId(data.session_id ?? activeChatSessionId ?? null);
      setChatSessions(data.sessions ?? []);
      setChatMessages((current) => [...current, { role: 'assistant', content: data.assistant_message ?? 'No response.', metadata: data.trace ?? {}, session_id: data.session_id ?? activeChatSessionId }]);
      if (Array.isArray(data.active_skills) && data.active_skills.length > 0) {
        setLastActiveSkills(data.active_skills);
      } else {
        setLastActiveSkills([]);
      }

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
    ? 'devhub-chat-panel relative flex h-full w-full flex-col bg-white text-slate-900'
    : mode === 'workspace'
      ? 'devhub-chat-panel relative flex h-full min-h-0 w-full min-w-0 flex-col overflow-hidden bg-[#111111] text-[#e8e8e3]'
      : `devhub-chat-panel relative pointer-events-auto flex flex-col overflow-hidden border border-slate-200/60 bg-white shadow-2xl ${chatExpanded ? 'fixed inset-4 z-50 rounded-3xl' : 'rounded-2xl'}`;

  const wrapperStyles = mode === 'standalone' || mode === 'workspace'
    ? undefined
    : (chatExpanded ? undefined : { width: 440, height: 600, resize: 'both' as const, minWidth: 360, minHeight: 400, maxWidth: '92vw', maxHeight: '80vh' });

  const isWorkspaceMode = mode === 'workspace';

  return (
    <div className={wrapperClasses} style={wrapperStyles}>
      {/* ══ ROW 1: HEADER ═══════════════════════════════════════════════════ */}
      <div className={`flex shrink-0 items-center justify-between gap-2 px-4 py-2.5 ${isWorkspaceMode ? 'border-b border-white/5 bg-[#0d0d0d]' : 'border-b border-slate-100 bg-white'}`}>
        
        {/* Left Side: Only show in floating/standalone mode */}
        <div className="flex flex-1 min-w-0 items-center gap-2">
          {!isWorkspaceMode && (
            <>
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[#f2efea] border border-[#e8e4de]">
                <Code2 className="h-4 w-4 text-[#8c5462]" />
              </div>
              <div className="min-w-0">
                <div className="truncate text-[12.5px] font-semibold leading-tight text-[#191714]">
                  DevHub Coding Agent
                </div>
                <div className="mt-0.5 truncate font-mono text-[9.5px] text-[#c4bfb8]">
                  {projectId ? projectId.slice(0, 8) : 'local'}
                </div>
              </div>
            </>
          )}
        </div>

        {/* Right Side: Actions */}
        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            onClick={startNewChat}
            className={`flex items-center gap-1.5 rounded-md px-2 py-1 text-[11.5px] font-medium transition ${isWorkspaceMode ? 'text-slate-400 hover:bg-white/10 hover:text-white' : 'text-[#888] hover:bg-slate-100 hover:text-slate-900'}`}
          >
            <MessageSquarePlus className="h-3 w-3" />
            <span className="hidden sm:inline">New Chat</span>
          </button>

          <div className="relative">
            <button
              type="button"
              onClick={() => setShowSessions(!showSessions)}
              className={`flex items-center gap-1.5 rounded-md px-2 py-1 text-[11.5px] font-medium transition ${isWorkspaceMode ? 'text-slate-400 hover:bg-white/10 hover:text-white' : 'text-[#888] hover:bg-slate-100 hover:text-slate-900'}`}
            >
              <Clock className="h-3 w-3" />
              <span className="hidden sm:inline">History</span>
              <ChevronDown className="h-3 w-3 opacity-70" />
            </button>
            {showSessions && (
              <div className={`absolute right-0 top-full z-10 mt-1.5 w-48 rounded-xl p-1.5 shadow-xl ${isWorkspaceMode ? 'border border-[#2a2a2a] bg-[#101010]' : 'border border-slate-200 bg-white'}`}>
                {chatSessions.length > 0 ? (
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
                ) : (
                  <div className={`px-3 py-4 text-center text-xs ${isWorkspaceMode ? 'text-slate-500' : 'text-slate-400'}`}>
                    No history to show.
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Skills button */}
          <button
            type="button"
            onClick={() => { setShowSkillsPanel((v) => !v); setShowSkillCreator(false); }}
            title="Global Skills"
            className={`flex items-center gap-1.5 rounded-md px-2 py-1 text-[11.5px] font-medium transition ${
              showSkillsPanel
                ? (isWorkspaceMode ? 'bg-[#70434f]/30 text-[#d9a4b2]' : 'bg-[#f5ecf0] text-[#8c5462]')
                : (isWorkspaceMode ? 'text-slate-400 hover:bg-white/10 hover:text-white' : 'text-[#888] hover:bg-slate-100 hover:text-slate-900')
            }`}
          >
            <Zap className="h-3 w-3" />
            <span className="hidden sm:inline">Skills</span>
            {pinnedSkillSlugs.length > 0 && (
              <span className={`ml-0.5 rounded-full px-1.5 py-0.5 text-[9px] font-bold ${isWorkspaceMode ? 'bg-[#d9a4b2]/30 text-[#d9a4b2]' : 'bg-[#d9a4b2]/20 text-[#8c5462]'}`}>
                {pinnedSkillSlugs.length}
              </span>
            )}
          </button>

          <div className={`mx-1.5 h-3.5 w-[1px] ${isWorkspaceMode ? 'bg-white/10' : 'bg-slate-200'}`} />

          {/* Collapse/Close Actions */}
          {mode === 'floating' && (
            <button
              type="button"
              onClick={() => setChatExpanded((c) => !c)}
              className={`flex items-center justify-center rounded-md p-1.5 transition ${isWorkspaceMode ? 'text-slate-400 hover:bg-white/10 hover:text-white' : 'text-slate-400 hover:bg-slate-100 hover:text-slate-900'}`}
              title={chatExpanded ? 'Minimize' : 'Expand'}
            >
              {chatExpanded ? <PanelLeftClose className="h-4 w-4" /> : <PanelRightClose className="h-4 w-4" />}
            </button>
          )}

          <button
            type="button"
            onClick={() => onToggleChat?.(false)}
            className={`flex items-center justify-center rounded-md p-1.5 transition ${isWorkspaceMode ? 'text-slate-400 hover:bg-white/10 hover:text-white' : 'text-slate-400 hover:bg-slate-100 hover:text-slate-900'}`}
            title="Close Panel"
          >
            <PanelRightClose className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className={`flex-1 min-w-0 min-h-0 overflow-x-hidden overflow-y-auto ${isWorkspaceMode ? 'bg-[#111111]' : 'bg-white'} ${mode === 'standalone' ? 'px-8 sm:px-12 lg:px-24 xl:px-40' : 'px-4'} py-4`}>
        <div className={`w-full ${isWorkspaceMode ? 'space-y-4' : 'mx-auto max-w-3xl space-y-6'}`}>
          {!isWorkspaceMode && (
          <>
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
                    Start a request with a slash skill like {slashCommands[0] || '/skills'} to apply project-specific instructions before planning and coding.
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
          </>
          )}

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
                  ? 'ml-auto max-w-[90%] rounded-[18px] border border-white/10 bg-[#1f1f1f] px-4 py-3 text-[13px] leading-relaxed text-white shadow-[0_12px_30px_rgba(0,0,0,0.28)]'
                  : 'ml-auto max-w-[85%] rounded-[20px] border border-slate-200/50 bg-[#f4f4f5] px-5 py-3.5 text-[13px] leading-relaxed text-slate-900 shadow-sm')
              : (isWorkspaceMode ? 'w-full rounded-[18px] border border-[#70434f] bg-[#181818] px-4 py-3 text-[13px] leading-7 text-[#e8e4e6] shadow-[0_14px_34px_rgba(0,0,0,0.32)]' : 'pr-4 w-full text-[14px] leading-relaxed text-slate-800')
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
                <div className={`${message.role === 'assistant' ? (isWorkspaceMode ? 'pl-7 text-[#d8d8d2]' : 'pl-7') : 'whitespace-pre-wrap break-words'}`}>
                  {message.role === 'assistant' ? renderMarkdownMessage(message.content, isWorkspaceMode) : message.content}
                </div>
              )}
              {message.role === 'assistant' && renderTrace(message.metadata)}
              {message.role === 'assistant' && message.metadata?.hit_turn_limit && index === chatMessages.length - 1 && (
                <div className={`mt-3 pl-7 flex items-start gap-3 ${isWorkspaceMode ? 'text-[#d8d8d2]' : 'text-slate-700'}`}>
                  <div className={`rounded-lg border px-3 py-2 text-[12px] leading-5 ${isWorkspaceMode ? 'border-[#4a4a4a] bg-[#222]' : 'border-slate-200 bg-slate-50'}`}>
                    <p className={`mb-2 font-medium ${isWorkspaceMode ? 'text-[#fbbf24]' : 'text-amber-700'}`}>
                      Turn limit reached — task may be incomplete
                    </p>
                    <p className={`mb-3 text-[11px] ${isWorkspaceMode ? 'text-[#a0a0a0]' : 'text-slate-500'}`}>
                      {message.metadata.partial_summary || 'The agent ran out of turns before finishing. Click Continue to resume from where it stopped.'}
                    </p>
                    <button
                      onClick={() => continuePreviousTask(message.metadata.partial_summary || '')}
                      disabled={chatSending || Boolean(streamingState?.active)}
                      className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[12px] font-semibold transition-all ${
                        isWorkspaceMode
                          ? 'bg-[#1a3a5c] text-[#60a5fa] hover:bg-[#1e4a75] disabled:opacity-40'
                          : 'bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40'
                      }`}
                    >
                      <RotateCcw className="h-3 w-3" />
                      Continue
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
          {runtimeAgentRun && (
            <div
              key={runtimeAgentRun.id}
              className={isWorkspaceMode
                ? 'w-full rounded-[18px] border border-[#70434f] bg-[#181818] px-4 py-3 text-[13px] leading-7 text-[#e8e4e6] shadow-[0_14px_34px_rgba(0,0,0,0.32)]'
                : 'pr-4 w-full text-[14px] leading-relaxed text-slate-800'}
            >
              <div className="mb-2 flex items-center gap-2">
                <div className={`flex h-5 w-5 items-center justify-center rounded ${isWorkspaceMode ? 'bg-[#0f172a]' : 'bg-black'} text-white`}>
                  <Sparkles className="h-3 w-3" />
                </div>
                <span className={`text-xs font-semibold ${isWorkspaceMode ? 'text-white' : 'text-slate-900'}`}>
                  {runtimeAgentRun.title || 'Runtime Recovery'}
                </span>
              </div>
              {runtimeAgentRun.content && (
                <div className={isWorkspaceMode ? 'pl-7 text-[#d4d4d4]' : 'pl-7'}>
                  {renderMarkdownMessage(runtimeAgentRun.content, isWorkspaceMode)}
                </div>
              )}
              {Array.isArray(runtimeAgentRun.events) && runtimeAgentRun.events.length > 0 && (
                <div className="mt-3 pl-7">
                  <AgentStepTimeline
                    liveEvents={runtimeAgentRun.events}
                    isLive={runtimeAgentRun.active}
                    isWorkspaceMode={isWorkspaceMode}
                  />
                </div>
              )}
              {!runtimeAgentRun.active && renderTrace(runtimeAgentRun.metadata)}
            </div>
          )}
          {/* Live streaming agent message */}
          {streamingState && (
            <div className={isWorkspaceMode ? 'w-full rounded-[18px] border border-[#70434f] bg-[#181818] px-4 py-3 text-[13px] leading-7 text-[#e8e4e6] shadow-[0_14px_34px_rgba(0,0,0,0.32)]' : 'pr-4 w-full text-[14px] leading-relaxed text-slate-800'}>
              <div className="mb-2 flex items-center gap-2">
                <div className={`flex h-5 w-5 items-center justify-center rounded ${isWorkspaceMode ? 'bg-[#0f172a]' : 'bg-black'} text-white`}>
                  <Sparkles className="h-3 w-3" />
                </div>
                <span className={`text-xs font-semibold ${isWorkspaceMode ? 'text-white' : 'text-slate-900'}`}>DevHub</span>
              </div>
              <div className="pl-7">
                <AgentStepTimeline
                  liveEvents={streamingState.events}
                  isLive={streamingState.active}
                  isWorkspaceMode={isWorkspaceMode}
                />
              </div>
            </div>
          )}
          {/* Non-agent thinking spinner */}
          {chatSending && (
            <div className={`rounded-2xl border px-4 py-3 ml-7 ${isWorkspaceMode ? 'border-[#2a2a2a] bg-[#101010]' : 'border-slate-200 bg-slate-50/80'}`}>
              <div className="flex items-center gap-2.5">
                <div className={`flex h-6 w-6 items-center justify-center rounded-lg ${isWorkspaceMode ? 'bg-[#2b1d22]' : 'bg-black'}`}>
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-white" />
                </div>
                <span className={`text-[13px] font-medium ${isWorkspaceMode ? 'text-white' : 'text-slate-900'}`}>Thinking...</span>
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>
      </div>

      {/* Input */}
      <div className={`shrink-0 ${isWorkspaceMode ? 'border-t border-white/10 bg-[#0d0d0d]' : 'bg-white'} ${mode === 'standalone' ? 'px-8 sm:px-12 lg:px-24 xl:px-40 pb-8' : 'px-4 pb-4'} pt-3`}>
        <div className={`${isWorkspaceMode ? 'w-full' : 'mx-auto w-full max-w-3xl'}`}>
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
              className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-[11px] font-semibold transition ${isWorkspaceMode ? 'border border-white/10 bg-[#1b1b1b] text-[#dbe4ee] hover:bg-[#242424]' : 'border border-slate-200 bg-white text-slate-700 shadow-sm hover:bg-slate-50'}`}
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
          {/* Active / pinned skill badges */}
          {(pinnedSkillSlugs.length > 0 || lastActiveSkills.length > 0) && (
            <div className="mb-2 flex flex-wrap items-center gap-1.5">
              {pinnedSkillSlugs.map((slug) => (
                <button
                  key={slug}
                  type="button"
                  onClick={() => setPinnedSkillSlugs((prev) => prev.filter((s) => s !== slug))}
                  title="Unpin skill"
                  className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium transition hover:opacity-80 ${isWorkspaceMode ? 'border-[#d9a4b2]/30 bg-[#70434f]/20 text-[#d9a4b2]' : 'border-[#d9a4b2]/40 bg-[#f5ecf0] text-[#8c5462]'}`}
                >
                  <Zap className="h-2.5 w-2.5" />
                  {pinnedSkillLabel(slug)}
                  <X className="h-2.5 w-2.5" />
                </button>
              ))}
              {lastActiveSkills.filter((s) => !pinnedSkillSlugs.includes(s)).map((name) => (
                <span
                  key={name}
                  title="Auto-activated for this message"
                  className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${isWorkspaceMode ? 'border-white/10 bg-white/5 text-[#64748b]' : 'border-slate-200 bg-slate-50 text-slate-400'}`}
                >
                  <Zap className="h-2.5 w-2.5" />
                  {name}
                </span>
              ))}
            </div>
          )}

          {attachmentError && (
            <p className={`mb-2 text-[11px] ${isWorkspaceMode ? 'text-amber-300' : 'text-amber-700'}`}>{attachmentError}</p>
          )}
          <div className={`relative flex min-w-0 flex-col rounded-2xl border transition-all ${inputFocused ? (isWorkspaceMode ? 'border-[#8c5462]/60 bg-[#151515] shadow-[0_0_15px_rgba(140,84,98,0.1)]' : 'border-[#8c5462]/40 bg-white shadow-sm') : (isWorkspaceMode ? 'border-white/10 bg-[#111111]' : 'border-slate-200 bg-slate-50/50')}`}>
            <textarea
              value={chatInput}
              onChange={(event) => setChatInput(event.target.value)}
              onFocus={() => setInputFocused(true)}
              onBlur={() => setInputFocused(false)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  sendChat();
                }
              }}
              placeholder={activePlaceholder}
              className={`min-h-[64px] w-full resize-none bg-transparent px-4 py-3.5 text-[13px] outline-none placeholder:font-light ${isWorkspaceMode ? 'text-[#e8e8e3] placeholder:text-[#6b6b6b]' : 'text-slate-900 placeholder:text-slate-400'}`}
              rows={2}
            />

            <div className="flex flex-wrap items-center gap-2 px-3 pb-3">
              {/* Mentions inside input */}
              <div className="flex flex-wrap gap-1.5 flex-1">
                {CHAT_SPECIAL_MENTIONS.slice(0, 3).map((item) => (
                  <button
                    key={item.value}
                    type="button"
                    onClick={() => insertMention(item)}
                    className={`rounded px-2 py-0.5 text-[10.5px] font-semibold transition-colors ${isWorkspaceMode ? 'bg-white/5 text-[#858585] hover:bg-white/10 hover:text-[#d4d4d4]' : 'bg-slate-100 text-slate-500 hover:bg-slate-200 hover:text-slate-700'}`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>

              {/* Mode dropdown */}
              <div className="relative group">
                <select
                  value={chatBehaviorMode}
                  onChange={(e) => setChatBehaviorMode(e.target.value as ChatBehaviorMode)}
                  className={`appearance-none rounded-lg border px-3 py-1.5 text-[11px] font-bold outline-none transition-colors cursor-pointer pr-6 ${isWorkspaceMode ? 'border-[#8c5462]/40 bg-[#2b1d22] text-[#d9a4b2] hover:bg-[#3a2a30]' : 'border-[#8c5462]/30 bg-rose-50 text-[#8c5462] hover:bg-rose-100 shadow-sm'}`}
                >
                  <option value="ask" className={isWorkspaceMode ? 'bg-[#181818] text-[#d4d4d4]' : 'bg-white text-slate-800'}>Ask Mode</option>
                  <option value="edit" className={isWorkspaceMode ? 'bg-[#181818] text-[#d4d4d4]' : 'bg-white text-slate-800'}>Edit Files</option>
                  <option value="agent" className={isWorkspaceMode ? 'bg-[#181818] text-[#d4d4d4]' : 'bg-white text-slate-800'}>Auto Agent</option>
                </select>
                <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2">
                  <ChevronDown className={`h-3 w-3 ${isWorkspaceMode ? 'text-[#d9a4b2]' : 'text-[#8c5462]'}`} />
                </div>
              </div>

              {/* Send Button */}
              <button
                onClick={sendChat}
                disabled={(!chatInput.trim() && chatAttachments.length === 0) || chatSending}
                className={`flex h-[28px] w-[28px] shrink-0 items-center justify-center rounded-lg transition disabled:opacity-40 ${isWorkspaceMode ? 'bg-[#8c5462] text-white hover:bg-[#70434f]' : (!chatInput.trim() && chatAttachments.length === 0 ? 'bg-slate-200 text-slate-400' : 'bg-[#8c5462] text-white hover:bg-[#70434f] shadow-sm')}`}
              >
                {chatSending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5 ml-0.5" />}
              </button>
            </div>

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
                    key={skill.key}
                    type="button"
                    onClick={() => insertSlashCommand(skill.command)}
                    className={`flex w-full items-start justify-between gap-3 rounded-xl px-3 py-2 text-left text-xs ${isWorkspaceMode ? 'text-[#d1d5db] hover:bg-white/5' : 'text-slate-700 hover:bg-slate-50'}`}
                  >
                    <span className="min-w-0">
                      <span className="block truncate font-medium">{skill.command}</span>
                      <span className={`mt-0.5 block truncate text-[10px] ${isWorkspaceMode ? 'text-[#64748b]' : 'text-slate-400'}`}>{skill.description}</span>
                    </span>
                    <span className={`shrink-0 text-[10px] ${isWorkspaceMode ? 'text-[#64748b]' : 'text-slate-400'}`}>{skill.source}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="mt-2 flex justify-end">
            <span className={`text-[9.5px] font-medium ${isWorkspaceMode ? 'text-[#555]' : 'text-[#d8d3cc]'}`}>
              DevHub AI Assistant
            </span>
          </div>
        </div>
      </div>

      {/* ══ SKILLS PANEL OVERLAY ════════════════════════════════════════════ */}
      {(showSkillsPanel || showSkillCreator) && (
        <div className="absolute inset-0 z-20 p-3">
          {showSkillCreator ? (
            <SkillCreatorWizard
              isWorkspaceMode={isWorkspaceMode}
              onClose={() => { setShowSkillCreator(false); setShowSkillsPanel(true); }}
              onCreated={(slug) => {
                setPinnedSkillSlugs((prev) => prev.includes(slug) ? prev : [...prev, slug]);
                setShowSkillCreator(false);
                setShowSkillsPanel(false);
              }}
            />
          ) : (
            <SkillsPanel
              isWorkspaceMode={isWorkspaceMode}
              pinnedSlugs={pinnedSkillSlugs}
              onPinToggle={(slug) =>
                setPinnedSkillSlugs((prev) =>
                  prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug]
                )
              }
              onCreateClick={() => { setShowSkillCreator(true); setShowSkillsPanel(false); }}
              onClose={() => setShowSkillsPanel(false)}
            />
          )}
        </div>
      )}
    </div>
  );
}
