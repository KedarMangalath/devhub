import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import DocumentationPanel from './DocumentationPanel';
import MermaidDiagram from './MermaidDiagram';

interface Props {
  blueprint: any;
  documentation?: any;
  projectId?: string;
  scrollContainer?: HTMLDivElement | null;
  deepDocsProgress?: { pct: number; section: string; completed: number; total: number } | null;
  onRegenerateSection?: (sectionKey: string) => void;
  onGenerateDocumentation?: () => void;
  documentationGenerating?: boolean;
  regeneratingSection?: string | null;
  blueprintBusy?: boolean;
}

type BlueprintTab = [id: string, label: string, regenerateWithBlueprint: boolean];

const API = 'http://localhost:8000/api';

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

const hasMeaningfulPrerequisites = (value: any): boolean => {
  if (!value || typeof value !== 'object') return false;
  return Boolean(
    toText(value.readme_excerpt, '') ||
    toArray(value.required_tools).length ||
    toArray(value.environment_files).length ||
    toArray(value.commands).length ||
    toArray(value.environment_variables).length ||
    toArray(value.instruction_files).length,
  );
};

function Pill({ children }: { children: ReactNode }) {
  return <span className="inline-flex rounded-full border border-black/5 bg-white px-3 py-1 text-[11px] font-medium text-slate-500 shadow-[0_8px_20px_rgba(15,23,42,0.05)]">{children}</span>;
}

function EmptyState({ text }: { text: string }) {
  return <div className="rounded-2xl border border-dashed border-black/5 bg-[#fbfcfe] px-4 py-8 text-center text-sm text-slate-400">{text}</div>;
}

