import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  FolderOpen,
  Github,
  Loader2,
  Plus,
  Settings2,
  Sparkles,
  Trash2,
  Workflow,
  X,
} from 'lucide-react';

const API = 'http://localhost:8000/api';

type SourceType = 'starter' | 'github' | 'folder';

type Project = {
  id: string;
  name: string;
  description: string;
  status: string;
  tech_stack: string[];
  github_url?: string | null;
  local_path?: string | null;
  source_type?: SourceType;
};

type ProjectForm = {
  idea: string;
  name: string;
  description: string;
  github_url: string;
  local_path: string;
  tech_stack: string[];
};

type ProjectInspection = {
  name: string;
  description: string;
  tech_stack: string[];
  detected_stack?: string[];
  resolved_path?: string;
  root_name?: string;
  github_url?: string;
  structure_preview?: string;
  source_summary?: string;
  runtime?: {
    runtime_type?: string;
    run_command?: string;
    preview_url?: string | null;
  };
};

type FlowStep = {
  title: string;
  detail: string;
  complete: boolean;
};

const SOURCE_OPTIONS: Array<{
  id: SourceType;
  title: string;
  eyebrow: string;
  summary: string;
  detail: string;
}> = [
  {
    id: 'starter',
    title: 'Start Fresh',
    eyebrow: 'Generate a runnable starter app',
    summary:
      'Create a brand new project from an idea, choose a stack, and let DevHub scaffold the first working version.',
    detail:
      'Best for first-time flows with scaffold generation, blueprinting, and guided feature setup.',
  },
  {
    id: 'github',
    title: 'Import GitHub',
    eyebrow: 'Clone an existing repository',
    summary:
      'Bring in a GitHub repo, detect the stack, and let DevHub build blueprint, memory, and implementation context.',
    detail:
      'Best when the code already exists and you want planning, pipeline, and workspace on top of it.',
  },
  {
    id: 'folder',
    title: 'Open Folder',
    eyebrow: 'Connect a local project directory',
    summary:
      'Attach an existing local folder so DevHub can understand it, edit it, and run it from the workspace.',
    detail:
      'Best for local repos, prototypes, and projects that are already on this machine.',
  },
];

const STACK_PRESETS = [
  'React',
  'Next.js',
  'Vue',
  'Django',
  'FastAPI',
  'Node.js',
  'Express',
  'TypeScript',
  'Tailwind',
  'PostgreSQL',
];

const DEFAULT_AI_CONFIG = {
  provider: 'openai',
  model: 'gpt-4o-mini',
  api_key: '',
  base_url: '',
  gemini_mode: 'api_key',
  gemini_cli_command: 'gemini',
  vertex_project: '',
  vertex_location: 'us-central1',
  vertex_access_token: '',
};

const PROVIDER_MODEL_PRESETS: Record<string, string[]> = {
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-5', 'gpt-5-mini'],
  claude: ['claude-3-5-sonnet-latest', 'claude-3-5-haiku-latest'],
  gemini: ['gemini-2.5-pro', 'gemini-2.5-flash'],
  openrouter: ['openai/gpt-4o-mini', 'anthropic/claude-3.5-sonnet', 'google/gemini-2.5-pro'],
};

function defaultModelFor(provider: string, geminiMode: string) {
  if (provider === 'claude') return 'claude-3-5-sonnet-latest';
  if (provider === 'gemini') return geminiMode === 'vertexai' ? 'gemini-2.5-pro' : 'gemini-2.5-pro';
  if (provider === 'openrouter') return 'openai/gpt-4o-mini';
  return 'gpt-4o-mini';
}

function mergeAiConfig(config?: any) {
  const merged = { ...DEFAULT_AI_CONFIG, ...(config || {}) };
  if (!merged.model) {
    merged.model = defaultModelFor(merged.provider, merged.gemini_mode);
  }
  if (merged.provider === 'openrouter' && !merged.base_url) {
    merged.base_url = 'https://openrouter.ai/api/v1';
  }
  return merged;
}

const DEFAULT_FORM: ProjectForm = {
  idea: '',
  name: '',
  description: '',
  github_url: '',
  local_path: '',
  tech_stack: [],
};

function getSourceLabel(sourceType: SourceType) {
  return SOURCE_OPTIONS.find((option) => option.id === sourceType)?.title ?? 'Start Fresh';
}

function getProjectLocation(project: Project) {
  if (project.github_url) return project.github_url;
  if (project.local_path) return project.local_path;
  return 'Managed DevHub workspace';
}

function normalizePathLike(value: string) {
  return value.replace(/\\/g, '/').replace(/\/+$/, '').trim().toLowerCase();
}

function isValidGitHubRepoUrl(value: string) {
  return /^https?:\/\/(www\.)?github\.com\/[^/\s]+\/[^/\s]+(?:\.git)?\/?$/i.test(value.trim());
}

function getFlowSteps(sourceType: SourceType, form: ProjectForm, inspection: ProjectInspection | null): FlowStep[] {
  if (sourceType === 'github') {
    return [
      {
        title: 'Paste repository URL',
        detail: 'Drop in the GitHub repo you want DevHub to import.',
        complete: Boolean(form.github_url.trim()),
      },
      {
        title: 'Auto-detect the repo',
        detail: 'DevHub clones it temporarily, detects the stack, and pre-fills the project metadata.',
        complete: Boolean(inspection),
      },
      {
        title: 'Import into DevHub',
        detail: 'Review the detected details and create the managed workspace.',
        complete: Boolean(inspection),
      },
    ];
  }

  if (sourceType === 'folder') {
    return [
      {
        title: 'Choose a local folder',
        detail: 'Pick a real project directory on this machine or paste its path.',
        complete: Boolean(form.local_path.trim()),
      },
      {
        title: 'Auto-detect the folder',
        detail: 'DevHub scans the folder, detects the runtime, and pre-fills the project metadata.',
        complete: Boolean(inspection),
      },
      {
        title: 'Connect the workspace',
        detail: 'Review the detected details and attach the folder to DevHub.',
        complete: Boolean(inspection),
      },
    ];
  }

  return [
    {
      title: 'Describe the idea',
      detail: 'Start with a clear product idea so DevHub can suggest a good scaffold.',
      complete: Boolean(form.idea.trim()),
    },
    {
      title: 'Shape the metadata',
      detail: 'Refine the generated name, description, and stack before creation.',
      complete: Boolean(form.name.trim() || form.description.trim() || form.tech_stack.length > 0),
    },
    {
      title: 'Create the starter',
      detail: 'DevHub scaffolds a runnable project and then fills in blueprint and onboarding.',
      complete: Boolean(form.name.trim() || form.idea.trim()),
    },
  ];
}

