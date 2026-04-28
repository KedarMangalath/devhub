import { useState } from 'react';
import {
  ChevronRight,
  Clock,
  Edit3,
  FilePlus,
  FileSearch,
  FileText,
  FolderOpen,
  Loader2,
  MessageSquare,
  Search,
  Terminal,
} from 'lucide-react';

// ─── Types ────────────────────────────────────────────────────────────────────

export type AgentStreamEvent =
  | { type: 'thought'; text: string }
  | { type: 'tool_start'; tool: string; summary: { label: string; [key: string]: string } }
  | { type: 'tool_end'; tool: string; success: boolean; preview: string }
  | { type: 'done'; response: string; trace?: any; session_id?: string }
  | { type: 'error'; error: string }
  | { type: 'keepalive' };

// Historical format stored in metadata.tool_events
type RawToolEvent = {
  type: 'tool_start' | 'tool_end';
  tool: string;
  args_preview?: Record<string, string>;
  success?: boolean;
  preview?: string;
};

type Step =
  | { kind: 'thought'; text: string; id: string }
  | { kind: 'tool'; tool: string; label: string; args: Record<string, string>; success?: boolean; preview?: string; active: boolean; id: string };

// ─── Helpers ──────────────────────────────────────────────────────────────────

function toolIcon(tool: string, className = 'h-3.5 w-3.5') {
  switch (tool) {
    case 'file_read':   return <FileText className={className} />;
    case 'file_edit':   return <Edit3 className={className} />;
    case 'file_write':  return <FilePlus className={className} />;
    case 'grep':        return <Search className={className} />;
    case 'glob':        return <FileSearch className={className} />;
    case 'bash':        return <Terminal className={className} />;
    case 'list_dir':    return <FolderOpen className={className} />;
    default:            return <MessageSquare className={className} />;
  }
}

function toolVerb(tool: string): string {
  switch (tool) {
    case 'file_read':  return 'Viewed';
    case 'file_edit':  return 'Edited';
    case 'file_write': return 'Created';
    case 'grep':       return 'Searched';
    case 'glob':       return 'Globbed';
    case 'bash':       return 'Ran';
    case 'list_dir':   return 'Explored';
    default:           return 'Called';
  }
}

function labelFromArgs(tool: string, args: Record<string, string> = {}): string {
  if (args.label) return args.label;
  if (tool === 'file_read' || tool === 'file_edit' || tool === 'file_write' || tool === 'list_dir')
    return args.path || '';
  if (tool === 'grep' || tool === 'glob') return args.pattern || '';
  if (tool === 'bash') return (args.command || '').slice(0, 80);
  return Object.values(args)[0]?.slice(0, 60) || '';
}

/** Convert streaming events into paired steps (thought | tool). */
function streamEventsToSteps(events: AgentStreamEvent[]): Step[] {
  const steps: Step[] = [];
  const activeTools = new Map<string, number>(); // tool → step index

  events.forEach((ev, i) => {
    if (ev.type === 'thought') {
      steps.push({ kind: 'thought', text: ev.text, id: `thought-${i}` });
    } else if (ev.type === 'tool_start') {
      const idx = steps.length;
      activeTools.set(ev.tool + idx, idx);
      steps.push({
        kind: 'tool',
        tool: ev.tool,
        label: ev.summary?.label || ev.tool,
        args: ev.summary || {},
        active: true,
        id: `tool-${i}`,
      });
    } else if (ev.type === 'tool_end') {
      // Find the most recent active step for this tool
      for (let j = steps.length - 1; j >= 0; j--) {
        const s = steps[j];
        if (s.kind === 'tool' && s.tool === ev.tool && s.active) {
          steps[j] = { ...s, active: false, success: ev.success, preview: ev.preview };
          break;
        }
      }
    }
  });

  return steps;
}

