import { useState, type ReactNode } from 'react';
import { ArrowRight, BookOpen, CheckCircle2, Circle, Code2, Layers3 } from 'lucide-react';

import MermaidDiagram from './MermaidDiagram';

type SourceType = 'starter' | 'github' | 'folder';

interface Props {
  blueprint: any;
  projectName?: string;
  sourceType?: SourceType | string;
  workItems?: any[];
  runtime?: any;
  workspaceReady?: boolean;
  onboardingSummary?: any;
  onNavigateToTab?: (tab: string) => void;
}

const toArray = (value: any): any[] => (Array.isArray(value) ? value : []);
const toText = (value: any, fallback = 'No data available yet.'): string => {
  if (typeof value === 'string') return value.trim() || fallback;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) {
    const text = value.map((item) => toText(item, '')).filter(Boolean).join(', ');
    return text || fallback;
  }
  if (value && typeof value === 'object') {
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return fallback;
    }
  }
  return fallback;
};

const normalizeSourceType = (value: any): SourceType => {
  const source = String(value || '').toLowerCase();
  if (source === 'github' || source === 'folder') return source;
  return 'starter';
};

function Pill({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full border border-black/5 bg-white px-3 py-1 text-[11px] font-medium text-slate-500 shadow-[0_8px_20px_rgba(15,23,42,0.05)]">
      {children}
    </span>
  );
}

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <section className="min-w-0">
      <div className="px-1 pb-4">
        <h3 className="text-base font-semibold text-slate-900">{title}</h3>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      <div>{children}</div>
    </section>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-black/5 bg-[#fbfcfe] px-4 py-8 text-center text-sm text-slate-400">
      {text}
    </div>
  );
}

function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="shrink-0 rounded-lg bg-slate-200 px-2 py-1 text-[9px] text-slate-600 transition-colors hover:bg-slate-300"
    >
      {copied ? 'Copied' : 'Copy'}
    </button>
  );
}

function SourceChip({
  label,
  active,
}: {
  label: string;
  active?: boolean;
}) {
  return (
    <span
      className={`inline-flex rounded-full px-3 py-1 text-[11px] font-medium ${
        active
          ? 'border border-black/5 bg-black text-white shadow-[0_10px_24px_rgba(15,23,42,0.1)]'
          : 'border border-black/5 bg-[#f8fafc] text-slate-500'
      }`}
    >
      {label}
    </span>
  );
}