function getFlowSummary(sourceType: SourceType, inspection: ProjectInspection | null) {
  if (sourceType === 'github') {
    return inspection
      ? 'Repository detected. DevHub is ready to import it into a managed workspace.'
      : 'Paste a GitHub URL and DevHub will auto-detect the stack, runtime, and editable project metadata.';
  }

  if (sourceType === 'folder') {
    return inspection
      ? 'Local folder detected. DevHub is ready to connect it as a workspace.'
      : 'Choose or paste a folder path and DevHub will auto-detect the runtime, stack, and editable project metadata.';
  }

  return 'Start with an idea, then let DevHub suggest a runnable starter scaffold.';
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [sourceType, setSourceType] = useState<SourceType>('starter');
  const [form, setForm] = useState<ProjectForm>(DEFAULT_FORM);
  const [creating, setCreating] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [inspecting, setInspecting] = useState(false);
  const [pickingFolder, setPickingFolder] = useState(false);
  const [inspection, setInspection] = useState<ProjectInspection | null>(null);
  const [deletingId, setDeletingId] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showAiSettings, setShowAiSettings] = useState(false);
  const [savingAiSettings, setSavingAiSettings] = useState(false);
  const [aiConfig, setAiConfig] = useState({ ...DEFAULT_AI_CONFIG });
  const lastGithubInspectionKey = useRef('');
  const lastFolderInspectionKey = useRef('');

  const currentSource = useMemo(
    () => SOURCE_OPTIONS.find((option) => option.id === sourceType) ?? SOURCE_OPTIONS[0],
    [sourceType]
  );
  const flowSteps = useMemo(() => getFlowSteps(sourceType, form, inspection), [form, inspection, sourceType]);
  const flowProgress = useMemo(() => {
    const completeCount = flowSteps.filter((step) => step.complete).length;
    return Math.round((completeCount / Math.max(flowSteps.length, 1)) * 100);
  }, [flowSteps]);

  const updateForm = (key: keyof ProjectForm, value: string | string[]) => {
    if (key === 'github_url' || key === 'local_path') {
      setInspection(null);
    }
    if (key === 'github_url' || key === 'local_path' || key === 'idea') {
      setError('');
    }
    setForm((current) => ({ ...current, [key]: value }));
  };

  const toggleStack = (stack: string) => {
    setForm((current) => ({
      ...current,
      tech_stack: current.tech_stack.includes(stack)
        ? current.tech_stack.filter((item) => item !== stack)
        : [...current.tech_stack, stack],
    }));
  };

  const fetchProjects = async () => {
    try {
      const response = await fetch(`${API}/projects/`);
      const data = await response.json();
      setProjects(Array.isArray(data.projects) ? data.projects : []);
    } catch {
      setError('Could not load projects right now.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const fetchAiSettings = async () => {
    try {
      const response = await fetch(`${API}/settings/ai/`);
      const data = await response.json();
      if (response.ok) {
        setAiConfig(mergeAiConfig(data.ai_config));
      }
    } catch {
      // Keep the current defaults if settings cannot be loaded.
    }
  };

  useEffect(() => {
    fetchAiSettings();
  }, []);

  const openCreateModal = (nextSource: SourceType = 'starter') => {
    setSourceType(nextSource);
    setForm(DEFAULT_FORM);
    setInspection(null);
    setError('');
    setSuccess('');
    setShowCreate(true);
  };

  const closeCreateModal = () => {
    if (creating || generating || inspecting || pickingFolder) return;
    setShowCreate(false);
    setError('');
  };

  const updateAiConfig = (patch: Partial<typeof DEFAULT_AI_CONFIG>) => {
    setAiConfig((current) => mergeAiConfig({ ...current, ...patch }));
  };

  const handleProviderChange = (provider: string) => {
    setAiConfig((current) => {
      const previous = mergeAiConfig(current);
      const next = mergeAiConfig({ ...previous, provider });
      if (!previous.model || previous.model === defaultModelFor(previous.provider, previous.gemini_mode)) {
        next.model = defaultModelFor(provider, next.gemini_mode);
      }
      return next;
    });
  };

  const handleGeminiModeChange = (geminiMode: string) => {
    setAiConfig((current) => {
      const previous = mergeAiConfig(current);
      const next = mergeAiConfig({ ...previous, gemini_mode: geminiMode });
      if (!previous.model || previous.model === defaultModelFor(previous.provider, previous.gemini_mode)) {
        next.model = defaultModelFor(next.provider, geminiMode);
      }
      return next;
    });
  };

  const saveAiSettings = async () => {
    setSavingAiSettings(true);
    setError('');
    setSuccess('');
    try {
      const response = await fetch(`${API}/settings/ai/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ai_config: mergeAiConfig(aiConfig) }),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(data.error || 'Could not save DevHub AI settings.');
        return;
      }
      setAiConfig(mergeAiConfig(data.ai_config));
      setShowAiSettings(false);
      setSuccess('DevHub AI settings updated.');
    } catch {
      setError('Could not save DevHub AI settings.');
    } finally {
      setSavingAiSettings(false);
    }
  };

  useEffect(() => {
    setInspection(null);
    setError('');
    lastGithubInspectionKey.current = '';
    lastFolderInspectionKey.current = '';
  }, [sourceType]);

  const applyInspection = (data: ProjectInspection) => {
    setInspection(data);
    setForm((current) => ({
      ...current,
      name: data.name || current.name,
      description: data.description || current.description,
      tech_stack: Array.isArray(data.tech_stack) ? data.tech_stack : current.tech_stack,
      local_path: sourceType === 'folder' && data.resolved_path ? data.resolved_path : current.local_path,
    }));
  };

  const requestSuggestedDetails = async (overrideIdea?: string) => {
    const seed =
      sourceType === 'github'
        ? (overrideIdea ?? form.idea).trim() || form.github_url.trim()
        : sourceType === 'folder'
          ? (overrideIdea ?? form.idea).trim() || form.local_path.trim()
          : (overrideIdea ?? form.idea).trim();

    if (!seed) return null;

    const response = await fetch(`${API}/projects/suggest/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        idea: seed,
        source_type: sourceType,
        tech_stack: form.tech_stack,
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || 'Could not generate project details.');
    }
    return data as Pick<ProjectInspection, 'name' | 'description' | 'tech_stack'>;
  };

  const inspectGitHub = async (options?: { githubUrl?: string; silent?: boolean }) => {
    const githubUrl = (options?.githubUrl ?? form.github_url).trim();
    const silent = Boolean(options?.silent);
    if (!githubUrl) {
      if (!silent) setError('Add a GitHub repository URL first.');
      return null;
    }

    setInspecting(true);
    if (!silent) setError('');
    try {
      const response = await fetch(`${API}/projects/import/github/inspect/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          github_url: githubUrl,
          idea: form.idea.trim(),
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        if (!silent) setError(data.error || 'Could not inspect the repository.');
        return null;
      }
      applyInspection(data);
      lastGithubInspectionKey.current = `${githubUrl}::${form.idea.trim()}`;
      return data as ProjectInspection;
    } catch {
      if (!silent) setError('Could not inspect the repository right now.');
      return null;
    } finally {
      setInspecting(false);
    }
  };

  const inspectFolder = async (options?: { localPath?: string; silent?: boolean }) => {
    const localPath = (options?.localPath ?? form.local_path).trim();
    const silent = Boolean(options?.silent);
    if (!localPath) {
      if (!silent) setError('Choose or enter a local folder path first.');
      return null;
    }

    setInspecting(true);
    if (!silent) setError('');
    try {
      const response = await fetch(`${API}/projects/import/folder/inspect/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          local_path: localPath,
          idea: form.idea.trim(),
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        if (!silent) setError(data.error || 'Could not inspect this folder.');
        return null;
      }
      applyInspection(data);
      lastFolderInspectionKey.current = `${normalizePathLike(localPath)}::${form.idea.trim()}`;
      return data as ProjectInspection;
    } catch {
      if (!silent) setError('Could not inspect this folder right now.');
      return null;
    } finally {
      setInspecting(false);
    }
  };

  const chooseFolder = async () => {
    setPickingFolder(true);
    setError('');
    try {
      const response = await fetch(`${API}/projects/import/folder/pick/`, { method: 'POST' });
      const data = await response.json();
      if (!response.ok) {
        setError(data.error || 'Could not open the folder picker.');
        return;
      }

      const selectedPath = data.local_path || '';
      if (!selectedPath) {
        setError('Folder selection was cancelled.');
        return;
      }

      setForm((current) => ({ ...current, local_path: selectedPath }));
      await inspectFolder({ localPath: selectedPath });
    } catch {
      setError('Could not open the folder picker.');
    } finally {
      setPickingFolder(false);
    }
  };

  useEffect(() => {
    if (sourceType !== 'github') return;

    const githubUrl = form.github_url.trim();
    const autoKey = `${githubUrl}::${form.idea.trim()}`;
    if (!isValidGitHubRepoUrl(githubUrl) || lastGithubInspectionKey.current === autoKey) return;

    const timeout = window.setTimeout(() => {
      void inspectGitHub({ githubUrl, silent: true });
    }, 650);

    return () => window.clearTimeout(timeout);
  }, [form.github_url, form.idea, sourceType]);

  useEffect(() => {
    if (sourceType !== 'folder') return;

    const localPath = form.local_path.trim();
    const normalizedPath = normalizePathLike(localPath);
    const autoKey = `${normalizedPath}::${form.idea.trim()}`;
    const looksLikePath = localPath.length > 2 && (/[\\/]/.test(localPath) || /^[A-Za-z]:/.test(localPath));

    if (!looksLikePath || lastFolderInspectionKey.current === autoKey) return;

    const timeout = window.setTimeout(() => {
      void inspectFolder({ localPath, silent: true });
    }, 700);

    return () => window.clearTimeout(timeout);
  }, [form.local_path, form.idea, sourceType]);

  const handleCreate = async () => {
    setError('');
    setSuccess('');

    if (sourceType === 'github' && !form.github_url.trim()) {
      setError('GitHub import needs a repository URL.');
      return;
    }

    if (sourceType === 'folder' && !form.local_path.trim()) {
      setError('Open Folder needs a local project path.');
      return;
    }

    let resolvedInspection = inspection;
    if (sourceType === 'github' && !resolvedInspection) {
      resolvedInspection = await inspectGitHub();
      if (!resolvedInspection) return;
    }

    if (sourceType === 'folder' && !resolvedInspection) {
      resolvedInspection = await inspectFolder();
      if (!resolvedInspection) return;
    }

    let starterSuggestion: Pick<ProjectInspection, 'name' | 'description' | 'tech_stack'> | null = null;
    if (sourceType === 'starter' && form.idea.trim() && (!form.name.trim() || form.tech_stack.length === 0 || !form.description.trim())) {
      setGenerating(true);
      try {
        starterSuggestion = await requestSuggestedDetails();
      } catch (error) {
        setError(error instanceof Error ? error.message : 'Could not generate project details right now.');
        setGenerating(false);
        return;
      }
      setGenerating(false);
    }

    const resolvedName =
      sourceType === 'starter'
        ? form.name.trim() || starterSuggestion?.name?.trim() || form.idea.trim()
        : form.name.trim() || resolvedInspection?.name?.trim() || '';
    if (!resolvedName) {
      setError('Project name is required.');
      return;
    }

    const resolvedDescription =
      sourceType === 'starter'
        ? form.description.trim() || starterSuggestion?.description || ''
        : form.description.trim() || resolvedInspection?.description || '';

    const resolvedTechStack =
      sourceType === 'starter'
        ? (form.tech_stack.length > 0 ? form.tech_stack : starterSuggestion?.tech_stack || [])
        : form.tech_stack.length > 0
          ? form.tech_stack
          : resolvedInspection?.tech_stack || [];

    setCreating(true);
    try {
      const response = await fetch(`${API}/projects/create/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: resolvedName,
          description: resolvedDescription,
          idea: form.idea.trim(),
          github_url: sourceType === 'github' ? form.github_url.trim() : '',
          local_path: sourceType === 'folder' ? form.local_path.trim() : '',
          tech_stack: resolvedTechStack,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(data.error || 'Could not create project.');
        return;
      }
      navigate(`/project/${data.id}`);
    } catch {
      setError('Could not create project because the server could not be reached.');
    } finally {
      setCreating(false);
    }
  };

  const deleteProject = async (projectId: string) => {
    if (!window.confirm('Delete this project and its workspace data?')) return;
    setDeletingId(projectId);
    setError('');
    try {
      const response = await fetch(`${API}/projects/${projectId}/delete/`, { method: 'DELETE' });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        setError(data.error || 'Could not delete the project.');
        return;
      }
      setProjects((current) => current.filter((project) => project.id !== projectId));
      setSuccess('Project deleted.');
    } catch {
      setError('Could not delete the project.');
    } finally {
      setDeletingId('');
    }
  };

  const renderStackSelector = () => (
    <div className="mt-5 flex flex-wrap gap-3">
      {STACK_PRESETS.map((stack) => {
        const active = form.tech_stack.includes(stack);
        return (
          <button
            key={stack}
            type="button"
            onClick={() => toggleStack(stack)}
            className={`rounded-full border px-3 py-2 text-sm transition ${
              active
                ? 'border-slate-900 bg-slate-900 text-white shadow-[0_10px_24px_rgba(15,23,42,0.15)]'
                : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900'
            }`}
          >
            {stack}
          </button>
        );
      })}
    </div>
  );

  const renderFlowStrip = () => (
    <section className="rounded-[30px] border border-slate-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.95),rgba(248,250,252,0.9))] p-5 shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur-xl">
      <div className="grid gap-4 xl:grid-cols-[minmax(250px,320px)_minmax(0,1fr)]">
        <div className="rounded-[24px] border border-slate-200/80 bg-white/88 p-5 shadow-[0_12px_28px_rgba(15,23,42,0.05)]">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-400">Flow</p>
              <h3 className="mt-2 text-xl font-semibold text-slate-950">{currentSource.title}</h3>
            </div>
            <div className="rounded-full border border-slate-200 bg-[#fbfcfe] px-3 py-1.5 text-xs font-medium text-slate-500">
              {flowSteps.filter((step) => step.complete).length} of {flowSteps.length} ready
            </div>
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-500">{getFlowSummary(sourceType, inspection)}</p>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-[linear-gradient(90deg,#0f172a_0%,#334155_100%)] transition-[width] duration-500 ease-out"
              style={{ width: `${flowProgress}%` }}
            />
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          {flowSteps.map((step, index) => (
            <div
              key={`${sourceType}-${step.title}`}
              className={`rounded-[22px] border p-4 shadow-[0_12px_28px_rgba(15,23,42,0.05)] transition ${
                step.complete
                  ? 'border-emerald-100 bg-emerald-50/70'
                  : index === 0 || (!flowSteps[index - 1]?.complete && index > 0)
                    ? 'border-slate-200 bg-white'
                    : 'border-slate-200 bg-[#fbfcfe]'
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-slate-950 text-[11px] font-semibold text-white shadow-[0_10px_20px_rgba(15,23,42,0.18)]">
                  {index + 1}
                </span>
                <span className={`text-[11px] font-medium ${step.complete ? 'text-emerald-600' : 'text-slate-400'}`}>
                  {step.complete ? 'Ready' : 'Next'}
                </span>
              </div>
              <h4 className="mt-3 text-sm font-semibold text-slate-900">{step.title}</h4>
              <p className="mt-1.5 text-xs leading-5 text-slate-500">{step.detail}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );

  const renderInspectionCard = (title: string, emptyTitle: string, emptyBody: string) => (
    <section className="rounded-[28px] border border-slate-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.95),rgba(248,252,255,0.92))] p-6 shadow-[0_18px_48px_rgba(15,23,42,0.08)] backdrop-blur-xl">
      <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-400">{title}</p>
      {inspection ? (
        <div className="mt-5 space-y-5">
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-[22px] border border-slate-200/80 bg-white/90 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Detected Root</p>
              <p className="mt-3 break-words text-sm font-medium text-slate-800">{inspection.resolved_path || inspection.root_name || 'Unknown root'}</p>
            </div>
            <div className="rounded-[22px] border border-slate-200/80 bg-white/90 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Runtime</p>
              <p className="mt-3 text-sm font-medium text-slate-800">
                {inspection.runtime?.runtime_type || 'unknown'}
                {inspection.runtime?.preview_url ? ` · ${inspection.runtime.preview_url}` : ''}
              </p>
            </div>
          </div>

          <div className="rounded-[22px] border border-slate-200/80 bg-white/90 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Detected Stack</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {(inspection.detected_stack?.length ? inspection.detected_stack : form.tech_stack).map((stack) => (
                <span key={stack} className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600">
                  {stack}
                </span>
              ))}
            </div>
          </div>

          <div className="rounded-[22px] border border-slate-200/80 bg-slate-50/80 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Structure Preview</p>
            <pre className="mt-3 max-h-52 overflow-auto whitespace-pre-wrap break-words text-xs leading-6 text-slate-600">
              {inspection.structure_preview || inspection.source_summary || 'Inspection completed.'}
            </pre>
          </div>
        </div>
      ) : inspecting ? (
        <div className="mt-5 flex items-center gap-3 rounded-[22px] border border-slate-200 bg-white/80 px-5 py-5 text-sm text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          Detecting repository structure, stack, and runtime...
        </div>
      ) : (
        <div className="mt-5 rounded-[22px] border border-dashed border-slate-200 bg-white/70 p-5 text-sm leading-7 text-slate-500">
          <p className="font-semibold text-slate-800">{emptyTitle}</p>
          <p className="mt-2">{emptyBody}</p>
        </div>
      )}
    </section>
  );

  const renderSourceFields = () => {
    if (sourceType === 'github') {
      return (
        <div className="space-y-5">
          <section className="rounded-[30px] border border-slate-200/80 bg-white/88 p-6 shadow-[0_24px_60px_rgba(15,23,42,0.08)] backdrop-blur-xl">
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-400">Repository</p>
                <h3 className="mt-2 text-xl font-semibold text-slate-900">Import from GitHub</h3>
                <p className="mt-2 max-w-2xl text-sm leading-7 text-slate-500">
                  Paste a GitHub repository URL and DevHub will auto-detect the codebase, runtime, and project details before import.
                </p>
              </div>
              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => void inspectGitHub()}
                  disabled={inspecting}
                  className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:-translate-y-0.5 disabled:opacity-60"
                >
                  {inspecting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Github className="h-4 w-4" />}
                  Refresh Detection
                </button>
              </div>
            </div>

            <div className="mt-6 grid gap-4">
              <label className="grid gap-2">
                <span className="text-sm font-medium text-slate-700">GitHub URL</span>
                <input
                  value={form.github_url}
                  onChange={(event) => updateForm('github_url', event.target.value)}
                  placeholder="https://github.com/owner/repo"
                  className="w-full rounded-2xl border border-slate-200 bg-white/95 px-4 py-3 text-sm text-slate-900 shadow-[inset_0_1px_0_rgba(255,255,255,0.65)] outline-none transition focus:border-slate-400"
                />
              </label>
            </div>
          </section>

          <div className="grid gap-5">
            {renderInspectionCard(
              'Auto-detected Repository Details',
              'Paste a GitHub URL to start detection',
              'DevHub will clone the repo into a temporary space, detect the stack, and show the imported project details automatically.'
            )}
          </div>
        </div>
      );
    }

    if (sourceType === 'folder') {
      return (
        <div className="space-y-5">
          <section className="rounded-[30px] border border-slate-200/80 bg-white/88 p-6 shadow-[0_24px_60px_rgba(15,23,42,0.08)] backdrop-blur-xl">
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-400">Local Workspace</p>
                <h3 className="mt-2 text-xl font-semibold text-slate-900">Connect an existing folder</h3>
                <p className="mt-2 max-w-2xl text-sm leading-7 text-slate-500">
                  Choose a real folder on this machine or paste its path and DevHub will auto-detect the codebase, runtime, and project details.
                </p>
              </div>
              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={chooseFolder}
                  disabled={pickingFolder || inspecting}
                  className="inline-flex items-center gap-2 rounded-full bg-slate-950 px-4 py-2 text-sm font-semibold text-white shadow-[0_14px_30px_rgba(15,23,42,0.16)] transition hover:-translate-y-0.5 disabled:opacity-60"
                >
                  {pickingFolder ? <Loader2 className="h-4 w-4 animate-spin" /> : <FolderOpen className="h-4 w-4" />}
                  Choose Folder
                </button>
                <button
                  type="button"
                  onClick={() => void inspectFolder()}
                  disabled={inspecting}
                  className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:-translate-y-0.5 disabled:opacity-60"
                >
                  {inspecting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  Refresh Detection
                </button>
              </div>
            </div>

            <div className="mt-6 grid gap-4">
              <label className="grid gap-2">
                <span className="text-sm font-medium text-slate-700">Local Folder Path</span>
                <input
                  value={form.local_path}
                  onChange={(event) => updateForm('local_path', event.target.value)}
                  placeholder="C:\\Users\\USER\\Desktop\\my-project"
                  className="w-full rounded-2xl border border-slate-200 bg-white/95 px-4 py-3 text-sm text-slate-900 shadow-[inset_0_1px_0_rgba(255,255,255,0.65)] outline-none transition focus:border-slate-400"
                />
              </label>

              <p className="rounded-[22px] border border-slate-200/80 bg-slate-50/80 px-4 py-3 text-sm leading-7 text-slate-500">
                DevHub can open a native folder picker because the backend is running locally on this machine. You can still paste a path manually if you prefer.
              </p>
            </div>
          </section>

          <div className="grid gap-5">
            {renderInspectionCard(
              'Auto-detected Project Details',
              'Choose or paste a folder path to start detection',
              'DevHub will scan the actual folder, detect runtime and stack details, and show the connected project details automatically.'
            )}
          </div>
        </div>
      );
    }

    return (
      <div className="space-y-5">
        <section className="rounded-[30px] border border-slate-200/80 bg-white/88 p-6 shadow-[0_24px_60px_rgba(15,23,42,0.08)] backdrop-blur-xl">
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-400">Start Fresh</p>
          <h3 className="mt-2 text-xl font-semibold text-slate-900">Describe the app you want to build</h3>
          <p className="mt-2 max-w-3xl text-sm leading-7 text-slate-500">
            DevHub will infer the project name, stack, and starter type automatically from your idea, then create a runnable mini app you can keep evolving.
          </p>

          <label className="mt-6 grid gap-2">
            <span className="text-sm font-medium text-slate-700">What are you building?</span>
            <textarea
              value={form.idea}
              onChange={(event) => updateForm('idea', event.target.value)}
              rows={6}
              placeholder="Example: A white-dominant AI coding workspace that imports GitHub repos, plans features, and shows live implementation progress."
              className="w-full rounded-[28px] border border-slate-200 bg-white/95 px-4 py-4 text-sm leading-7 text-slate-900 shadow-[inset_0_1px_0_rgba(255,255,255,0.65)] outline-none transition focus:border-slate-400"
            />
          </label>

          <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
            <label className="grid gap-2">
              <span className="text-sm font-medium text-slate-700">Project Name</span>
              <input
                value={form.name}
                onChange={(event) => updateForm('name', event.target.value)}
                placeholder="My Project"
                className="w-full rounded-2xl border border-slate-200 bg-white/95 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-400"
              />
            </label>

            <div className="rounded-[24px] border border-slate-200/80 bg-[linear-gradient(180deg,rgba(248,250,252,0.9),rgba(255,255,255,0.94))] p-4 text-sm leading-7 text-slate-600">
              DevHub will infer the description and generate a working starter from your idea.
            </div>
          </div>

          <div className="mt-5">
            <p className="text-sm font-medium text-slate-700">Tech Stack</p>
            <p className="mt-2 text-sm leading-6 text-slate-500">Pick the stack if you know it, or leave it minimal and DevHub will infer the rest.</p>
            {renderStackSelector()}
          </div>
        </section>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.98),rgba(245,247,251,0.96)_55%,rgba(236,241,247,0.9))] text-slate-900">
      <div className="mx-auto flex min-h-screen max-w-[1440px] flex-col px-6 py-8 lg:px-10">
        <header className="rounded-[32px] border border-white/70 bg-white/78 px-7 py-6 shadow-[0_24px_80px_rgba(15,23,42,0.12)] backdrop-blur-xl">
          <div className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-xs font-semibold uppercase tracking-[0.36em] text-slate-400">DevHub</p>
              <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-950">
                Create, import, or connect projects without the messy setup.
              </h1>
              <p className="mt-4 text-base leading-8 text-slate-600">
                Start from an idea, import an existing repository, or attach a local folder. DevHub keeps blueprint, features, pipeline, onboarding, and workspace tied to the same project source.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              {SOURCE_OPTIONS.map((option) => {
                const Icon = option.id === 'starter' ? Sparkles : option.id === 'github' ? Github : FolderOpen;
                return (
                  <button
                    key={option.id}
                    type="button"
                    onClick={() => openCreateModal(option.id)}
                    className="group rounded-[24px] border border-slate-200/90 bg-white/90 p-4 text-left shadow-[0_16px_36px_rgba(15,23,42,0.08)] transition hover:-translate-y-1 hover:shadow-[0_24px_48px_rgba(15,23,42,0.12)]"
                  >
                    <div className="flex items-center justify-between">
                      <div className="rounded-2xl bg-slate-950 p-2 text-white shadow-[0_12px_24px_rgba(15,23,42,0.18)]">
                        <Icon className="h-4 w-4" />
                      </div>
                      <ArrowRight className="h-4 w-4 text-slate-300 transition group-hover:text-slate-700" />
                    </div>
                    <h2 className="mt-5 text-lg font-semibold text-slate-950">{option.title}</h2>
                    <p className="mt-2 text-sm leading-7 text-slate-500">{option.eyebrow}</p>
                  </button>
                );
              })}
            </div>
          </div>
        </header>

        <section className="mt-8 grid gap-6 xl:grid-cols-[minmax(0,1fr)_21rem]">
          <div className="rounded-[32px] border border-white/70 bg-white/80 p-6 shadow-[0_24px_80px_rgba(15,23,42,0.1)] backdrop-blur-xl">
            <div className="flex flex-col gap-4 border-b border-slate-100 pb-5 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Projects</p>
                <h2 className="mt-2 text-2xl font-semibold text-slate-950">Your workspaces</h2>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={() => setShowAiSettings(true)}
                  className="inline-flex items-center justify-center gap-2 rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 shadow-[0_14px_28px_rgba(15,23,42,0.08)] transition hover:-translate-y-0.5"
                >
                  <Settings2 className="h-4 w-4" />
                  AI Settings
                </button>
                <button
                  type="button"
                  onClick={() => openCreateModal('starter')}
                  className="inline-flex items-center justify-center gap-2 rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white shadow-[0_18px_32px_rgba(15,23,42,0.18)] transition hover:-translate-y-0.5"
                >
                  <Plus className="h-4 w-4" />
                  New Project
                </button>
              </div>
            </div>

            {error ? (
              <div className="mt-5 rounded-2xl border border-rose-200 bg-rose-50/90 px-4 py-3 text-sm text-rose-700">{error}</div>
            ) : null}
            {success ? (
              <div className="mt-5 rounded-2xl border border-emerald-200 bg-emerald-50/90 px-4 py-3 text-sm text-emerald-700">{success}</div>
            ) : null}

            {loading ? (
              <div className="mt-8 flex items-center gap-3 rounded-[28px] border border-slate-200/80 bg-slate-50/80 px-5 py-6 text-sm text-slate-500">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading projects...
              </div>
            ) : projects.length === 0 ? (
              <div className="mt-8 rounded-[28px] border border-dashed border-slate-200 bg-[linear-gradient(180deg,rgba(255,255,255,0.9),rgba(248,250,252,0.92))] p-10 text-center">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-950 text-white shadow-[0_18px_36px_rgba(15,23,42,0.16)]">
                  <Workflow className="h-6 w-6" />
                </div>
                <h3 className="mt-5 text-xl font-semibold text-slate-950">No projects yet</h3>
                <p className="mx-auto mt-3 max-w-xl text-sm leading-7 text-slate-500">
                  Start fresh, import a repository, or connect a local folder. Each path opens into the same workspace, pipeline, and blueprint system after setup.
                </p>
                <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
                  <button
                    type="button"
                    onClick={() => openCreateModal('starter')}
                    className="rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white shadow-[0_16px_32px_rgba(15,23,42,0.18)]"
                  >
                    Start Fresh
                  </button>
                  <button
                    type="button"
                    onClick={() => openCreateModal('github')}
                    className="rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700"
                  >
                    Import GitHub
                  </button>
                  <button
                    type="button"
                    onClick={() => openCreateModal('folder')}
                    className="rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700"
                  >
                    Open Folder
                  </button>
                </div>
              </div>
            ) : (
              <div className="mt-8 grid gap-4 xl:grid-cols-2">
                {projects.map((project) => (
                  <article
                    key={project.id}
                    className="overflow-hidden rounded-[28px] border border-slate-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.94),rgba(248,250,252,0.96))] p-5 shadow-[0_18px_44px_rgba(15,23,42,0.08)] transition hover:-translate-y-1 hover:shadow-[0_26px_54px_rgba(15,23,42,0.12)]"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">
                            {getSourceLabel((project.source_type as SourceType) || 'starter')}
                          </span>
                          <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                            {project.status || 'active'}
                          </span>
                        </div>
                        <h3 className="mt-4 break-words text-xl font-semibold text-slate-950">{project.name}</h3>
                        <p className="mt-3 line-clamp-3 break-words text-sm leading-7 text-slate-500">{project.description}</p>
                      </div>

                      <button
                        type="button"
                        onClick={() => deleteProject(project.id)}
                        disabled={deletingId === project.id}
                        className="rounded-2xl border border-rose-200 bg-white/90 p-2 text-rose-500 transition hover:bg-rose-50 disabled:opacity-60"
                        aria-label={`Delete ${project.name}`}
                      >
                        {deletingId === project.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                      </button>
                    </div>

                    <div className="mt-5 flex flex-wrap gap-2">
                      {(project.tech_stack || []).slice(0, 5).map((stack) => (
                        <span key={stack} className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600">
                          {stack}
                        </span>
                      ))}
                    </div>

                    <div className="mt-6 flex items-center justify-between gap-4">
                      <div className="min-w-0 flex-1 overflow-hidden text-xs text-slate-400">
                        <span className="block truncate">{getProjectLocation(project)}</span>
                      </div>
                      <Link
                        to={`/project/${project.id}`}
                        className="inline-flex shrink-0 items-center gap-2 rounded-full bg-slate-950 px-4 py-2 text-sm font-semibold text-white shadow-[0_14px_28px_rgba(15,23,42,0.16)]"
                      >
                        Open
                        <ArrowRight className="h-4 w-4" />
                      </Link>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </div>

          <aside className="grid gap-5">
            <div className="rounded-[30px] border border-white/70 bg-white/78 p-6 shadow-[0_20px_56px_rgba(15,23,42,0.1)] backdrop-blur-xl">
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">How it connects</p>
              <h3 className="mt-3 text-xl font-semibold text-slate-950">One project, one shared system.</h3>
              <ul className="mt-5 space-y-4 text-sm leading-7 text-slate-600">
                <li>Blueprint captures intent and architecture from the same project source.</li>
                <li>Features and pipeline track implementation work against that shared blueprint.</li>
                <li>Workspace and chat operate on the same codebase and runtime, not a disconnected copy.</li>
              </ul>
            </div>

            <div className="rounded-[30px] border border-white/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.88),rgba(247,248,251,0.92))] p-6 shadow-[0_20px_56px_rgba(15,23,42,0.1)] backdrop-blur-xl">
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Recommended first step</p>
              <h3 className="mt-3 text-xl font-semibold text-slate-950">Use the right setup path.</h3>
              <p className="mt-3 text-sm leading-7 text-slate-600">
                New product? Use <span className="font-semibold text-slate-900">Start Fresh</span>. Existing online repo? Use <span className="font-semibold text-slate-900">Import GitHub</span>. Existing local codebase? Use <span className="font-semibold text-slate-900">Open Folder</span>.
              </p>
            </div>
          </aside>
        </section>
      </div>

      {showAiSettings ? (
        <div className="fixed inset-0 z-[55] flex items-center justify-center bg-[rgba(15,23,42,0.18)] px-4 py-4 backdrop-blur-sm">
          <div className="max-h-[calc(100vh-2rem)] w-full max-w-3xl overflow-y-auto rounded-[36px] border border-white/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(248,250,252,0.98))] shadow-[0_36px_120px_rgba(15,23,42,0.18)]">
            <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-6 py-6 lg:px-8 lg:py-7">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.32em] text-slate-400">DevHub Settings</p>
                <h2 className="mt-3 text-2xl font-semibold tracking-tight text-slate-950 lg:text-3xl">Global AI provider</h2>
                <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-500">
                  These settings power DevHub itself, so blueprint generation, planning, chat, review, specs, and code generation all use the same provider across projects.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowAiSettings(false)}
                className="rounded-2xl border border-slate-200 bg-white/90 p-2 text-slate-500 transition hover:text-slate-900"
                aria-label="Close AI settings"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="px-6 py-6 lg:px-8 lg:py-7">
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">Provider</label>
                  <select
                    value={aiConfig.provider}
                    onChange={(event) => handleProviderChange(event.target.value)}
                    className="h-11 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-700 outline-none transition focus:border-slate-400"
                  >
                    <option value="openai">OpenAI</option>
                    <option value="claude">Claude</option>
                    <option value="gemini">Gemini</option>
                    <option value="openrouter">OpenRouter</option>
                  </select>
                </div>
                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">Model</label>
                  <input
                    type="text"
                    value={aiConfig.model}
                    onChange={(event) => updateAiConfig({ model: event.target.value })}
                    placeholder="Enter the exact model id"
                    className="h-11 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-700 outline-none transition focus:border-slate-400"
                  />
                  <div className="mt-3 flex flex-wrap gap-2">
                    {(PROVIDER_MODEL_PRESETS[aiConfig.provider] || []).map((model) => (
                      <button
                        key={model}
                        type="button"
                        onClick={() => updateAiConfig({ model })}
                        className={`rounded-full px-3 py-1.5 text-[11px] font-medium transition ${
                          aiConfig.model === model
                            ? 'bg-slate-950 text-white shadow-[0_12px_24px_rgba(15,23,42,0.16)]'
                            : 'border border-slate-200 bg-white text-slate-600 hover:border-slate-300'
                        }`}
                      >
                        {model}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {aiConfig.provider === 'gemini' ? (
                <div className="mt-5 grid gap-4 md:grid-cols-2">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">Gemini Mode</label>
                    <select
                      value={aiConfig.gemini_mode}
                      onChange={(event) => handleGeminiModeChange(event.target.value)}
                      className="h-11 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-700 outline-none transition focus:border-slate-400"
                    >
                      <option value="api_key">Gemini API Key</option>
                      <option value="gemini_cli">Gemini CLI</option>
                      <option value="vertexai">Vertex AI</option>
                    </select>
                  </div>
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">Base URL</label>
                    <input
                      type="text"
                      value={aiConfig.base_url}
                      onChange={(event) => updateAiConfig({ base_url: event.target.value })}
                      placeholder={aiConfig.gemini_mode === 'vertexai' ? 'Optional custom Vertex AI base URL' : 'Optional Gemini API base URL'}
                      className="h-11 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-700 outline-none transition focus:border-slate-400"
                    />
                  </div>
                </div>
              ) : null}

              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <div>
                  <label className="mb-2 block text-sm font-medium text-slate-700">
                    {aiConfig.provider === 'gemini' && aiConfig.gemini_mode === 'gemini_cli' ? 'Gemini API Key (Optional)' : 'API Key'}
                  </label>
                  <input
                    type="password"
                    value={aiConfig.api_key}
                    onChange={(event) => updateAiConfig({ api_key: event.target.value })}
                    placeholder={
                      aiConfig.provider === 'claude'
                        ? 'Anthropic API key'
                        : aiConfig.provider === 'openrouter'
                          ? 'OpenRouter API key'
                          : aiConfig.provider === 'gemini'
                            ? 'Gemini API key'
                            : 'OpenAI API key'
                    }
                    className="h-11 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-700 outline-none transition focus:border-slate-400"
                  />
                </div>
                {aiConfig.provider !== 'gemini' ? (
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">Base URL</label>
                    <input
                      type="text"
                      value={aiConfig.base_url}
                      onChange={(event) => updateAiConfig({ base_url: event.target.value })}
                      placeholder={aiConfig.provider === 'openrouter' ? 'https://openrouter.ai/api/v1' : 'Optional custom API base URL'}
                      className="h-11 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-700 outline-none transition focus:border-slate-400"
                    />
                  </div>
                ) : null}
              </div>

              {aiConfig.provider === 'gemini' && aiConfig.gemini_mode === 'gemini_cli' ? (
                <div className="mt-5">
                  <label className="mb-2 block text-sm font-medium text-slate-700">Gemini CLI Command</label>
                  <input
                    type="text"
                    value={aiConfig.gemini_cli_command}
                    onChange={(event) => updateAiConfig({ gemini_cli_command: event.target.value })}
                    placeholder="gemini"
                    className="h-11 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-700 outline-none transition focus:border-slate-400"
                  />
                  <p className="mt-2 text-xs leading-5 text-slate-500">
                    DevHub calls the command with `-m` and `-p` by default. Advanced command templates can use <code>{'{model}'}</code> and <code>{'{prompt_file}'}</code>.
                  </p>
                </div>
              ) : null}

              {aiConfig.provider === 'gemini' && aiConfig.gemini_mode === 'vertexai' ? (
                <div className="mt-5 grid gap-4 md:grid-cols-2">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">Google Cloud Project</label>
                    <input
                      type="text"
                      value={aiConfig.vertex_project}
                      onChange={(event) => updateAiConfig({ vertex_project: event.target.value })}
                      placeholder="my-gcp-project"
                      className="h-11 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-700 outline-none transition focus:border-slate-400"
                    />
                  </div>
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">Vertex Location</label>
                    <input
                      type="text"
                      value={aiConfig.vertex_location}
                      onChange={(event) => updateAiConfig({ vertex_location: event.target.value })}
                      placeholder="us-central1"
                      className="h-11 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-700 outline-none transition focus:border-slate-400"
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="mb-2 block text-sm font-medium text-slate-700">Vertex Access Token (Optional)</label>
                    <input
                      type="password"
                      value={aiConfig.vertex_access_token}
                      onChange={(event) => updateAiConfig({ vertex_access_token: event.target.value })}
                      placeholder="Leave blank to let DevHub use gcloud auth print-access-token"
                      className="h-11 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-700 outline-none transition focus:border-slate-400"
                    />
                  </div>
                </div>
              ) : null}

              <div className="mt-7 flex flex-wrap items-center justify-end gap-3 border-t border-slate-100 pt-6">
                <button
                  type="button"
                  onClick={() => setShowAiSettings(false)}
                  className="rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={saveAiSettings}
                  disabled={savingAiSettings}
                  className="inline-flex items-center gap-2 rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white shadow-[0_18px_32px_rgba(15,23,42,0.18)] disabled:opacity-60"
                >
                  {savingAiSettings ? <Loader2 className="h-4 w-4 animate-spin" /> : <Settings2 className="h-4 w-4" />}
                  {savingAiSettings ? 'Saving...' : 'Save AI Settings'}
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {showCreate ? (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-[rgba(15,23,42,0.18)] px-4 py-4 backdrop-blur-sm lg:items-center">
          <div className="max-h-[calc(100vh-2rem)] w-full max-w-[1180px] overflow-hidden rounded-[36px] border border-white/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.94),rgba(248,250,252,0.98))] shadow-[0_36px_120px_rgba(15,23,42,0.18)]">
            <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-6 py-6 lg:px-8 lg:py-7">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.32em] text-slate-400">Project Setup</p>
                <h2 className="mt-3 text-2xl font-semibold tracking-tight text-slate-950 lg:text-3xl">Create a project the clean way</h2>
              </div>
              <button
                type="button"
                onClick={closeCreateModal}
                className="rounded-2xl border border-slate-200 bg-white/90 p-2 text-slate-500 transition hover:text-slate-900"
                aria-label="Close project setup"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="max-h-[calc(100vh-8rem)] min-h-0 overflow-y-auto">
              <div className="border-b border-slate-100 bg-white/72 px-5 py-5 lg:px-7">
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Source</p>
                <div className="mt-5 grid gap-3 sm:grid-cols-3">
                  {SOURCE_OPTIONS.map((option) => {
                    const selected = option.id === sourceType;
                    return (
                      <button
                        key={option.id}
                        type="button"
                        onClick={() => setSourceType(option.id)}
                        className={`rounded-[24px] border px-4 py-4 text-left transition ${
                          selected
                            ? 'border-slate-900 bg-slate-950 text-white shadow-[0_22px_40px_rgba(15,23,42,0.16)]'
                            : 'border-slate-200/90 bg-white/90 text-slate-700 shadow-[0_14px_32px_rgba(15,23,42,0.06)] hover:-translate-y-0.5'
                        }`}
                      >
                        <h3 className="text-base font-semibold lg:text-lg">{option.title}</h3>
                        <p className={`mt-2 text-sm leading-6 ${selected ? 'text-slate-200' : 'text-slate-500'}`}>
                          {option.eyebrow}
                        </p>
                        <p className={`mt-2 text-sm leading-6 ${selected ? 'text-slate-300' : 'text-slate-400'}`}>
                          {option.detail}
                        </p>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="px-5 py-5 lg:px-7 lg:py-7">
                {renderFlowStrip()}

                {error ? (
                  <div className="mb-5 rounded-2xl border border-rose-200 bg-rose-50/90 px-4 py-3 text-sm text-rose-700">{error}</div>
                ) : null}

                {renderSourceFields()}

                <div className="mt-7 flex flex-col gap-3 border-t border-slate-100 pt-6 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-sm text-slate-500">
                    {sourceType === 'starter'
                      ? 'A managed project folder and a working starter app will be created from your input.'
                      : sourceType === 'github'
                        ? inspection
                          ? 'Repository detected. Import will clone it into a managed DevHub workspace.'
                          : 'Paste a valid repository URL and DevHub will detect the project details automatically.'
                        : inspection
                          ? 'Folder detected. DevHub is ready to connect it as a local workspace.'
                          : 'Choose or paste a local folder path and DevHub will detect the project details automatically.'}
                  </p>
                  <div className="flex flex-wrap items-center gap-3">
                    <button
                      type="button"
                      onClick={closeCreateModal}
                      className="rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={handleCreate}
                      disabled={creating || inspecting}
                      className="inline-flex items-center gap-2 rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white shadow-[0_18px_32px_rgba(15,23,42,0.18)] disabled:opacity-60"
                    >
                      {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                      {sourceType === 'starter'
                        ? 'Create Working Starter'
                        : sourceType === 'github'
                          ? 'Import GitHub Project'
                          : 'Connect Folder Project'}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