/** Convert historical tool_events (from metadata) into steps. */
function rawEventsToSteps(rawEvents: RawToolEvent[]): Step[] {
  const steps: Step[] = [];

  rawEvents.forEach((ev, i) => {
    if (ev.type === 'tool_start') {
      // narrate → thought step (mirrors live streaming path)
      if (ev.tool === 'narrate') {
        const text = ev.args_preview?.thought || Object.values(ev.args_preview || {})[0] || '';
        steps.push({ kind: 'thought', text, id: `raw-thought-${i}` });
        return;
      }
      steps.push({
        kind: 'tool',
        tool: ev.tool,
        label: labelFromArgs(ev.tool, ev.args_preview),
        args: ev.args_preview || {},
        active: false,
        id: `raw-${i}`,
      });
    } else if (ev.type === 'tool_end') {
      if (ev.tool === 'narrate') return; // already handled as thought
      // Patch the most recent step for this tool that has no success yet
      for (let j = steps.length - 1; j >= 0; j--) {
        const s = steps[j];
        if (s.kind === 'tool' && s.tool === ev.tool && s.success === undefined) {
          steps[j] = { ...s, success: ev.success, preview: ev.preview };
          break;
        }
      }
    }
  });

  return steps.filter((s) => s.kind === 'thought' || (s.kind === 'tool' && s.success !== undefined));
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function ThoughtStep({ step, ws }: { step: Extract<Step, { kind: 'thought' }>; ws: boolean }) {
  return (
    <p className={`px-1 py-0.5 text-[11px] italic leading-5 ${ws ? 'text-[#7a8a9e]' : 'text-slate-400'}`}>
      {step.text}
    </p>
  );
}

function ToolStep({
  step,
  ws,
}: {
  step: Extract<Step, { kind: 'tool' }>;
  ws: boolean;
}) {
  const [open, setOpen] = useState(false);
  const verb = toolVerb(step.tool);
  const label = step.label || step.tool;

  const borderColor = ws ? 'border-white/5' : 'border-slate-100';
  const bgColor = ws ? 'bg-white/5' : 'bg-slate-50';
  const textMain = ws ? 'text-[#dbe4ee]' : 'text-slate-700';
  const textSub = ws ? 'text-[#7a8a9e]' : 'text-slate-400';

  const iconBg = step.active
    ? ws ? 'bg-amber-500/20 text-amber-300' : 'bg-amber-100 text-amber-600'
    : step.success === false
    ? ws ? 'bg-rose-500/20 text-rose-300' : 'bg-rose-100 text-rose-600'
    : ws ? 'bg-white/10 text-[#94a3b8]' : 'bg-slate-200 text-slate-500';

  return (
    <div className={`rounded-lg border ${borderColor} overflow-hidden`}>
      <button
        type="button"
        onClick={() => !step.active && step.preview && setOpen((o) => !o)}
        className={`flex w-full items-center gap-2 px-2.5 py-1.5 text-left transition ${bgColor} ${
          step.preview && !step.active ? 'cursor-pointer hover:opacity-80' : 'cursor-default'
        }`}
      >
        <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-md ${iconBg}`}>
          {step.active ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            toolIcon(step.tool)
          )}
        </span>
        <span className={`text-[11px] font-semibold ${textMain}`}>{verb}</span>
        <code className={`flex-1 truncate text-[10px] font-mono ${textSub}`}>{label}</code>
        {step.preview && !step.active && (
          <ChevronRight
            className={`h-3 w-3 shrink-0 transition-transform ${textSub} ${open ? 'rotate-90' : ''}`}
          />
        )}
      </button>
      {open && step.preview && (
        <div className={`border-t ${borderColor} px-3 py-2`}>
          <pre className={`whitespace-pre-wrap break-words text-[10px] leading-5 ${textSub}`}>
            {step.preview}
          </pre>
        </div>
      )}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

type Props = {
  /** Live streaming events (agent mode, in progress). */
  liveEvents?: AgentStreamEvent[];
  /** Historical events from metadata.tool_events. */
  rawEvents?: RawToolEvent[];
  isLive?: boolean;
  durationMs?: number;
  turnsUsed?: number;
  compacted?: boolean;
  isWorkspaceMode?: boolean;
  /** Names of skills that were active for this run. */
  activeSkills?: string[];
};

export default function AgentStepTimeline({
  liveEvents,
  rawEvents,
  isLive = false,
  durationMs,
  turnsUsed,
  compacted,
  isWorkspaceMode: ws = false,
  activeSkills,
}: Props) {
  const [collapsed, setCollapsed] = useState(false);

  const steps: Step[] = liveEvents
    ? streamEventsToSteps(liveEvents)
    : rawEventsToSteps(rawEvents || []);

  if (steps.length === 0 && !isLive) return null;

  const durationLabel = durationMs
    ? durationMs > 1000
      ? `${(durationMs / 1000).toFixed(1)}s`
      : `${durationMs}ms`
    : null;

  const toolCount = steps.filter((s) => s.kind === 'tool').length;
  const summaryText = [
    turnsUsed ? `${turnsUsed} turns` : null,
    toolCount ? `${toolCount} steps` : null,
    durationLabel ? `${durationLabel}` : null,
    compacted ? 'compacted' : null,
  ]
    .filter(Boolean)
    .join(' · ');

  const border = ws ? 'border-white/10' : 'border-slate-200';
  const bg = ws ? 'bg-[#0f0f0f]' : 'bg-white';
  const textMuted = ws ? 'text-[#64748b]' : 'text-slate-400';
  const textMain = ws ? 'text-[#dbe4ee]' : 'text-slate-700';

  return (
    <div className={`mt-2 rounded-2xl border ${border} ${bg} overflow-hidden`}>
      {/* Header */}
      <button
        type="button"
        onClick={() => setCollapsed((c) => !c)}
        className={`flex w-full items-center justify-between gap-3 px-3.5 py-2.5 text-left transition hover:opacity-80`}
      >
        <div className="flex items-center gap-2">
          {isLive ? (
            <Loader2 className={`h-3.5 w-3.5 animate-spin ${ws ? 'text-amber-300' : 'text-amber-500'}`} />
          ) : (
            <Clock className={`h-3.5 w-3.5 ${textMuted}`} />
          )}
          <span className={`text-[11px] font-semibold ${textMain}`}>
            {isLive ? 'Working…' : `Worked${durationLabel ? ` for ${durationLabel}` : ''}`}
          </span>
          {summaryText && !isLive && (
            <span className={`text-[10px] ${textMuted}`}>{summaryText}</span>
          )}
        </div>
        <ChevronRight
          className={`h-3.5 w-3.5 shrink-0 transition-transform ${textMuted} ${!collapsed ? 'rotate-90' : ''}`}
        />
      </button>

      {/* Steps */}
      {!collapsed && (
        <div className={`space-y-1 border-t ${border} px-3 py-2.5`}>
          {activeSkills && activeSkills.length > 0 && (
            <div className="mb-1.5 flex flex-wrap gap-1">
              {activeSkills.map((name) => (
                <span
                  key={name}
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide ${
                    ws ? 'bg-[#8c5462]/20 text-[#d9a4b2]' : 'bg-violet-50 text-violet-600'
                  }`}
                >
                  ⚡ {name}
                </span>
              ))}
            </div>
          )}
          {steps.length === 0 && isLive && (
            <p className={`text-[11px] ${textMuted}`}>Starting up…</p>
          )}
          {steps.map((step) =>
            step.kind === 'thought' ? (
              <ThoughtStep key={step.id} step={step} ws={ws} />
            ) : (
              <ToolStep key={step.id} step={step} ws={ws} />
            )
          )}
        </div>
      )}
    </div>
  );
}