export default function OnboardingPanel({
  blueprint,
  projectName = 'Project',
  sourceType,
  workItems,
  runtime,
  workspaceReady,
  onboardingSummary,
  onNavigateToTab,
}: Props) {
  const [done, setDone] = useState<Set<string>>(new Set());

  const resolvedSource = normalizeSourceType(
    sourceType ?? blueprint?.source_type ?? blueprint?._meta?.source_type,
  );
  const isImported = resolvedSource !== 'starter';
  const projectSummary = toText(
    blueprint?.project_summary,
    isImported
      ? `This is an imported codebase. Start with the blueprint, then move into the workspace and work items.`
      : `This is a fresh starter project. Start with the workspace, shape the first feature, and let the blueprint fill in.`,
  );

  const liveWorkItems = toArray(workItems);
  const blueprintWorkItems = toArray(blueprint?.feature_inventory);
  const visibleWorkItems = liveWorkItems.length ? liveWorkItems : blueprintWorkItems;

  const setupSteps = toArray(blueprint?.setup_steps);
  const onboardingChecklist = toArray(blueprint?.onboarding_checklist);
  const checklist = [
    ...setupSteps.map((item: any, index: number) => ({
      id: `setup-${index}`,
      group: 'Setup',
      title: typeof item === 'string' ? item : toText(item.step, `Setup step ${index + 1}`),
      detail: typeof item === 'string' ? '' : toText(item.explanation || item.command, ''),
      command: typeof item === 'string' ? '' : toText(item.command, ''),
      note: typeof item === 'string' ? '' : toText(item.os_note, ''),
    })),
    ...onboardingChecklist.map((item: any, index: number) => ({
      id: `check-${index}`,
      group: toText(item.category, 'Checklist'),
      title: toText(item.task, `Checklist item ${index + 1}`),
      detail: toText(item.why_important || item.instructions, ''),
      command: '',
      note: toText(item.estimated_time, ''),
    })),
  ];

  const completedCount = checklist.filter((item) => done.has(item.id)).length;
  const progress = checklist.length ? Math.round((completedCount / checklist.length) * 100) : 0;

  const steps = isImported
    ? [
        {
          title: 'Read the blueprint first',
          body: 'Use the architecture, repo tree, and codebase tour to understand what already exists before making changes.',
          tab: 'blueprint',
          icon: BookOpen,
        },
        {
          title: 'Review the current work items',
          body: 'Features and pipeline are the same work stream. Check what is already backlog, in development, or ready to review.',
          tab: 'work_items',
          icon: Layers3,
        },
        {
          title: 'Open the workspace',
          body: 'Jump into the editor and preview to make the change against the live codebase.',
          tab: 'code',
          icon: Code2,
        },
      ]
    : [
        {
          title: 'Open the workspace',
          body: 'Start from the runnable starter and shape the first visible feature in code.',
          tab: 'code',
          icon: Code2,
        },
        {
          title: 'Define the first work item',
          body: 'Create a feature so the pipeline and blueprint can track the app as it grows.',
          tab: 'work_items',
          icon: Layers3,
        },
        {
          title: 'Let the blueprint catch up',
          body: 'Regenerate the blueprint after the first meaningful implementation so the wiki stays grounded.',
          tab: 'blueprint',
          icon: BookOpen,
        },
      ];

  const flowLabel = isImported ? 'Imported codebase' : 'Starter project';
  const recommendedTab = isImported ? 'onboarding' : 'code';
  const aiSuggestions = toArray(onboardingSummary?.ai_suggestions);
  const suggestedWorkItems = toArray(onboardingSummary?.suggested_work_items);

  const navigate = (tab: string) => {
    if (onNavigateToTab) onNavigateToTab(tab);
  };

  if (!blueprint || Object.keys(blueprint).length === 0) {
    return (
      <div className="flex min-h-[360px] items-center justify-center rounded-[28px] border border-dashed border-black/5 bg-white/70 text-center shadow-[0_18px_50px_rgba(15,23,42,0.06)]">
        <div className="max-w-lg px-6">
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">Onboarding</p>
          <h3 className="mt-3 text-2xl font-semibold text-slate-900">No blueprint generated yet</h3>
          <p className="mt-3 text-sm leading-7 text-slate-500">
            Generate the blueprint first so this page can explain the project, the work items, and the correct
            starting path.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div className="grid gap-5 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">Onboarding</p>
          <h2 className="mt-2 break-words text-[clamp(1.65rem,3vw,2.6rem)] font-semibold leading-[1.05] text-slate-900">
            {projectName}
          </h2>
          <p className="mt-4 max-w-4xl break-words text-sm leading-7 text-slate-600">{projectSummary}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <SourceChip label={flowLabel} active />
            <SourceChip label={resolvedSource === 'starter' ? 'Build first' : 'Understand first'} />
            <SourceChip label={`${toArray(blueprint?.tech_stack_details).length} technologies`} />
            <SourceChip label={`${visibleWorkItems.length} work items`} />
          </div>
        </div>

        <div className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="rounded-2xl border border-black/5 bg-[#f8fafc] p-4 shadow-[0_16px_32px_rgba(15,23,42,0.06)]">
            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Workspace</p>
            <p className="mt-3 text-sm font-medium text-slate-800">{workspaceReady ? 'Ready' : 'Waiting'}</p>
            <p className="mt-1 text-xs text-slate-500 break-words whitespace-pre-wrap">{toText(runtime?.run_command, 'Open the workspace to keep code, preview, and chat in sync.')}</p>
          </div>
          <div className="rounded-2xl border border-black/5 bg-[#fff7ef] p-4 shadow-[0_16px_32px_rgba(15,23,42,0.06)]">
            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-400">Next tab</p>
            <p className="mt-3 text-sm font-medium text-slate-800 capitalize">{recommendedTab}</p>
            <p className="mt-1 text-xs text-slate-500">
              {isImported
                ? 'Imported projects should start with orientation and blueprint review.'
                : 'New starters should go straight to code and the first feature.'}
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-3">
        {steps.map((step) => {
          const Icon = step.icon;
          return (
            <div
              key={step.title}
              className="rounded-[24px] border border-black/5 bg-white p-5 shadow-[0_18px_48px_rgba(15,23,42,0.06)]"
            >
              <div className="flex items-center gap-2">
                <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-black text-white shadow-[0_12px_24px_rgba(15,23,42,0.14)]">
                  <Icon className="h-4 w-4" />
                </div>
                <h3 className="text-sm font-semibold text-slate-900">{step.title}</h3>
              </div>
              <p className="mt-3 text-sm leading-6 text-slate-600">{step.body}</p>
              <button
                type="button"
                onClick={() => navigate(step.tab)}
                disabled={!onNavigateToTab}
                className="mt-4 inline-flex items-center gap-2 rounded-full border border-black/5 bg-[#f8fafc] px-3 py-2 text-xs font-medium text-slate-600 transition-colors hover:bg-white disabled:cursor-default disabled:opacity-60"
              >
                Open {step.tab === 'code' ? 'Workspace' : step.tab === 'blueprint' ? 'Blueprint' : 'Work Items'}
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>
          );
        })}
      </div>

      <div className="space-y-6">
        <Section title="AI Suggestions" subtitle="Auto-generated next actions based on the current blueprint, source type, and tracked work.">
          {aiSuggestions.length ? (
            <div className="space-y-3">
              {aiSuggestions.map((item: any, index: number) => (
                <div key={`${toText(item, 'suggestion')}-${index}`} className="rounded-[20px] border border-black/5 bg-white px-4 py-3 text-sm leading-6 text-slate-600 whitespace-pre-wrap break-words">
                  {toText(item)}
                </div>
              ))}
            </div>
          ) : (
            <EmptyState text="No AI suggestions available yet." />
          )}
        </Section>

        <Section title="Suggested Work Items" subtitle="Feature ideas inferred from the blueprint and current repository state.">
          {suggestedWorkItems.length ? (
            <div className="space-y-3">
              {suggestedWorkItems.map((item: any, index: number) => (
                <div key={`${item.title || 'suggestion'}-${index}`} className="rounded-[20px] border border-black/5 bg-white p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-slate-900">{toText(item.title, 'Suggested work item')}</span>
                    {item.source && <Pill>{toText(item.source, 'source')}</Pill>}
                    {item.suggested_stage && <Pill>{toText(item.suggested_stage, 'stage')}</Pill>}
                  </div>
                  <p className="mt-2 text-sm leading-6 text-slate-600 whitespace-pre-wrap break-words">{toText(item.reason, 'Suggested from the current blueprint.')}</p>
                  <button
                    type="button"
                    onClick={() => navigate('work_items')}
                    disabled={!onNavigateToTab}
                    className="mt-3 inline-flex items-center gap-2 rounded-full border border-black/5 bg-[#f8fafc] px-3 py-2 text-xs font-medium text-slate-600 transition-colors hover:bg-white disabled:cursor-default disabled:opacity-60"
                  >
                    Open Work Items
                    <ArrowRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState text="No suggested work items available yet." />
          )}
        </Section>
      </div>

      <div className="space-y-6">
        <Section
          title="Blueprint Anchors"
          subtitle="A compact orientation layer that points into the deeper project wiki."
        >
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-[22px] border border-black/5 bg-[#fbfcfe] p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">Architecture</p>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                {toText(blueprint?.architecture_overview, 'Use the architecture section to understand the major parts of the system.')}
              </p>
              {blueprint?.mermaid_architecture && (
                <div className="mt-3">
                  <MermaidDiagram chart={blueprint.mermaid_architecture} id="onboard-arch" />
                </div>
              )}
            </div>

            <div className="rounded-[22px] border border-black/5 bg-[#fbfcfe] p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">Repository Map</p>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                {toText(
                  blueprint?.repository_map?.length
                    ? `The repo map highlights ${blueprint.repository_map.length} major areas and how they connect.`
                    : blueprint?.repo_tree
                      ? 'Use the repository tree to understand the real folder structure.'
                      : 'The repository map will appear after blueprint regeneration.',
                )}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => navigate('blueprint')}
                  disabled={!onNavigateToTab}
                  className="rounded-full bg-black px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-slate-800 disabled:cursor-default disabled:opacity-60"
                >
                  Open Blueprint
                </button>
                <button
                  type="button"
                  onClick={() => navigate('code')}
                  disabled={!onNavigateToTab}
                  className="rounded-full border border-black/5 bg-white px-3 py-2 text-xs font-medium text-slate-600 transition-colors hover:bg-[#f8fafc] disabled:cursor-default disabled:opacity-60"
                >
                  Open Workspace
                </button>
              </div>
            </div>
          </div>

          {toArray(blueprint?.repo_tree).length > 0 || typeof blueprint?.repo_tree === 'string' ? (
            <div className="mt-4 rounded-[22px] border border-black/5 bg-[#0f172a] p-4 text-xs leading-6 text-slate-100">
              <div className="mb-3 flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-slate-400">
                <Code2 className="h-3.5 w-3.5" />
                Repository Tree
              </div>
              <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap break-words">{toText(blueprint.repo_tree, 'No repository tree available yet.')}</pre>
            </div>
          ) : null}

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {toArray(blueprint?.directory_guide).slice(0, 4).map((item: any, index: number) => (
              <div key={`${item.path || 'dir'}-${index}`} className="rounded-[20px] border border-black/5 bg-white p-4">
                <div className="flex items-center gap-2">
                  <Pill>{toText(item.path, './')}</Pill>
                  {item.pattern && <Pill>{toText(item.pattern, 'pattern')}</Pill>}
                </div>
                <p className="mt-3 text-sm leading-6 text-slate-600 whitespace-pre-wrap break-words">{toText(item.purpose, 'No purpose summary available.')}</p>
              </div>
            ))}
          </div>
        </Section>

        <Section
          title="Where To Start"
          subtitle="The first useful actions depend on whether this is a starter or an imported codebase."
        >
          <div className="space-y-3">
            <div className="rounded-[22px] border border-black/5 bg-white p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">Recommended flow</p>
              <div className="mt-3 space-y-3">
                {steps.map((step, index) => {
                  const isDone = done.has(`flow-${index}`);
                  return (
                    <div key={step.title} className="flex items-start gap-3">
                      <button
                        type="button"
                        onClick={() => {
                          setDone((current) => {
                            const next = new Set(current);
                            next.has(`flow-${index}`) ? next.delete(`flow-${index}`) : next.add(`flow-${index}`);
                            return next;
                          });
                        }}
                        className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 transition-colors ${
                          isDone ? 'border-emerald-500 bg-emerald-500 text-white' : 'border-slate-300 hover:border-slate-400'
                        }`}
                      >
                        {isDone ? <CheckCircle2 className="h-3 w-3" /> : <Circle className="h-3 w-3 opacity-0" />}
                      </button>
                      <div className="min-w-0">
                        <p className={`text-sm font-medium ${isDone ? 'text-slate-400 line-through' : 'text-slate-800'}`}>
                          {step.title}
                        </p>
                        <p className="mt-1 text-xs leading-6 text-slate-500">{step.body}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="rounded-[22px] border border-black/5 bg-[#fbfcfe] p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">Connected surfaces</p>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {[ 
                  { label: 'Blueprint', detail: 'Deep project wiki and repo map', tab: 'blueprint' },
                  { label: 'Work Items', detail: 'Features and pipeline in one view', tab: 'work_items' },
                  { label: 'Workspace', detail: 'Editor, preview, and chat', tab: 'code' },
                  { label: 'Overview', detail: 'Project health and next steps', tab: 'overview' },
                ].map((item) => (
                  <button
                    key={item.label}
                    type="button"
                    onClick={() => navigate(item.tab)}
                    disabled={!onNavigateToTab}
                    className="rounded-2xl border border-black/5 bg-white p-3 text-left text-xs transition-colors hover:bg-[#f8fafc] disabled:cursor-default disabled:opacity-60"
                  >
                    <div className="font-medium text-slate-800">{item.label}</div>
                    <div className="mt-1 text-slate-500">{item.detail}</div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </Section>
      </div>

      <div className="space-y-6">
        <Section
          title="Work Items"
          subtitle="This is the bridge between the blueprint and the workspace. It is where the project turns into action."
        >
          {visibleWorkItems.length ? (
            <div className="space-y-3">
              {visibleWorkItems.slice(0, 5).map((item: any, index: number) => (
                <div key={`${item.title || 'item'}-${index}`} className="rounded-[22px] border border-black/5 bg-white p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <h4 className="text-sm font-semibold text-slate-900">{toText(item.title, 'Untitled work item')}</h4>
                    {item.status && <Pill>{toText(item.status, 'unknown').replaceAll('_', ' ')}</Pill>}
                  </div>
                  {item.description && <p className="mt-2 text-sm leading-6 text-slate-600 whitespace-pre-wrap break-words">{toText(item.description)}</p>}
                  {item.implementation_notes && (
                    <p className="mt-2 text-sm leading-6 text-slate-500 whitespace-pre-wrap break-words">{toText(item.implementation_notes)}</p>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <EmptyState text="No work items detected yet. Create a feature to seed the first item here." />
          )}

          {toArray(blueprint?.sdlc_pipeline?.stages).length > 0 && (
            <div className="mt-4 rounded-[22px] border border-black/5 bg-[#fbfcfe] p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">Pipeline Snapshot</p>
              <div className="mt-3 grid gap-2 md:grid-cols-2">
                {toArray(blueprint?.sdlc_pipeline?.stages).slice(0, 4).map((stage: any, index: number) => (
                  <div key={`${stage.name || 'stage'}-${index}`} className="rounded-2xl bg-white p-3 shadow-[0_10px_24px_rgba(15,23,42,0.05)]">
                    <div className="text-xs font-medium text-slate-800">{toText(stage.name, `Stage ${index + 1}`)}</div>
                    <div className="mt-1 text-[11px] leading-5 text-slate-500 whitespace-pre-wrap break-words">{toText(stage.purpose, 'Pipeline stage details available after blueprint generation.')}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Section>

        <Section
          title="Checklist"
          subtitle="Small steps to get from first look to productive work."
        >
          <div className="mb-4 rounded-[22px] border border-black/5 bg-[#f8fafc] p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">Progress</p>
                <p className="mt-1 text-sm font-medium text-slate-800">
                  {completedCount} of {checklist.length || 0} completed
                </p>
              </div>
              <div className="text-sm font-semibold text-slate-700">{progress}%</div>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-200">
              <div className="h-full rounded-full bg-black transition-[width] duration-500" style={{ width: `${progress}%` }} />
            </div>
          </div>

          {checklist.length ? (
            <div className="space-y-3">
              {checklist.map((item) => {
                const checked = done.has(item.id);
                return (
                  <div key={item.id} className="rounded-[20px] border border-black/5 bg-white p-4">
                    <div className="flex items-start gap-3">
                      <button
                        type="button"
                        onClick={() => {
                          setDone((current) => {
                            const next = new Set(current);
                            next.has(item.id) ? next.delete(item.id) : next.add(item.id);
                            return next;
                          });
                        }}
                        className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 transition-colors ${
                          checked ? 'border-emerald-500 bg-emerald-500 text-white' : 'border-slate-300 hover:border-slate-400'
                        }`}
                      >
                        {checked ? <CheckCircle2 className="h-3 w-3" /> : <Circle className="h-3 w-3 opacity-0" />}
                      </button>
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className={`text-sm font-medium ${checked ? 'text-slate-400 line-through' : 'text-slate-800'}`}>
                            {item.title}
                          </p>
                          <Pill>{item.group}</Pill>
                          {item.note && <Pill>{item.note}</Pill>}
                        </div>
                        {item.detail && <p className="mt-2 text-xs leading-6 text-slate-500">{item.detail}</p>}
                        {item.command && (
                          <div className="mt-3 flex items-center gap-2">
                            <pre className="min-w-0 flex-1 overflow-x-auto rounded-2xl bg-[#0f172a] px-3 py-2 text-[11px] leading-6 text-emerald-300">
                              {item.command}
                            </pre>
                            <CopyBtn text={item.command} />
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <EmptyState text="No checklist data available yet. Regenerate the blueprint to populate onboarding tasks." />
          )}
        </Section>
      </div>

      {toArray(blueprint?.gotchas).length > 0 && (
        <Section title="Gotchas" subtitle="The small things that usually trip up new contributors.">
          <div className="grid gap-3 md:grid-cols-2">
            {toArray(blueprint.gotchas).slice(0, 4).map((item: any, index: number) => (
              <div key={`${toText(item, 'gotcha')}-${index}`} className="rounded-[20px] border border-black/5 bg-[#fff8ec] p-4 text-sm leading-6 text-slate-600 whitespace-pre-wrap break-words">
                {toText(item, 'No gotcha details available.')}
              </div>
            ))}
          </div>
        </Section>
      )}

      {toArray(blueprint?.faq).length > 0 && (
        <Section title="FAQ" subtitle="A quick reference for common questions.">
          <div className="space-y-3">
            {toArray(blueprint.faq).slice(0, 4).map((item: any, index: number) => (
              <div key={`${toText(item.question, 'faq')}-${index}`} className="rounded-[20px] border border-black/5 bg-white p-4">
                <p className="text-sm font-medium text-slate-800">{toText(item.question, 'Question not available')}</p>
                <p className="mt-2 text-sm leading-6 text-slate-600 whitespace-pre-wrap break-words">{toText(item.answer, 'No answer available yet.')}</p>
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  );
}