function Section({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <section className="overflow-hidden rounded-[28px] border border-black/5 bg-[linear-gradient(145deg,rgba(255,255,255,0.98),rgba(248,250,252,0.9))] shadow-[0_22px_60px_rgba(15,23,42,0.08)]">
      <div className="border-b border-black/5 px-5 py-4">
        <h3 className="text-base font-semibold text-slate-900">{title}</h3>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function downloadMarkdown(filename: string, content: string) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function renderRichMarkdown(text: string) {
  const lines = (text || '').split('\n');
  const blocks: ReactNode[] = [];
  let paragraph: string[] = [];
  let listItems: string[] = [];
  let codeLines: string[] = [];
  let inCodeBlock = false;
  let codeLanguage = '';

  const flushParagraph = () => {
    if (!paragraph.length) return;
    blocks.push(
      <p key={`p-${blocks.length}`} className="text-sm leading-7 text-slate-600">
        {paragraph.join(' ')}
      </p>,
    );
    paragraph = [];
  };

  const flushList = () => {
    if (!listItems.length) return;
    blocks.push(
      <ul key={`ul-${blocks.length}`} className="space-y-2 text-sm leading-7 text-slate-600">
        {listItems.map((item, index) => (
          <li key={index} className="flex gap-2">
            <span className="mt-[10px] inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400" />
            <span>{item}</span>
          </li>
        ))}
      </ul>,
    );
    listItems = [];
  };

  const flushCode = () => {
    if (!codeLines.length) return;
    const language = codeLanguage.trim().toLowerCase();
    if (/^mermaid(?:\s|$)/.test(language)) {
      blocks.push(
        <div key={`mermaid-${blocks.length}`} className="overflow-hidden rounded-[22px] border border-black/5 bg-[#fbfcfe] p-3">
          <MermaidDiagram chart={codeLines.join('\n')} id={`design-doc-mermaid-${blocks.length}`} />
        </div>,
      );
      codeLines = [];
      codeLanguage = '';
      return;
    }
    blocks.push(
      <pre key={`code-${blocks.length}`} className="overflow-x-auto whitespace-pre-wrap break-words rounded-[22px] bg-[#0f172a] p-4 text-xs leading-6 text-slate-100">
        {codeLanguage ? `${codeLanguage}\n` : ''}{codeLines.join('\n')}
      </pre>,
    );
    codeLines = [];
    codeLanguage = '';
  };

  lines.forEach((line, index) => {
    const trimmed = line.trim();

    if (trimmed.startsWith('```')) {
      if (inCodeBlock) {
        flushCode();
        inCodeBlock = false;
      } else {
        flushParagraph();
        flushList();
        inCodeBlock = true;
        codeLanguage = trimmed.replace('```', '').trim();
      }
      return;
    }

    if (inCodeBlock) {
      codeLines.push(line);
      if (index === lines.length - 1) flushCode();
      return;
    }

    if (!trimmed) {
      flushParagraph();
      flushList();
      return;
    }

    if (/^#{1,4}\s+/.test(trimmed)) {
      flushParagraph();
      flushList();
      const depth = trimmed.match(/^#+/)?.[0].length || 2;
      const content = trimmed.replace(/^#{1,4}\s+/, '');
      const classes = depth <= 2 ? 'text-xl font-semibold text-slate-900' : 'text-base font-semibold text-slate-800';
      blocks.push(
        <h4 key={`h-${blocks.length}`} className={classes}>
          {content}
        </h4>,
      );
      return;
    }

    if (/^[-*]\s+/.test(trimmed) || /^\d+\.\s+/.test(trimmed)) {
      flushParagraph();
      listItems.push(trimmed.replace(/^([-*]|\d+\.)\s+/, ''));
      return;
    }

    paragraph.push(trimmed);
  });

  flushParagraph();
  flushList();
  flushCode();
  return blocks;
}

export default function BlueprintPanel({
  blueprint,
  documentation,
  projectId,
  scrollContainer,
  deepDocsProgress,
  onRegenerateSection,
  onGenerateDocumentation,
  documentationGenerating,
  regeneratingSection,
  blueprintBusy,
}: Props) {
  const [tab, setTab] = useState('overview');
  const [tabBarVisible, setTabBarVisible] = useState(true);
  const [expandedRepoTree, setExpandedRepoTree] = useState<Record<string, boolean>>({});
  const [selectedRepoPath, setSelectedRepoPath] = useState('');
  const [repoDoc, setRepoDoc] = useState<any>(null);
  const [repoDocLoading, setRepoDocLoading] = useState(false);
  const [repoDocError, setRepoDocError] = useState('');
  const [showFullReadmePreview, setShowFullReadmePreview] = useState(false);
  const lastScrollTopRef = useRef(0);
  const tabs = useMemo<BlueprintTab[]>(
    () => [
      ['design_doc', 'Design Doc', true],
      ['overview', 'Overview', true],
      ['repository', 'Repository', true],
      ['reference', 'Reference', false],
      ['services', 'Services', true],
      ['api', 'API', true],
      ['database', 'Database', true],
      ['workflows', 'Workflows', true],
      ['setup', 'Setup', true],
      ['quality', 'Quality', true],
      ['knowledge', 'Knowledge', true],
    ],
    [],
  );
  const currentTabMeta = tabs.find(([id]) => id === tab);
  const currentTabLabel = currentTabMeta?.[1] || 'Section';
  const currentTabCanRegenerateWithBlueprint = currentTabMeta?.[2] !== false;
  const isCurrentSectionRunning = regeneratingSection === tab;
  const showPrerequisites = hasMeaningfulPrerequisites(repoDoc?.prerequisites);

  useEffect(() => {
    const element = scrollContainer;
    if (!element) return;

    const onScroll = () => {
      const current = element.scrollTop;
      const previous = lastScrollTopRef.current;

      if (current < 24) {
        setTabBarVisible(true);
      } else if (current > previous + 16) {
        setTabBarVisible(false);
      } else if (current < previous - 8) {
        setTabBarVisible(true);
      }

      lastScrollTopRef.current = current;
    };

    element.addEventListener('scroll', onScroll, { passive: true });
    return () => element.removeEventListener('scroll', onScroll);
  }, [scrollContainer]);

  useEffect(() => {
    setTabBarVisible(true);
    lastScrollTopRef.current = scrollContainer?.scrollTop || 0;
  }, [tab, scrollContainer]);

  const fetchRepoDoc = async (path = '') => {
    if (!projectId) return;
    setRepoDocLoading(true);
    setRepoDocError('');
    setSelectedRepoPath(path);
    try {
      const response = await fetch(`${API}/projects/${projectId}/codebase/doc/?path=${encodeURIComponent(path)}`);
      const data = await response.json();
      if (!response.ok) {
        setRepoDoc(null);
        setRepoDocError(data.error || 'Unable to load codebase documentation.');
        return;
      }
      setRepoDoc(data.doc || null);
    } catch {
      setRepoDoc(null);
      setRepoDocError('Unable to load codebase documentation.');
    } finally {
      setRepoDocLoading(false);
    }
  };

  useEffect(() => {
    setExpandedRepoTree({});
    setSelectedRepoPath('');
    setRepoDoc(null);
    setRepoDocError('');
    setShowFullReadmePreview(false);
  }, [projectId, blueprint?._meta?.fingerprint]);

  useEffect(() => {
    if (tab !== 'repository' || !projectId || repoDocLoading || repoDoc) return;
    void fetchRepoDoc('');
  }, [tab, projectId, repoDocLoading, repoDoc]);

  if (!blueprint || !Object.keys(blueprint).length) {
    return (
      <div className="flex min-h-[360px] items-center justify-center rounded-[28px] border border-dashed border-black/5 bg-white/70 text-center shadow-[0_18px_50px_rgba(15,23,42,0.06)]">
        <div className="max-w-lg px-6">
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">Blueprint</p>
          <h3 className="mt-3 text-2xl font-semibold text-slate-900">No blueprint generated yet</h3>
          <p className="mt-3 text-sm leading-7 text-slate-500">Generate the blueprint to create the full project wiki, repository map, file structure visualizer, diagrams, and onboarding guide.</p>
        </div>
      </div>
    );
  }

  const services = toArray(blueprint.services);
  const endpoints = toArray(blueprint.api_endpoints);
  const schema = toArray(blueprint.database_schema);
  const features = toArray(blueprint.feature_inventory);
  const keyComponents = toArray(blueprint.key_components);
  const integrations = toArray(blueprint.integration_points);
  const sequenceFlows = toArray(blueprint.sequence_flows);
  const workflows = toArray(blueprint.common_workflows);
  const setupSteps = toArray(blueprint.setup_steps);
  const envVars = toArray(blueprint.environment_variables);
  const onboarding = toArray(blueprint.onboarding_checklist);
  const security = toArray(blueprint.security_considerations);
  const performance = toArray(blueprint.performance_notes);
  const quality = toArray(blueprint.code_quality_standards);
  const concepts = toArray(blueprint.key_concepts);
  const faq = toArray(blueprint.faq);
  const gotchas = toArray(blueprint.gotchas);
  const overviewHealth = toArray(blueprint.overview_project_health);
  const overviewRisks = toArray(blueprint.overview_current_risks);
  const overviewRuntime = toArray(blueprint.overview_runtime_entrypoints);
  const overviewReadFirst = toArray(blueprint.overview_read_first);
  const overviewRecentChanges = toArray(blueprint.overview_recent_changes);
  const overviewNextSteps = toArray(blueprint.overview_next_steps);
  const designDocumentMarkdown = toText(blueprint.design_document_markdown, 'No design document generated yet.');
  const designDocumentSections = toArray(blueprint.design_document_sections);
  const repoTreeNodes = toArray(blueprint.repo_tree_nodes);
  const readmeExcerpt = toText(blueprint.readme_excerpt, '').trim();
  const rootReadmePath = (() => {
    for (const node of repoTreeNodes) {
      const name = toText(node?.name, '').toLowerCase();
      const path = toText(node?.path, '');
      if (path && (name === 'readme.md' || name === 'readme' || name === 'readme.txt')) {
        return path;
      }
    }
    return '';
  })();
  const repoSidebarReadmeText = showFullReadmePreview ? readmeExcerpt : readmeExcerpt.slice(0, 400).trim();
  const endpointGroups = useMemo(() => {
    const groups = new Map<string, any[]>();
    endpoints.forEach((endpoint) => {
      const group = toText(endpoint?.group, 'Other');
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group)?.push(endpoint);
    });
    return Array.from(groups.entries());
  }, [endpoints]);
  const uniqueEndpointPaths = new Set(endpoints.map((endpoint) => toText(endpoint?.path, '/'))).size;

  const toggleRepoTreePath = (path: string) => {
    setExpandedRepoTree((current) => ({ ...current, [path]: !current[path] }));
  };

  const renderRepoTreeNodes = (nodes: any[], depth = 0): ReactNode => (
    <div className="space-y-1">
      {nodes.map((node: any, index: number) => {
        const children = toArray(node.children);
        const isDirectory = node.type === 'directory';
        const expanded = Boolean(expandedRepoTree[node.path]);
        return (
          <div key={`${node.path || node.name || 'node'}-${index}`}>
            <button
              type="button"
              onClick={() => {
                if (isDirectory) toggleRepoTreePath(node.path);
                void fetchRepoDoc(node.path || '');
              }}
              className={`flex w-full items-center gap-2 rounded-xl px-2 py-1.5 text-left text-xs ${isDirectory ? 'text-slate-700 hover:bg-white/70' : 'text-slate-500'} ${node.truncated ? 'italic text-slate-400' : ''} ${selectedRepoPath === node.path ? 'bg-white text-slate-900 shadow-[0_10px_24px_rgba(15,23,42,0.08)]' : ''}`}
              style={{ paddingLeft: `${8 + depth * 16}px` }}
            >
              {isDirectory ? <span className="text-slate-400">{expanded ? '▾' : '▸'}</span> : <span className="text-slate-300">•</span>}
              <span className="truncate">{toText(node.name, 'unknown')}</span>
              {isDirectory && typeof node.child_count === 'number' && <span className="ml-auto shrink-0 text-[10px] text-slate-400">{node.child_count}</span>}
            </button>
            {isDirectory && expanded && children.length > 0 && renderRepoTreeNodes(children, depth + 1)}
          </div>
        );
      })}
    </div>
  );

  const bulletList = (items: any[]) => (
    <ul className="space-y-1 text-sm text-slate-600">
      {items.map((item, index) => <li key={index}>- {toText(item, 'Unknown')}</li>)}
    </ul>
  );

  const codeList = (items: any[]) => (
    <div className="mt-3 flex flex-wrap gap-2">
      {items.map((item, index) => <code key={index} className="rounded-lg bg-[#f8fafc] px-2 py-1 text-[11px] text-slate-600">{toText(item, 'Unknown')}</code>)}
    </div>
  );

  const detailList = (items: any[], emptyText = 'None documented.') => (
    items.length ? (
      <div className="mt-3 space-y-2">
        {items.map((item, index) => (
          <div key={index} className="rounded-2xl bg-white px-3 py-2 shadow-[0_8px_20px_rgba(15,23,42,0.04)]">
            <div className="flex flex-wrap items-center gap-2">
              <code className="text-[11px] text-slate-700">{toText(item?.name ?? item, 'unknown')}</code>
              {typeof item === 'object' && item?.required && <Pill>required</Pill>}
            </div>
            {typeof item === 'object' && item?.description && (
              <p className="mt-1 text-xs leading-5 text-slate-500">{toText(item.description, '')}</p>
            )}
          </div>
        ))}
      </div>
    ) : <p className="mt-3 text-sm text-slate-400">{emptyText}</p>
  );

  const tonePanelClass = (tone: any) => {
    const value = toText(tone, 'neutral').toLowerCase();
    if (value === 'good') return 'border-emerald-100 bg-emerald-50/60';
    if (value === 'warn') return 'border-amber-100 bg-amber-50/60';
    if (value === 'danger') return 'border-rose-100 bg-rose-50/60';
    return 'border-black/5 bg-[#fbfcfe]';
  };

  const severityPillClass = (severity: any) => {
    const value = toText(severity, 'low').toLowerCase();
    if (value === 'critical' || value === 'high') return 'border-rose-200 bg-rose-50 text-rose-700';
    if (value === 'medium' || value === 'warning') return 'border-amber-200 bg-amber-50 text-amber-700';
    return 'border-slate-200 bg-slate-50 text-slate-600';
  };

  const traceCard = (trace: any) => {
    if (!trace) return null;
    const filesAccessed = toArray(trace.files_accessed);
    const commandsRan = toArray(trace.commands_ran);
    return (
      <div className="rounded-[22px] border border-black/5 bg-[#fbfcfe] p-4">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Inspection Trace</p>
        {trace.approach && <p className="mt-2 text-sm leading-6 text-slate-600">{toText(trace.approach)}</p>}
        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Files Accessed</p>
            {filesAccessed.length ? (
              <div className="mt-2 space-y-2">
                {filesAccessed.slice(0, 18).map((item: any, index: number) => (
                  <div key={`${item.path || 'file'}-${index}`} className="rounded-2xl bg-white p-3 text-xs text-slate-600 shadow-[0_8px_20px_rgba(15,23,42,0.04)]">
                    <code className="break-all text-[11px] text-slate-700">{toText(item.path, 'unknown')}</code>
                    {item.reason && <p className="mt-1 leading-5 text-slate-500">{toText(item.reason)}</p>}
                  </div>
                ))}
              </div>
            ) : <p className="mt-2 text-sm text-slate-400">No file access captured.</p>}
          </div>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Commands Ran</p>
            {commandsRan.length ? (
              <div className="mt-2 space-y-2">
                {commandsRan.slice(0, 12).map((item: any, index: number) => (
                  <div key={`${item.command || 'command'}-${index}`} className="rounded-2xl bg-[#0f172a] p-3 text-xs text-slate-100">
                    <code className="block whitespace-pre-wrap break-words">{toText(item.command, 'unknown command')}</code>
                    {item.detail && <p className="mt-2 text-[11px] leading-5 text-slate-300">{toText(item.detail)}</p>}
                  </div>
                ))}
              </div>
            ) : <p className="mt-2 text-sm text-slate-400">No terminal commands were needed for this inspection.</p>}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-5">
      <div className={`sticky top-0 z-20 -mx-4 sm:-mx-6 px-4 sm:px-6 py-3 bg-[linear-gradient(180deg,rgba(247,249,252,0.96),rgba(247,249,252,0.82))] backdrop-blur-xl transition-transform duration-200 ${tabBarVisible ? 'translate-y-0' : '-translate-y-[130%]'}`}>
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex flex-wrap gap-2">
            {tabs.map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => setTab(id)}
                className={`rounded-full px-4 py-2 text-sm font-medium transition-all ${tab === id ? 'border border-black/5 bg-white text-slate-900 shadow-[0_10px_24px_rgba(15,23,42,0.1)]' : 'text-slate-500 hover:bg-white/70'}`}
              >
                {label}
              </button>
            ))}
          </div>
          {projectId && onRegenerateSection && currentTabCanRegenerateWithBlueprint && (
            <button
              type="button"
              onClick={() => onRegenerateSection(tab)}
              disabled={Boolean(blueprintBusy)}
              className="inline-flex items-center justify-center rounded-full border border-black/5 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-[0_10px_24px_rgba(15,23,42,0.08)] transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isCurrentSectionRunning ? `Regenerating ${currentTabLabel}...` : blueprintBusy ? 'Blueprint busy...' : `Regenerate ${currentTabLabel}`}
            </button>
          )}
        </div>
      </div>

      {deepDocsProgress && (
        <div className="rounded-2xl border border-black/5 bg-gradient-to-r from-blue-50 to-indigo-50 p-4 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-slate-700">Generating: {deepDocsProgress.section}</span>
            <span className="text-xs text-slate-500">{deepDocsProgress.completed}/{deepDocsProgress.total} sections</span>
          </div>
          <div className="w-full bg-slate-200/60 rounded-full h-2 overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-blue-500 to-indigo-500 transition-all duration-700 ease-out"
              style={{ width: `${deepDocsProgress.pct}%` }}
            />
          </div>
        </div>
      )}

      {tab === 'design_doc' && (
        <div className="space-y-5">
          <Section title="Blueprint Design Document" subtitle="A long-form architecture document generated from the current blueprint, repository map, workflow state, and indexed evidence.">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="max-w-3xl text-sm leading-7 text-slate-600">
                This view is rendered as a readable design document in the UI. If you need the raw markdown, you can download it.
              </p>
              <button
                type="button"
                onClick={() => downloadMarkdown(`${String(blueprint.project_summary || 'blueprint').slice(0, 40).replace(/[^a-z0-9]+/gi, '-').replace(/^-+|-+$/g, '') || 'blueprint-design-document'}.md`, designDocumentMarkdown)}
                className="inline-flex items-center rounded-full bg-black px-4 py-2 text-xs font-medium text-white shadow-[0_14px_30px_rgba(15,23,42,0.14)] transition hover:bg-slate-800"
              >
                Download Markdown
              </button>
            </div>
          </Section>

          {designDocumentSections.length ? (
            designDocumentSections.map((section: any, index: number) => (
              <Section
                key={`${section.id || section.title || 'design-section'}-${index}`}
                title={section.title || `Section ${index + 1}`}
              >
                <div className="space-y-4">
                  {renderRichMarkdown(section.markdown || '')}
                </div>
              </Section>
            ))
          ) : (
            <Section title="Blueprint Design Document">
              <div className="space-y-4">
                {renderRichMarkdown(designDocumentMarkdown)}
              </div>
            </Section>
          )}

        </div>
      )}

      {tab === 'overview' && (
        <div className="space-y-5">
          <Section title="Verified Repository Snapshot" subtitle="Root docs, generated interpretation, and evidence-backed coverage from the imported codebase.">
            <div className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
              <div className="space-y-5">
                  <div className="rounded-[24px] border border-black/5 bg-[#fbfcfe] p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">Root Documentation</p>
                    {readmeExcerpt ? (
                      <div className="mt-3 space-y-3">
                        <div className="max-h-[26rem] overflow-y-auto rounded-2xl bg-white/70 p-4">
                          <div className="prose prose-sm prose-slate max-w-none">
                            {renderRichMarkdown(readmeExcerpt)}
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {rootReadmePath && (
                            <button
                              type="button"
                              onClick={() => void fetchRepoDoc(rootReadmePath)}
                              className="inline-flex items-center rounded-full border border-black/5 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:bg-slate-50"
                            >
                              Open Full README
                            </button>
                          )}
                        </div>
                      </div>
                    ) : <p className="mt-3 text-sm text-slate-400">No root README excerpt detected yet.</p>}
                  </div>
                <div><p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">Generated Project Summary</p><p className="mt-3 text-sm leading-7 text-slate-600">{toText(blueprint.project_summary)}</p></div>
                <div><p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">Generated Architecture Interpretation</p><p className="mt-3 text-sm leading-7 text-slate-600">{toText(blueprint.architecture_overview)}</p></div>
                <div><p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">Generated Data Flow Interpretation</p><p className="mt-3 text-sm leading-7 text-slate-600">{toText(blueprint.data_flow)}</p></div>
              </div>
              <div className="space-y-4">
                <div className="rounded-[24px] border border-black/5 bg-[#fbfcfe] p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">Coverage</p>
                  <div className="mt-4 grid grid-cols-2 gap-3">
                    {[['Services', services.length], ['API Endpoints', endpoints.length], ['Entities', schema.length], ['Tracked Features', features.length]].map(([label, value]) => (
                      <div key={String(label)} className="rounded-2xl bg-white p-3 shadow-[0_10px_24px_rgba(15,23,42,0.05)]"><div className="text-2xl font-semibold text-slate-900">{value}</div><div className="text-xs text-slate-500">{label}</div></div>
                    ))}
                  </div>
                </div>
                <div className="rounded-[24px] border border-black/5 bg-[#fdfaf5] p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">Technology Stack</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {toArray(blueprint.tech_stack_details).length
                      ? toArray(blueprint.tech_stack_details).map((item: any, index) => <Pill key={`${toText(item.tech, 'tech')}-${index}`}>{toText(item.tech, 'Unknown tech')}{item.category ? ` / ${toText(item.category, 'unknown category')}` : ''}</Pill>)
                      : <span className="text-sm text-slate-400">No stack details detected yet.</span>}
                  </div>
                </div>
              </div>
            </div>
          </Section>

          <div className="grid gap-5 xl:grid-cols-2">
            <Section title="System Architecture Diagram" subtitle="How the major areas of the system fit together."><MermaidDiagram chart={blueprint.mermaid_architecture || ''} id="blueprint-architecture" /></Section>
            <Section title="Service Dependency Graph" subtitle="Which services, layers, or modules depend on each other."><MermaidDiagram chart={blueprint.mermaid_service_dependencies || ''} id="blueprint-service-deps" /></Section>
          </div>

          <Section title="Project Health" subtitle="Live readiness signals from the imported repo, detected runtime, docs, validation, and tracked work.">
            {overviewHealth.length ? (
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                {overviewHealth.map((item: any, index: number) => (
                  <div key={`${item.label || 'health'}-${index}`} className={`rounded-[22px] border p-4 shadow-[0_10px_24px_rgba(15,23,42,0.04)] ${tonePanelClass(item.tone)}`}>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">{toText(item.label, 'Health')}</p>
                    <p className="mt-3 text-xl font-semibold text-slate-900">{toText(item.value, 'Unknown')}</p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{toText(item.detail, 'No detail captured yet.')}</p>
                  </div>
                ))}
              </div>
            ) : <EmptyState text="No project health signals available yet." />}
          </Section>

          <div className="grid gap-5 xl:grid-cols-2">
            <Section title="Current Risks" subtitle="The highest-signal warnings from security, performance, and operational analysis.">
              {overviewRisks.length ? (
                <div className="space-y-3">
                  {overviewRisks.map((item: any, index: number) => (
                    <div key={`${item.title || 'risk'}-${index}`} className="rounded-[22px] border border-black/5 bg-[#fbfcfe] p-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <h4 className="text-sm font-semibold text-slate-900">{toText(item.title, 'Detected risk')}</h4>
                        <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-medium ${severityPillClass(item.severity)}`}>{toText(item.severity, 'info')}</span>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-slate-600">{toText(item.detail, 'No additional detail captured yet.')}</p>
                    </div>
                  ))}
                </div>
              ) : <EmptyState text="No major risks were surfaced by the current repo scan." />}
            </Section>

            <Section title="Active Runtime / Entry Points" subtitle="Detected runtime commands and the files most likely to control local startup.">
              {overviewRuntime.length ? (
                <div className="space-y-3">
                  {overviewRuntime.map((item: any, index: number) => (
                    <div key={`${item.label || 'runtime'}-${index}`} className="rounded-[22px] border border-black/5 bg-[#fbfcfe] p-4">
                      <p className="text-sm font-semibold text-slate-900">{toText(item.label, 'Entry point')}</p>
                      {item.path && <code className="mt-2 block break-all rounded-lg bg-white px-3 py-2 text-[11px] text-slate-700 shadow-[0_8px_20px_rgba(15,23,42,0.04)]">{toText(item.path, '')}</code>}
                      {item.command && <code className="mt-2 block break-all rounded-lg bg-[#0f172a] px-3 py-2 text-[11px] text-slate-100">{toText(item.command, '')}</code>}
                      {item.detail && <p className="mt-2 text-sm leading-6 text-slate-600">{toText(item.detail, '')}</p>}
                    </div>
                  ))}
                </div>
              ) : <EmptyState text="No runtime or entrypoint signals were detected yet." />}
            </Section>
          </div>

          <div className="grid gap-5 xl:grid-cols-2">
            <Section title="What To Read First" subtitle="The fastest paths into this repo before you start making changes.">
              {overviewReadFirst.length ? (
                <div className="space-y-3">
                  {overviewReadFirst.map((item: any, index: number) => (
                    <div key={`${item.path || 'read'}-${index}`} className="rounded-[22px] border border-black/5 bg-[#fbfcfe] p-4">
                      <p className="text-sm font-semibold text-slate-900">{toText(item.title, 'Read first')}</p>
                      <code className="mt-2 block break-all rounded-lg bg-white px-3 py-2 text-[11px] text-slate-700 shadow-[0_8px_20px_rgba(15,23,42,0.04)]">{toText(item.path, 'unknown')}</code>
                      <p className="mt-2 text-sm leading-6 text-slate-600">{toText(item.reason, 'No reason captured yet.')}</p>
                    </div>
                  ))}
                </div>
              ) : <EmptyState text="No prioritized reading list has been derived yet." />}
            </Section>

            <Section title="Repo-specific Next Steps" subtitle="Practical next actions based on the detected setup flow, docs, and current project state.">
              {overviewNextSteps.length ? (
                <div className="space-y-3">
                  {overviewNextSteps.map((item: any, index: number) => (
                    <div key={`${item.title || 'step'}-${index}`} className="rounded-[22px] border border-black/5 bg-[#fbfcfe] p-4">
                      <div className="flex items-center gap-3">
                        <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-white text-xs font-semibold text-slate-700 shadow-[0_8px_20px_rgba(15,23,42,0.04)]">{index + 1}</span>
                        <h4 className="text-sm font-semibold text-slate-900">{toText(item.title, 'Next step')}</h4>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-slate-600">{toText(item.detail, 'No guidance captured yet.')}</p>
                    </div>
                  ))}
                </div>
              ) : <EmptyState text="No repo-specific next steps have been derived yet." />}
            </Section>
          </div>

          <div className="grid gap-5 xl:grid-cols-2">
            <Section title="Recent Changes" subtitle="Latest recorded project changesets or workflow transitions tied to this project.">
              {overviewRecentChanges.length ? (
                <div className="space-y-3">
                  {overviewRecentChanges.map((item: any, index: number) => (
                    <div key={`${item.title || 'change'}-${index}`} className="rounded-[22px] border border-black/5 bg-[#fbfcfe] p-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <h4 className="text-sm font-semibold text-slate-900">{toText(item.title, 'Recent change')}</h4>
                        {item.status && <Pill>{toText(item.status, 'unknown')}</Pill>}
                        {item.meta && <span className="text-[11px] text-slate-400">{toText(item.meta, '')}</span>}
                      </div>
                      <p className="mt-2 text-sm leading-6 text-slate-600">{toText(item.detail, 'No detail captured yet.')}</p>
                    </div>
                  ))}
                </div>
              ) : <EmptyState text="No recent changes have been recorded yet." />}
            </Section>

            <Section title="Active Work" subtitle="Tracked work items and capabilities visible from the current project state.">
              {features.length ? (
                <div className="space-y-3">
                  {features.slice(0, 6).map((item: any, index) => (
                    <div key={`${item.title || 'feature'}-${index}`} className="rounded-[22px] border border-black/5 bg-[#fbfcfe] p-4 shadow-[0_10px_24px_rgba(15,23,42,0.04)]">
                      <div className="flex flex-wrap items-center gap-2"><h4 className="text-sm font-semibold text-slate-900">{toText(item.title, 'Untitled feature')}</h4>{item.status && <Pill>{toText(item.status, 'unknown')}</Pill>}</div>
                      {item.description && <p className="mt-2 text-sm leading-6 text-slate-600 whitespace-pre-wrap break-words">{toText(item.description)}</p>}
                      {item.implementation_notes && <p className="mt-2 text-sm leading-6 text-slate-500 whitespace-pre-wrap break-words">{toText(item.implementation_notes)}</p>}
                    </div>
                  ))}
                </div>
              ) : <EmptyState text="No active work inventory is available yet." />}
            </Section>
          </div>
        </div>
      )}

      {tab === 'reference' && (
        <div className="space-y-5">
          <div className="rounded-[28px] border border-black/5 bg-[linear-gradient(145deg,rgba(255,255,255,0.98),rgba(248,250,252,0.9))] p-5 shadow-[0_22px_60px_rgba(15,23,42,0.08)]">
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">Blueprint Reference</p>
            <h3 className="mt-2 text-2xl font-semibold text-slate-900">Fingerprint-backed codebase snapshot</h3>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-600">
              This keeps the old Docs workflow inside Blueprint so the exportable codebase reference stays available without a duplicate top-level project page.
            </p>
          </div>
          <DocumentationPanel
            documentation={documentation}
            onGenerate={onGenerateDocumentation || (() => {})}
            generating={Boolean(documentationGenerating)}
          />
        </div>
      )}

      {tab === 'repository' && (
        <div className="space-y-5">
          <div className="flex flex-col xl:flex-row gap-0 overflow-hidden rounded-[24px] border border-black/5 bg-white shadow-sm min-h-[75vh]">
            
            {/* LEFT SIDEBAR */}
            <div className="w-full xl:w-[340px] shrink-0 border-b xl:border-b-0 xl:border-r border-black/5 bg-[#fbfcfe]">
              <div className="p-5 border-b border-black/5">
                <h3 className="text-[12px] font-semibold uppercase tracking-[0.18em] text-slate-800">Repository Explorer</h3>
                <p className="mt-1 text-xs leading-5 text-slate-500">Browse the repo tree and load folder-by-folder or file-by-file documentation on demand.</p>
              </div>
              <div className="p-5 space-y-4">
                <button
                  type="button"
                  onClick={() => void fetchRepoDoc('')}
                  className={`flex w-full items-center justify-between rounded-xl border border-black/5 px-3 py-2 text-left text-sm font-medium ${selectedRepoPath === '' ? 'bg-white text-slate-900 shadow-[0_4px_12px_rgba(15,23,42,0.06)]' : 'bg-transparent text-slate-600 hover:bg-white'}`}
                >
                  <span>codebase</span>
                  <span className="text-[11px] text-slate-400">root</span>
                </button>
                <div className="max-h-[60vh] overflow-y-auto pr-1">
                  {repoTreeNodes.length ? renderRepoTreeNodes(repoTreeNodes) : (
                    blueprint.repo_tree ? <pre className="overflow-auto whitespace-pre-wrap break-words rounded-xl bg-[#0f172a] p-4 text-xs leading-6 text-slate-100">{toText(blueprint.repo_tree, 'No repository tree available yet.')}</pre> : <EmptyState text="No repository tree available yet." />
                  )}
                </div>
                {readmeExcerpt && (
                  <div className="mt-4 rounded-xl border border-black/5 bg-white p-4 shadow-sm">
                    <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">README Context</p>
                    <p className="mt-2 whitespace-pre-wrap break-words text-xs leading-5 text-slate-600">{repoSidebarReadmeText}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {readmeExcerpt.length > 400 && (
                        <button
                          type="button"
                          onClick={() => setShowFullReadmePreview((current) => !current)}
                          className="inline-flex items-center rounded-full border border-black/5 bg-[#fbfcfe] px-3 py-1 text-[11px] font-medium text-slate-600 transition hover:bg-white"
                        >
                          {showFullReadmePreview ? 'Show Less' : 'Show More'}
                        </button>
                      )}
                      {rootReadmePath && (
                        <button
                          type="button"
                          onClick={() => void fetchRepoDoc(rootReadmePath)}
                          className="inline-flex items-center rounded-full border border-black/5 bg-[#fbfcfe] px-3 py-1 text-[11px] font-medium text-slate-600 transition hover:bg-white"
                        >
                          Open Full README
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* RIGHT DETAIL */}
            <div className="flex-1 w-full bg-white p-6 md:p-8">
              {repoDocLoading ? (
                <div className="flex h-full min-h-[400px] items-center justify-center text-sm text-slate-400">Loading documentation...</div>
              ) : repoDocError ? (
                <EmptyState text={repoDocError} />
              ) : repoDoc ? (
                <div className="space-y-6">
                  {/* Header / Breadcrumbs */}
                  <div className="flex flex-wrap items-center gap-2">
                    {toArray(repoDoc.breadcrumbs).map((item: any, index: number) => (
                      <button
                        key={`${item.path || 'root'}-${index}`}
                        type="button"
                        onClick={() => void fetchRepoDoc(toText(item.path, ''))}
                        className="rounded-lg border border-transparent bg-slate-50 px-2.5 py-1 text-[12px] font-medium text-slate-600 hover:border-black/5 hover:bg-white transition-colors"
                      >
                        {toText(item.label, 'codebase')} <span className="text-slate-300 ml-1">/</span>
                      </button>
                    ))}
                  </div>
                  
                  {/* Title Area */}
                  <div className="border-b border-black/5 pb-5">
                    <div className="flex flex-wrap items-center gap-3">
                      <h2 className="text-xl font-semibold text-slate-900 break-all">{toText(repoDoc.name || 'codebase', 'codebase')}</h2>
                      <Pill>{repoDoc.kind === 'directory' ? 'Directory' : 'File'}</Pill>
                    </div>
                    <p className="mt-3 text-[15px] leading-relaxed text-slate-600">{toText(repoDoc.summary, 'Documentation summary unavailable.')}</p>
                    {repoDoc.stats && (
                      <div className="mt-4 flex flex-wrap gap-2">
                        {Object.entries(repoDoc.stats).map(([key, value]) => (
                          <Pill key={key}>{key}: {toText(value, '0')}</Pill>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Detail Grid */}
                  {repoDoc.details && (
                    <div className="grid gap-5 lg:grid-cols-2">
                      <div className="rounded-[20px] bg-[#fbfcfe] border border-black/5 p-5">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">What</p>
                        <p className="mt-2 text-sm leading-6 text-slate-700">{toText(repoDoc.details.what, 'No purpose summary available yet.')}</p>
                      </div>
                      <div className="rounded-[20px] bg-[#fbfcfe] border border-black/5 p-5">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Why</p>
                        <p className="mt-2 text-sm leading-6 text-slate-700">{toText(repoDoc.details.why, 'No rationale available yet.')}</p>
                      </div>
                      <div className="rounded-[20px] bg-[#fbfcfe] border border-black/5 p-5">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">How To Read It</p>
                        <p className="mt-2 text-sm leading-6 text-slate-700">{toText(repoDoc.details.how, 'No reading guidance available yet.')}</p>
                      </div>
                      <div className="rounded-[20px] border border-amber-500/20 bg-amber-50/50 p-5">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-amber-700">Change Guidance</p>
                        <p className="mt-2 text-sm leading-6 text-amber-900/80">{toText(repoDoc.details.change_guidance, 'No change guidance available yet.')}</p>
                      </div>
                    </div>
                  )}

                  {repoDoc.kind === 'directory' && toArray(repoDoc.children).length > 0 && (
                    <div className="border-t border-black/5 pt-6">
                      <h3 className="text-[13px] font-semibold uppercase tracking-[0.16em] text-slate-800 mb-4">Children</h3>
                      <div className="grid gap-3 md:grid-cols-2">
                        {toArray(repoDoc.children).map((item: any, index: number) => (
                          <button
                            key={`${item.path || 'child'}-${index}`}
                            type="button"
                            onClick={() => void fetchRepoDoc(toText(item.path, ''))}
                            className="block w-full rounded-[16px] border border-black/5 bg-[#fbfcfe] p-4 text-left transition hover:bg-white hover:shadow-sm"
                          >
                            <div className="flex flex-wrap items-center gap-2">
                              <Pill>{toText(item.type, 'unknown')}</Pill>
                              <code className="break-all text-[11px] text-slate-700">{toText(item.name || item.path?.split('/').pop(), 'unknown')}</code>
                            </div>
                            <p className="mt-2 text-xs leading-5 text-slate-500">{toText(item.summary, 'No summary available yet.')}</p>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {repoDoc.docs && toArray(repoDoc.docs).length > 0 && (
                    <div className="border-t border-black/5 pt-6">
                      <h3 className="text-[13px] font-semibold uppercase tracking-[0.16em] text-slate-800 mb-4">Related Documentation</h3>
                      <div className="grid gap-4 md:grid-cols-2">
                        {toArray(repoDoc.docs).map((item: any, index: number) => (
                          <div key={`${item.path || 'doc'}-${index}`} className="rounded-[16px] border border-black/5 bg-[#fbfcfe] p-4">
                            <code className="text-[11px] text-slate-700">{toText(item.path, 'doc')}</code>
                            <p className="mt-2 whitespace-pre-wrap break-words text-xs leading-5 text-slate-500">{toText(item.excerpt, '')}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="border-t border-black/5 pt-6">
                    <h3 className="text-[13px] font-semibold uppercase tracking-[0.16em] text-slate-800 mb-4">Rendered Documentation</h3>
                    <div className="prose prose-sm prose-slate max-w-none">
                      {renderRichMarkdown(toText(repoDoc.markdown, 'No rendered documentation available yet.'))}
                    </div>
                  </div>

                  {traceCard(repoDoc.trace)}
                </div>
              ) : (
                <EmptyState text="Select a folder or file from the repository explorer to load detailed documentation." />
              )}
            </div>
          </div>

          {showPrerequisites && (
            <div>
              <Section title="Prerequisites" subtitle="Root docs, setup commands, tools, and environment hints detected from the repo.">
                <div className="space-y-4">
                  {repoDoc.prerequisites.readme_excerpt && (
                    <div className="rounded-[22px] border border-black/5 bg-[#fbfcfe] p-4">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">README Summary</p>
                      <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-slate-600">{toText(repoDoc.prerequisites.readme_excerpt, '')}</p>
                    </div>
                  )}
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="rounded-[22px] border border-black/5 bg-white p-4">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Required Tools</p>
                      {toArray(repoDoc.prerequisites.required_tools).length ? codeList(toArray(repoDoc.prerequisites.required_tools)) : <p className="mt-2 text-sm text-slate-400">No tool prerequisites detected yet.</p>}
                    </div>
                    <div className="rounded-[22px] border border-black/5 bg-white p-4">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Environment Files</p>
                      {toArray(repoDoc.prerequisites.environment_files).length ? codeList(toArray(repoDoc.prerequisites.environment_files)) : <p className="mt-2 text-sm text-slate-400">No env template files detected.</p>}
                    </div>
                  </div>
                  <div className="rounded-[22px] border border-black/5 bg-white p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Setup Commands</p>
                    {toArray(repoDoc.prerequisites.commands).length ? codeList(toArray(repoDoc.prerequisites.commands)) : <p className="mt-2 text-sm text-slate-400">No setup commands detected yet.</p>}
                  </div>
                  <div className="rounded-[22px] border border-black/5 bg-white p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Environment Variables</p>
                    {toArray(repoDoc.prerequisites.environment_variables).length ? codeList(toArray(repoDoc.prerequisites.environment_variables)) : <p className="mt-2 text-sm text-slate-400">No environment variables extracted yet.</p>}
                  </div>
                  {toArray(repoDoc.prerequisites.instruction_files).length > 0 && (
                    <div className="rounded-[22px] border border-black/5 bg-white p-4">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Instruction Files</p>
                      <div className="mt-3 space-y-3">
                        {toArray(repoDoc.prerequisites.instruction_files).map((item: any, index: number) => (
                          <div key={`${item.path || 'instruction'}-${index}`} className="rounded-[18px] bg-[#fbfcfe] p-3">
                            <code className="text-[11px] text-slate-700">{toText(item.path, 'instruction file')}</code>
                            <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-slate-600">{toText(item.content, '')}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </Section>
            </div>
          )}
        </div>
      )}

      {tab === 'services' && (
        <div className="space-y-5">
          <Section title="Services And Major Modules" subtitle="Detailed responsibilities, dependencies, and key files.">
            {services.length ? (
              <div className="space-y-3">
                {services.map((item: any, index) => (
                  <div key={`${item.name || 'service'}-${index}`} className="rounded-[22px] border border-black/5 bg-white p-4">
                    <div className="flex flex-wrap items-center gap-2"><h4 className="text-sm font-semibold text-slate-900">{toText(item.name, 'Unnamed service')}</h4>{item.type && <Pill>{toText(item.type, 'unknown')}</Pill>}{item.tech && <Pill>{toText(item.tech, 'unknown')}</Pill>}{item.port && <Pill>port {toText(item.port, 'unknown')}</Pill>}</div>
                    <p className="mt-3 text-sm leading-6 text-slate-600 whitespace-pre-wrap break-words">{toText(item.description, 'No service description available.')}</p>
                    <div className="mt-4 grid gap-4 lg:grid-cols-2">
                      <div><p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Dependencies</p>{bulletList(toArray(item.dependencies))}</div>
                      <div><p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Key Files</p>{bulletList(toArray(item.key_files))}</div>
                    </div>
                  </div>
                ))}
              </div>
            ) : <EmptyState text="No services detected yet." />}
          </Section>

          <Section title="Key Components" subtitle="Important files, exports, and responsibilities across the codebase.">
            {keyComponents.length ? (
              <div className="space-y-3">
                {keyComponents.map((item: any, index) => (
                  <div key={`${item.file_path || 'component'}-${index}`} className="rounded-[22px] border border-black/5 bg-[#fbfcfe] p-4">
                    <div className="flex flex-wrap items-center gap-2"><code className="rounded-lg bg-white px-2 py-1 text-[11px] text-slate-700">{toText(item.file_path, 'unknown file')}</code>{item.complexity && <Pill>{toText(item.complexity, 'unknown')}</Pill>}</div>
                    <p className="mt-3 text-sm font-medium text-slate-700">{toText(item.name, 'Unnamed component')}</p>
                    <p className="mt-2 text-sm leading-6 text-slate-600 whitespace-pre-wrap break-words">{toText(item.purpose, 'No purpose documented.')}</p>
                    <div className="mt-3 flex flex-wrap gap-2">{item.exports && <Pill>{toText(item.exports, 'unknown')}</Pill>}{item.lines_estimate && <Pill>{toText(item.lines_estimate, 'unknown')}</Pill>}{toArray(item.dependencies).slice(0, 6).map((dep: any, depIndex) => <Pill key={depIndex}>{toText(dep, 'Unknown')}</Pill>)}</div>
                  </div>
                ))}
              </div>
            ) : <EmptyState text="No key components detected yet." />}
          </Section>

          <Section title="Integration Points" subtitle="Internal and external connections, plus likely failure points.">
            {integrations.length ? (
              <div className="space-y-3">
                {integrations.map((item: any, index) => (
                  <div key={`${item.name || 'integration'}-${index}`} className="rounded-[22px] border border-black/5 bg-white p-4">
                    <div className="flex flex-wrap items-center gap-2"><h4 className="text-sm font-semibold text-slate-900">{toText(item.name, 'Unnamed integration')}</h4>{item.type && <Pill>{toText(item.type, 'unknown')}</Pill>}</div>
                    <p className="mt-3 text-sm leading-6 text-slate-600 whitespace-pre-wrap break-words">{toText(item.description, 'No description available.')}</p>
                    {toArray(item.evidence).length > 0 && <div className="mt-3"><p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Evidence</p>{bulletList(toArray(item.evidence))}</div>}
                    {toArray(item.failure_modes).length > 0 && <div className="mt-3"><p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Failure Modes</p>{bulletList(toArray(item.failure_modes))}</div>}
                  </div>
                ))}
              </div>
            ) : <EmptyState text="No integration points documented yet." />}
          </Section>
        </div>
      )}

      {tab === 'api' && (
        <div className="space-y-5">
          <Section title="API Reference" subtitle="Real routed endpoints, grouped by area, with handler and payload notes from the current codebase.">
            {endpoints.length ? (
              <div className="space-y-5">
                <div className="grid gap-3 sm:grid-cols-3">
                  {[
                    ['Operations', endpoints.length],
                    ['Unique Paths', uniqueEndpointPaths],
                    ['Groups', endpointGroups.length],
                  ].map(([label, value]) => (
                    <div key={String(label)} className="rounded-[22px] border border-black/5 bg-[#fbfcfe] p-4 shadow-[0_10px_24px_rgba(15,23,42,0.04)]">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">{label}</p>
                      <p className="mt-2 text-2xl font-semibold text-slate-900">{value}</p>
                    </div>
                  ))}
                </div>

                {endpointGroups.map(([group, items]) => (
                  <div key={group} className="space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <h4 className="text-sm font-semibold text-slate-900">{group}</h4>
                      <Pill>{items.length} operation{items.length === 1 ? '' : 's'}</Pill>
                    </div>

                    {items.map((endpoint: any, index: number) => (
                      <div key={`${endpoint.method || 'method'}-${endpoint.path || index}`} className="rounded-[22px] border border-black/5 bg-white p-4 shadow-[0_10px_24px_rgba(15,23,42,0.04)]">
                        <div className="flex flex-wrap items-center gap-2">
                          <Pill>{toText(endpoint.method, 'UNKNOWN')}</Pill>
                          <code className="rounded-lg bg-[#f8fafc] px-2 py-1 text-[11px] text-slate-700">{toText(endpoint.path, '/')}</code>
                          {endpoint.handler && <Pill>{toText(endpoint.handler, 'handler')}</Pill>}
                          <Pill>{endpoint.auth_required ? 'auth required' : 'no explicit auth'}</Pill>
                        </div>

                        <p className="mt-3 text-sm font-medium leading-6 text-slate-800">{toText(endpoint.summary || endpoint.description, 'No endpoint summary available.')}</p>
                        {endpoint.when_to_use && <p className="mt-2 text-sm leading-6 text-slate-600">{toText(endpoint.when_to_use, '')}</p>}
                        {endpoint.access && <p className="mt-2 text-sm leading-6 text-slate-500">{toText(endpoint.access, '')}</p>}
                        {endpoint.behavior_notes && toArray(endpoint.behavior_notes).length > 0 && (
                          <div className="mt-3">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Behavior Notes</p>
                            {bulletList(toArray(endpoint.behavior_notes))}
                          </div>
                        )}
                        {toArray(endpoint.status_codes).length > 0 && (
                          <div className="mt-3">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Status Codes</p>
                            {codeList(toArray(endpoint.status_codes))}
                          </div>
                        )}

                        <div className="mt-4 grid gap-4 xl:grid-cols-2">
                          <div className="rounded-[20px] border border-black/5 bg-[#fbfcfe] p-4">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Path Params</p>
                            {detailList(toArray(endpoint.path_params), 'No path params.')}
                          </div>
                          <div className="rounded-[20px] border border-black/5 bg-[#fbfcfe] p-4">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Query Params</p>
                            {detailList(toArray(endpoint.query_params), 'No query params.')}
                          </div>
                          <div className="rounded-[20px] border border-black/5 bg-[#fbfcfe] p-4">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Request Fields</p>
                            {detailList(toArray(endpoint.request_fields), 'No JSON body fields detected.')}
                          </div>
                          <div className="rounded-[20px] border border-black/5 bg-[#fbfcfe] p-4">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Response Keys</p>
                            {toArray(endpoint.response_keys).length ? codeList(toArray(endpoint.response_keys)) : <p className="mt-3 text-sm text-slate-400">No response keys documented.</p>}
                          </div>
                        </div>

                        <div className="mt-4 grid gap-4 xl:grid-cols-3">
                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Request Body</p>
                            <pre className="mt-2 overflow-auto whitespace-pre-wrap break-words rounded-2xl bg-[#0f172a] p-3 text-xs leading-6 text-slate-100">{toText(endpoint.request_body, 'No request body documented.')}</pre>
                          </div>
                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Response</p>
                            <pre className="mt-2 overflow-auto whitespace-pre-wrap break-words rounded-2xl bg-[#0f172a] p-3 text-xs leading-6 text-slate-100">{toText(endpoint.response, 'No response documented.')}</pre>
                          </div>
                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Curl Example</p>
                            <pre className="mt-2 overflow-auto whitespace-pre-wrap break-words rounded-2xl bg-[#0f172a] p-3 text-xs leading-6 text-slate-100">{toText(endpoint.curl_example, 'No curl example documented.')}</pre>
                          </div>
                        </div>

                        <div className="mt-4 grid gap-4 xl:grid-cols-2">
                          <div className="rounded-[20px] border border-black/5 bg-[#fbfcfe] p-4">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Common Errors</p>
                            {toArray(endpoint.common_errors).length ? bulletList(toArray(endpoint.common_errors)) : <p className="mt-3 text-sm text-slate-400">No common errors documented.</p>}
                          </div>
                          <div className="rounded-[20px] border border-black/5 bg-[#fbfcfe] p-4">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Source</p>
                            <div className="mt-3 space-y-2 text-sm text-slate-600">
                              <p><span className="font-medium text-slate-800">Route:</span> {toText(endpoint.route_name, 'unknown')}</p>
                              <p><span className="font-medium text-slate-800">View File:</span> <code className="text-[11px] text-slate-700">{toText(endpoint.source?.view_file, 'unknown')}</code></p>
                              <p><span className="font-medium text-slate-800">URL File:</span> <code className="text-[11px] text-slate-700">{toText(endpoint.source?.url_file, 'unknown')}</code></p>
                              {endpoint.source?.line && <p><span className="font-medium text-slate-800">Line:</span> {toText(endpoint.source.line, '')}</p>}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            ) : <EmptyState text="No API endpoints detected yet." />}
          </Section>
        </div>
      )}

      {tab === 'database' && (
        <div className="space-y-5">
          <Section title="Entity Relationship Diagram" subtitle="Relationships detected between entities or schema objects."><MermaidDiagram chart={blueprint.mermaid_erd || ''} id="blueprint-erd" /></Section>
          <Section title="Schema Reference" subtitle="Table or model-level documentation with key fields and relationships.">
            {schema.length ? (
              <div className="space-y-3">
                {schema.map((entity: any, index) => (
                  <div key={`${entity.table || 'entity'}-${index}`} className="rounded-[22px] border border-black/5 bg-white p-4">
                    <div className="flex flex-wrap items-center gap-2"><h4 className="text-sm font-semibold text-slate-900">{toText(entity.table, 'Unnamed entity')}</h4>{toArray(entity.indexes).slice(0, 3).map((item: any, itemIndex) => <Pill key={itemIndex}>{toText(item, 'Unknown')}</Pill>)}</div>
                    <p className="mt-3 text-sm leading-6 text-slate-600 whitespace-pre-wrap break-words">{toText(entity.description, 'No entity description available.')}</p>
                    {toArray(entity.key_fields).length > 0 && <div className="mt-4 overflow-hidden rounded-2xl border border-black/5"><table className="min-w-full divide-y divide-black/5 text-sm"><thead className="bg-[#fbfcfe]"><tr className="text-left text-[11px] uppercase tracking-[0.16em] text-slate-400"><th className="px-3 py-2">Field</th><th className="px-3 py-2">Type</th><th className="px-3 py-2">Constraints</th><th className="px-3 py-2">Description</th></tr></thead><tbody className="divide-y divide-black/5 bg-white text-slate-600">{toArray(entity.key_fields).map((field: any, fieldIndex) => <tr key={fieldIndex}><td className="px-3 py-2 font-medium text-slate-700">{toText(field.name, '-')}</td><td className="px-3 py-2">{toText(field.type, '-')}</td><td className="px-3 py-2 whitespace-pre-wrap break-words">{toText(field.constraints, '-')}</td><td className="px-3 py-2 whitespace-pre-wrap break-words">{toText(field.description, '-')}</td></tr>)}</tbody></table></div>}
                    {entity.relationships && <p className="mt-3 text-sm leading-6 text-slate-500 whitespace-pre-wrap break-words">{toText(entity.relationships)}</p>}
                  </div>
                ))}
              </div>
            ) : <EmptyState text="No database schema data available." />}
          </Section>
        </div>
      )}

      {tab === 'workflows' && (
        <div className="space-y-5">
          <Section title="Sequence Flows" subtitle="Important interaction diagrams for user and system paths.">
            {sequenceFlows.length ? (
              <div className="space-y-4">
                {sequenceFlows.map((flow: any, index) => (
                  <div key={`${flow.title || 'flow'}-${index}`} className="space-y-4 rounded-[24px] border border-black/5 bg-white p-4">
                    <div><h4 className="text-sm font-semibold text-slate-900">{toText(flow.title, 'Untitled flow')}</h4><p className="mt-2 text-sm leading-6 text-slate-600 whitespace-pre-wrap break-words">{toText(flow.description, 'No flow description available.')}</p></div>
                    <MermaidDiagram chart={flow.mermaid_sequence || ''} id={`blueprint-sequence-${index}`} />
                    {toArray(flow.touchpoints).length > 0 && <div className="flex flex-wrap gap-2">{toArray(flow.touchpoints).map((touchpoint: any, touchpointIndex) => <Pill key={touchpointIndex}>{toText(touchpoint, 'Unknown')}</Pill>)}</div>}
                  </div>
                ))}
              </div>
            ) : <EmptyState text="No sequence flow data available yet." />}
          </Section>

          <Section title="Common Workflows" subtitle="Operational or engineering workflows that define day-to-day project usage.">
            {workflows.length ? (
              <div className="space-y-3">
                {workflows.map((workflow: any, index) => (
                  <div key={`${workflow.title || 'workflow'}-${index}`} className="rounded-[22px] border border-black/5 bg-[#fbfcfe] p-4">
                    <h4 className="text-sm font-semibold text-slate-900">{toText(workflow.title, 'Workflow')}</h4>
                    <ol className="mt-3 space-y-2 text-sm text-slate-600">{toArray(workflow.steps).map((step: any, stepIndex) => <li key={stepIndex} className="flex gap-2"><span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white text-[11px] font-semibold text-slate-600 shadow-[0_6px_18px_rgba(15,23,42,0.06)]">{stepIndex + 1}</span><span>{toText(step, 'Unknown step')}</span></li>)}</ol>
                  </div>
                ))}
              </div>
            ) : <EmptyState text="No common workflow notes available yet." />}
          </Section>
        </div>
      )}

      {tab === 'setup' && (
        <div className="space-y-5">
          <Section title="Setup Steps" subtitle="Commands and notes for getting the project running locally.">
            {setupSteps.length ? (
              <div className="space-y-3">
                {setupSteps.map((step: any, index) => (
                  <div key={`${step.step || 'step'}-${index}`} className="rounded-[22px] border border-black/5 bg-white p-4">
                    <div className="flex items-center gap-2"><Pill>Step {index + 1}</Pill><h4 className="text-sm font-semibold text-slate-900">{toText(step.step, 'Setup step')}</h4></div>
                    {step.explanation && <p className="mt-3 text-sm leading-6 text-slate-600 whitespace-pre-wrap break-words">{toText(step.explanation)}</p>}
                    {step.command && <pre className="mt-3 overflow-auto whitespace-pre-wrap break-words rounded-2xl bg-[#0f172a] p-3 text-xs leading-6 text-slate-100">{toText(step.command)}</pre>}
                    {step.os_note && <p className="mt-3 text-sm leading-6 text-slate-500 whitespace-pre-wrap break-words">{toText(step.os_note)}</p>}
                  </div>
                ))}
              </div>
            ) : <EmptyState text="No setup steps documented yet." />}
          </Section>

          <Section title="Environment Variables" subtitle="Configuration and secrets that influence project behavior.">
            {envVars.length ? (
              <div className="space-y-3">
                {envVars.map((env: any, index) => (
                  <div key={`${env.name || 'env'}-${index}`} className="rounded-[22px] border border-black/5 bg-[#fbfcfe] p-4">
                    <div className="flex flex-wrap items-center gap-2"><code className="rounded-lg bg-white px-2 py-1 text-[11px] text-slate-700">{toText(env.name, 'VAR_NAME')}</code><Pill>{env.required ? 'required' : 'optional'}</Pill>{env.category && <Pill>{toText(env.category, 'uncategorized')}</Pill>}</div>
                    <p className="mt-3 text-sm leading-6 text-slate-600 whitespace-pre-wrap break-words">{toText(env.description, 'No description available.')}</p>
                    <div className="mt-3 grid gap-3 md:grid-cols-2"><div className="rounded-2xl bg-white p-3"><p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Default</p><p className="mt-1 text-sm text-slate-600 whitespace-pre-wrap break-words">{toText(env.default, 'None specified')}</p></div><div className="rounded-2xl bg-white p-3"><p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">Example</p><p className="mt-1 text-sm text-slate-600 whitespace-pre-wrap break-words">{toText(env.example, 'No example provided')}</p></div></div>
                  </div>
                ))}
              </div>
            ) : <EmptyState text="No environment variable data available yet." />}
          </Section>

          <Section title="Onboarding Checklist" subtitle="What a new engineer should do first to become productive in this repo.">
            {onboarding.length ? (
              <div className="space-y-3">
                {onboarding.map((item: any, index) => (
                  <div key={`${item.task || 'task'}-${index}`} className="rounded-[22px] border border-black/5 bg-white p-4">
                    <div className="flex flex-wrap items-center gap-2"><Pill>{toText(item.category, 'task')}</Pill>{item.estimated_time && <Pill>{toText(item.estimated_time, 'unknown time')}</Pill>}</div>
                    <h4 className="mt-3 text-sm font-semibold text-slate-900">{toText(item.task, 'Onboarding task')}</h4>
                    <p className="mt-2 text-sm leading-6 text-slate-600 whitespace-pre-wrap break-words">{toText(item.why_important, 'No context provided.')}</p>
                    {item.instructions && <p className="mt-2 text-sm leading-6 text-slate-500 whitespace-pre-wrap break-words">{toText(item.instructions)}</p>}
                  </div>
                ))}
              </div>
            ) : <EmptyState text="No onboarding checklist available yet." />}
          </Section>
        </div>
      )}

      {tab === 'quality' && (
        <div className="space-y-5">
          <div className="grid gap-5 xl:grid-cols-2">
            <Section title="Security Considerations" subtitle="Risks, controls, and areas that need careful review.">{security.length ? <div className="space-y-3">{security.map((item: any, index) => <div key={`${item.area || 'security'}-${index}`} className="rounded-[22px] border border-black/5 bg-white p-4"><div className="flex flex-wrap items-center gap-2"><h4 className="text-sm font-semibold text-slate-900">{toText(item.area, 'Security area')}</h4>{item.severity && <Pill>{toText(item.severity, 'unknown')}</Pill>}</div><p className="mt-3 text-sm leading-6 text-slate-600 whitespace-pre-wrap break-words">{toText(item.description, 'No security description available.')}</p></div>)}</div> : <EmptyState text="No security notes documented yet." />}</Section>
            <Section title="Performance Notes" subtitle="Potential bottlenecks, scale concerns, and optimization context.">{performance.length ? <div className="space-y-3">{performance.map((item: any, index) => <div key={`${item.area || 'performance'}-${index}`} className="rounded-[22px] border border-black/5 bg-white p-4"><div className="flex flex-wrap items-center gap-2"><h4 className="text-sm font-semibold text-slate-900">{toText(item.area, 'Performance area')}</h4>{item.impact && <Pill>{toText(item.impact, 'unknown')}</Pill>}</div><p className="mt-3 text-sm leading-6 text-slate-600 whitespace-pre-wrap break-words">{toText(item.description, 'No performance description available.')}</p></div>)}</div> : <EmptyState text="No performance notes documented yet." />}</Section>
          </div>

          <Section title="Testing Strategy" subtitle="How this project should be validated across unit, integration, and end-to-end layers.">
            <div className="grid gap-4 xl:grid-cols-2">
              {[['Unit', blueprint.testing_strategy?.unit], ['Integration', blueprint.testing_strategy?.integration], ['E2E', blueprint.testing_strategy?.e2e], ['Coverage Target', blueprint.testing_strategy?.coverage_target]].map(([label, value]) => <div key={String(label)} className="rounded-[22px] border border-black/5 bg-[#fbfcfe] p-4"><p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">{label}</p><p className="mt-2 text-sm leading-6 text-slate-600">{toText(value)}</p></div>)}
            </div>
            {blueprint.testing_strategy?.run_command && <pre className="mt-4 overflow-auto rounded-2xl bg-[#0f172a] p-3 text-xs leading-6 text-slate-100">{blueprint.testing_strategy.run_command}</pre>}
          </Section>

          <Section title="Code Quality Standards" subtitle="Linting, typing, formatting, and quality rules that shape contributions.">
            {quality.length ? <div className="space-y-3">{quality.map((item: any, index) => <div key={`${item.tool || 'tool'}-${index}`} className="rounded-[22px] border border-black/5 bg-white p-4"><div className="flex flex-wrap items-center gap-2"><h4 className="text-sm font-semibold text-slate-900">{toText(item.tool, 'Tool')}</h4>{item.config_file && <Pill>{toText(item.config_file, 'unknown')}</Pill>}</div><p className="mt-3 text-sm leading-6 text-slate-600 whitespace-pre-wrap break-words">{toText(item.purpose, 'No purpose documented.')}</p></div>)}</div> : <EmptyState text="No code quality standards documented yet." />}
          </Section>
        </div>
      )}

      {tab === 'knowledge' && (
        <div className="space-y-5">
          <Section title="Key Concepts" subtitle="The mental model a new engineer needs to understand the project quickly.">
            {concepts.length ? (
              <div className="space-y-3">
                {concepts.map((item: any, index) => (
                  <div key={`${item.concept || 'concept'}-${index}`} className="rounded-[22px] border border-black/5 bg-white p-4">
                    <div className="flex flex-wrap items-center gap-2"><h4 className="text-sm font-semibold text-slate-900">{toText(item.concept, 'Concept')}</h4>{item.related_code && <code className="rounded-lg bg-[#f8fafc] px-2 py-1 text-[11px] text-slate-600">{toText(item.related_code)}</code>}</div>
                    <p className="mt-3 text-sm leading-6 text-slate-600 whitespace-pre-wrap break-words">{toText(item.explanation, 'No concept explanation available.')}</p>
                    {item.why_important && <p className="mt-2 text-sm leading-6 text-slate-500 whitespace-pre-wrap break-words">{toText(item.why_important)}</p>}
                    {toArray(item.related_concepts).length > 0 && <div className="mt-3 flex flex-wrap gap-2">{toArray(item.related_concepts).map((related: any, relatedIndex) => <Pill key={relatedIndex}>{toText(related, 'Unknown')}</Pill>)}</div>}
                  </div>
                ))}
              </div>
            ) : <EmptyState text="No key concepts documented yet." />}
          </Section>

          <div className="grid gap-5 xl:grid-cols-2">
            <Section title="FAQ" subtitle="Common project questions a new teammate is likely to ask.">{faq.length ? <div className="space-y-3">{faq.map((item: any, index) => <div key={`${toText(item.question, 'faq')}-${index}`} className="rounded-[22px] border border-black/5 bg-white p-4"><h4 className="text-sm font-semibold text-slate-900">{toText(item.question, 'Question')}</h4><p className="mt-3 text-sm leading-6 text-slate-600 whitespace-pre-wrap break-words">{toText(item.answer, 'No answer available.')}</p></div>)}</div> : <EmptyState text="No FAQ entries available yet." />}</Section>
            <Section title="Gotchas" subtitle="Non-obvious behavior, pitfalls, and sharp edges to watch for.">{gotchas.length ? <div className="space-y-3">{gotchas.map((item: any, index) => <div key={`${toText(item, 'gotcha')}-${index}`} className="rounded-[22px] border border-black/5 bg-[#fff8f4] p-4 text-sm leading-6 text-slate-600 whitespace-pre-wrap break-words">{toText(item, 'No gotcha details available.')}</div>)}</div> : <EmptyState text="No gotchas documented yet." />}</Section>
          </div>
        </div>
      )}
    </div>
  );
}
