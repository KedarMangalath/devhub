import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  CheckCircle2,
  ChevronLeft,
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

import GitHubConnectPanel from '../components/GitHubConnectPanel';
import AppSettingsButton from '../components/AppSettingsButton';
import ToastStack from '../components/ToastStack';

const API = 'http://localhost:8000/api';

type SourceType = 'starter' | 'github' | 'github_connect' | 'folder';
type CreateStep = 'source' | 'details';

type Project = {
  id: string;
  name: string;
  description: string;
  status: string;
  raw_status?: string;
  tech_stack: string[];
  github_url?: string | null;
  local_path?: string | null;
  source_type?: SourceType;
  context_initializing?: boolean;
  documentation_status?: string;
  scaffold_progress?: ScaffoldProgress | null;
};

type ScaffoldTask = {
  id?: string;
  label: string;
  status?: string;
};

type ScaffoldProgress = {
  status?: string;
  title?: string;
  message?: string;
  progress_pct?: number;
  tasks?: ScaffoldTask[];
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
  github_connection_id?: number;
  github_repository_full_name?: string;
  github_repository?: {
    full_name?: string;
    html_url?: string;
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
    id: 'github_connect',
    title: 'Connect GitHub',
    eyebrow: 'Sign in and import accessible repos',
    summary:
      'Sign in with GitHub, browse repositories you can access, and keep issues and pull requests connected after import.',
    detail:
      'Best for private repositories, personal repos, and org repos where the signed-in account already has access.',
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
  provider: 'gemini',
  model: 'gemini-3.1-pro-preview',
  api_key: '',
  base_url: '',
  gemini_mode: 'vertexai',
  gemini_cli_command: 'gemini',
  vertex_project: 'noted-computing-459609-n2',
  vertex_location: 'global',
  vertex_access_token: '',
};

const PROVIDER_MODEL_PRESETS: Record<string, string[]> = {
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-5', 'gpt-5-mini'],
  claude: ['claude-3-5-sonnet-latest', 'claude-3-5-haiku-latest'],
  gemini: ['gemini-3.1-pro-preview', 'gemini-2.5-pro', 'gemini-2.5-flash'],
  openrouter: ['google/gemini-3.1-pro-preview', 'openai/gpt-4o-mini', 'anthropic/claude-3.5-sonnet', 'google/gemini-2.5-pro'],
};

function defaultModelFor(provider: string, geminiMode: string) {
  if (provider === 'claude') return 'claude-3-5-sonnet-latest';
  if (provider === 'gemini') return geminiMode === 'vertexai' ? 'gemini-3.1-pro-preview' : 'gemini-3.1-pro-preview';
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

function isScaffoldingProject(project: Project) {
  const progressStatus = project.scaffold_progress?.status;
  return project.status === 'scaffolding' || progressStatus === 'running';
}

function isBusyProject(project: Project) {
  const progressStatus = project.scaffold_progress?.status;
  return isScaffoldingProject(project) || Boolean(project.context_initializing && progressStatus !== 'done' && progressStatus !== 'failed');
}

function projectStatusLabel(project: Project) {
  if (isScaffoldingProject(project)) return 'Scaffolding';
  if (project.context_initializing) return 'Syncing';
  if (project.scaffold_progress?.status === 'failed') return 'Needs attention';
  return project.status || 'active';
}

function currentScaffoldTask(progress?: ScaffoldProgress | null) {
  const tasks = Array.isArray(progress?.tasks) ? progress?.tasks || [] : [];
  return tasks.find((task) => task.status === 'running') || tasks.find((task) => task.status === 'pending') || null;
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

function getFlowSteps(
  sourceType: SourceType,
  form: ProjectForm,
  inspection: ProjectInspection | null,
  githubSelection?: { github_connection_id: number | null; github_repository_full_name: string }
): FlowStep[] {
  if (sourceType === 'github_connect') {
    return [
      {
        title: 'Connect your GitHub account',
        detail: 'Open the browser auth flow and let DevHub read the repositories available to your signed-in account.',
        complete: Boolean(githubSelection?.github_connection_id),
      },
      {
        title: 'Select a repository',
        detail: 'Choose one repository from the connected account and let DevHub inspect it before import.',
        complete: Boolean(githubSelection?.github_repository_full_name),
      },
      {
        title: 'Import with GitHub metadata attached',
        detail: 'DevHub imports the repo and keeps issues, pull requests, and repo metadata connected to the project.',
        complete: Boolean(inspection),
      },
    ];
  }

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

function getFlowSummary(
  sourceType: SourceType,
  inspection: ProjectInspection | null,
  githubSelection?: { github_connection_id: number | null; github_repository_full_name: string }
) {
  if (sourceType === 'github_connect') {
    return inspection
      ? 'Connected GitHub repository detected. DevHub is ready to import it with repo metadata attached.'
      : githubSelection?.github_connection_id
        ? githubSelection.github_repository_full_name
          ? 'Repository selected. DevHub is preparing the connected import details.'
          : 'GitHub is already connected. Choose the repository you want DevHub to inspect next.'
        : 'Connect GitHub in the browser, then choose the repository you want DevHub to inspect.';
  }

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

function getSourceIcon(sourceType: SourceType) {
  if (sourceType === 'starter') return Sparkles;
  if (sourceType === 'folder') return FolderOpen;
  return Github;
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [createStep, setCreateStep] = useState<CreateStep>('source');
  const [sourceType, setSourceType] = useState<SourceType>('starter');
  const [form, setForm] = useState<ProjectForm>(DEFAULT_FORM);
  const [creating, setCreating] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [inspecting, setInspecting] = useState(false);
  const [pickingFolder, setPickingFolder] = useState(false);
  const [inspection, setInspection] = useState<ProjectInspection | null>(null);
  const [githubAppSelection, setGitHubAppSelection] = useState<{
    github_connection_id: number | null;
    github_repository_full_name: string;
    github_url?: string;
  }>({
    github_connection_id: null,
    github_repository_full_name: '',
    github_url: '',
  });
  const [deletingId, setDeletingId] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showAiSettings, setShowAiSettings] = useState(false);
  const [savingAiSettings, setSavingAiSettings] = useState(false);
  const [createHeaderCompact, setCreateHeaderCompact] = useState(false);
  const [aiConfig, setAiConfig] = useState({ ...DEFAULT_AI_CONFIG });
  const lastGithubInspectionKey = useRef('');
  const lastFolderInspectionKey = useRef('');
  const createBodyRef = useRef<HTMLDivElement | null>(null);

  const flowSteps = useMemo(
    () => getFlowSteps(sourceType, form, inspection, githubAppSelection),
    [form, githubAppSelection, inspection, sourceType]
  );
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

  const fetchProjects = useCallback(async () => {
    try {
      const response = await fetch(`${API}/projects/`);
      const data = await response.json();
      setProjects(Array.isArray(data.projects) ? data.projects : []);
    } catch {
      setError('Could not load projects right now.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const hasBusyProjects = useMemo(() => projects.some(isBusyProject), [projects]);

  useEffect(() => {
    if (!hasBusyProjects) return undefined;
    const timer = window.setInterval(() => {
      void fetchProjects();
    }, 1500);
    return () => window.clearInterval(timer);
  }, [fetchProjects, hasBusyProjects]);

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

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const shouldOpenCreate = params.get('create') === '1';
    const requestedSource = params.get('source');
    const githubState = params.get('github');
    const githubLogin = params.get('github_login');
    const githubReason = params.get('reason');

    if (githubState === 'connected') {
      setSuccess(githubLogin ? `GitHub connected as @${githubLogin}.` : 'GitHub connected.');
    } else if (githubState === 'error') {
      setError(githubReason ? `GitHub connection failed: ${githubReason}` : 'GitHub connection failed.');
    }

    if (shouldOpenCreate) {
      const nextSource: SourceType =
        requestedSource === 'github' || requestedSource === 'github_connect' || requestedSource === 'folder'
          ? requestedSource
          : 'starter';
      openCreateModal(nextSource, 'details');
    }

    if (shouldOpenCreate || githubState) {
      const nextUrl = new URL(window.location.href);
      nextUrl.searchParams.delete('create');
      nextUrl.searchParams.delete('source');
      nextUrl.searchParams.delete('github');
      nextUrl.searchParams.delete('github_login');
      nextUrl.searchParams.delete('reason');
      window.history.replaceState({}, '', nextUrl.toString());
    }
  }, []);

  useEffect(() => {
    if (!error) return undefined;
    const timeout = window.setTimeout(() => setError(''), 2600);
    return () => window.clearTimeout(timeout);
  }, [error]);

  useEffect(() => {
    if (!success) return undefined;
    const timeout = window.setTimeout(() => setSuccess(''), 1800);
    return () => window.clearTimeout(timeout);
  }, [success]);

  const openCreateModal = (nextSource?: SourceType, nextStep: CreateStep = 'source') => {
    setSourceType(nextSource ?? 'starter');
    setCreateStep(nextStep);
    setCreateHeaderCompact(false);
    setForm(DEFAULT_FORM);
    setInspection(null);
    setGitHubAppSelection({ github_connection_id: null, github_repository_full_name: '', github_url: '' });
    setError('');
    setSuccess('');
    setShowCreate(true);
  };

  const closeCreateModal = () => {
    if (creating || generating || inspecting || pickingFolder) return;
    setShowCreate(false);
    setCreateStep('source');
    setCreateHeaderCompact(false);
    setError('');
  };

  const beginCreateSetup = (nextSource: SourceType) => {
    setSourceType(nextSource);
    setCreateStep('details');
    setCreateHeaderCompact(false);
    setInspection(null);
    setGitHubAppSelection({ github_connection_id: null, github_repository_full_name: '', github_url: '' });
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
    setGitHubAppSelection({ github_connection_id: null, github_repository_full_name: '', github_url: '' });
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

    if (sourceType === 'github_connect' && !githubAppSelection.github_repository_full_name) {
      setError('Connect GitHub and choose a repository before importing.');
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

    if (sourceType === 'github_connect' && !resolvedInspection) {
      setError('Inspect the selected GitHub repository before creating the project.');
      return;
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
            github_connection_id: sourceType === 'github_connect' ? githubAppSelection.github_connection_id : null,
            github_repository_full_name:
              sourceType === 'github_connect' ? githubAppSelection.github_repository_full_name : '',
            local_path: sourceType === 'folder' ? form.local_path.trim() : '',
            tech_stack: resolvedTechStack,
          }),
        });
      const data = await response.json();
      if (!response.ok) {
        setError(data.error || 'Could not create project.');
        return;
      }
      navigate(`/project/${data.id}${sourceType === 'starter' ? '?autorun=1' : ''}`);
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
            className={`rounded-full border px-3.5 py-2.5 text-[14px] font-medium transition ${
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
    <section className="setup-plum-surface smooth-panel-enter rounded-[30px] border p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-400">Flow</p>
          <p className="mt-2 text-[15px] leading-7 text-slate-700">{getFlowSummary(sourceType, inspection, githubAppSelection)}</p>
        </div>
        <div className="setup-plum-chip rounded-full border px-3 py-1.5 text-[13px] font-semibold text-slate-700">
          {flowSteps.filter((step) => step.complete).length} of {flowSteps.length} ready
        </div>
      </div>

      <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
        <div
          className="setup-plum-progress h-full rounded-full transition-[width] duration-500 ease-out"
          style={{ width: `${flowProgress}%` }}
        />
      </div>

      <div className="mt-5 grid gap-3 xl:grid-cols-3">
        {flowSteps.map((step, index) => (
          <div
            key={`${sourceType}-${step.title}`}
            className={`smooth-card-enter rounded-[22px] border bg-white p-4 shadow-[0_14px_30px_rgba(112,67,79,0.07)] ${
              step.complete
                ? 'border-[rgba(112,67,79,0.10)] shadow-[0_18px_34px_rgba(112,67,79,0.09)]'
                : index === 0 || (!flowSteps[index - 1]?.complete && index > 0)
                  ? 'border-[rgba(112,67,79,0.08)] shadow-[0_16px_30px_rgba(112,67,79,0.06)]'
                  : 'border-[rgba(112,67,79,0.06)] shadow-[0_14px_28px_rgba(112,67,79,0.05)]'
            }`}
            style={{ animationDelay: `${index * 45}ms` }}
          >
            <div className="flex items-center justify-between gap-3">
              <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-[#70434f] text-[12px] font-semibold text-white shadow-[0_10px_20px_rgba(112,67,79,0.18)]">
                {index + 1}
              </span>
              <span className={`text-[12px] font-semibold ${step.complete ? 'text-[#70434f]' : 'text-slate-500'}`}>
                {step.complete ? 'Ready' : 'Next'}
              </span>
            </div>
            <h4 className="mt-3 text-[15px] font-semibold leading-6 text-slate-950">{step.title}</h4>
          </div>
        ))}
      </div>
    </section>
  );

  const renderFlowSidebar = () => (
    <section className="setup-plum-surface smooth-panel-enter rounded-[30px] border p-5 xl:sticky xl:top-0">
      <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-400">Flow</p>
      <p className="mt-3 text-[15px] leading-8 text-slate-700">{getFlowSummary(sourceType, inspection, githubAppSelection)}</p>
      <div className="setup-plum-chip mt-4 inline-flex rounded-full border px-3 py-1.5 text-[13px] font-semibold text-slate-700">
        {flowSteps.filter((step) => step.complete).length} of {flowSteps.length} ready
      </div>

      <div className="mt-5 space-y-3">
        {flowSteps.map((step, index) => (
          <div
            key={`sidebar-${sourceType}-${step.title}`}
            className={`smooth-card-enter rounded-[22px] border bg-white p-4 shadow-[0_14px_30px_rgba(112,67,79,0.07)] ${
              step.complete
                ? 'border-[rgba(112,67,79,0.10)] shadow-[0_18px_34px_rgba(112,67,79,0.09)]'
                : index === 0 || (!flowSteps[index - 1]?.complete && index > 0)
                  ? 'border-[rgba(112,67,79,0.08)] shadow-[0_16px_30px_rgba(112,67,79,0.06)]'
                  : 'border-[rgba(112,67,79,0.06)] shadow-[0_14px_28px_rgba(112,67,79,0.05)]'
            }`}
            style={{ animationDelay: `${index * 45}ms` }}
          >
            <div className="flex items-start gap-3">
              <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#70434f] text-[12px] font-semibold text-white shadow-[0_10px_20px_rgba(112,67,79,0.18)]">
                {index + 1}
              </span>
              <div className="min-w-0">
                <p className={`text-[12px] font-semibold uppercase tracking-[0.18em] ${step.complete ? 'text-[#70434f]' : 'text-slate-500'}`}>
                  {step.complete ? 'Ready' : 'Next'}
                </p>
                <h4 className="mt-1 text-[15px] font-semibold leading-6 text-slate-950">{step.title}</h4>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );

  const renderInspectionCard = (title: string, emptyTitle: string, emptyBody: string) => (
    <section className="setup-plum-surface rounded-[28px] border p-6">
      <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-400">{title}</p>
      {inspection ? (
        <div className="mt-5 space-y-5">
          <div className="grid gap-3 md:grid-cols-2">
            <div className="setup-plum-card rounded-[22px] border p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Detected Root</p>
              <p className="mt-3 break-words text-[15px] font-medium leading-7 text-slate-900">{inspection.resolved_path || inspection.root_name || 'Unknown root'}</p>
            </div>
            <div className="setup-plum-card rounded-[22px] border p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Runtime</p>
              <p className="mt-3 text-[15px] font-medium leading-7 text-slate-900">
                {inspection.runtime?.runtime_type || 'unknown'}
                {inspection.runtime?.preview_url ? ` · ${inspection.runtime.preview_url}` : ''}
              </p>
            </div>
          </div>

          <div className="setup-plum-card rounded-[22px] border p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Detected Stack</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {(inspection.detected_stack?.length ? inspection.detected_stack : form.tech_stack).map((stack) => (
                <span key={stack} className="setup-plum-chip rounded-full border px-3 py-1.5 text-[13px] font-semibold text-slate-900">
                  {stack}
                </span>
              ))}
            </div>
          </div>

          <div className="setup-plum-card rounded-[22px] border p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Structure Preview</p>
            <pre className="mt-3 max-h-52 overflow-auto whitespace-pre-wrap break-words text-[13px] leading-7 text-slate-700">
              {inspection.structure_preview || inspection.source_summary || 'Inspection completed.'}
            </pre>
          </div>
        </div>
      ) : inspecting ? (
        <div className="setup-plum-card mt-5 flex items-center gap-3 rounded-[22px] border px-5 py-5 text-sm text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          Detecting repository structure, stack, and runtime...
        </div>
      ) : (
        <div className="setup-plum-card mt-5 rounded-[22px] border border-dashed p-5 text-[15px] leading-8 text-slate-700">
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
          <section className="setup-plum-surface rounded-[30px] border p-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-400">Repository</p>
                <h3 className="font-display-serif mt-2 text-[1.75rem] font-semibold leading-none text-slate-950">Import from GitHub</h3>
                <p className="mt-2 max-w-2xl text-[15px] leading-8 text-slate-700">
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
                <span className="text-[15px] font-semibold text-slate-800">GitHub URL</span>
                <input
                  value={form.github_url}
                  onChange={(event) => updateForm('github_url', event.target.value)}
                  placeholder="https://github.com/owner/repo"
                  className="setup-plum-input w-full rounded-2xl border px-4 py-3 text-[15px] text-slate-900 outline-none transition focus:border-[rgba(112,67,79,0.16)]"
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

    if (sourceType === 'github_connect') {
      return (
        <div className="space-y-5">
          <GitHubConnectPanel
            apiBase={API}
            idea={form.idea}
            inspecting={inspecting}
            onInspection={(data) => {
              applyInspection(data);
              setGitHubAppSelection({
                github_connection_id: data.github_connection_id || null,
                github_repository_full_name: data.github_repository_full_name || '',
                github_url: data.github_url || '',
              });
            }}
            onSelectionChange={(selection) => {
              setInspection(null);
              setGitHubAppSelection(selection);
            }}
            onError={(message) => setError(message)}
          />

          <div className="grid gap-5">
            {renderInspectionCard(
              'Auto-detected Connected Repository Details',
              'Connect GitHub and select a repository',
              'DevHub will inspect the selected repository, detect the stack and runtime, and import it with connected GitHub access.'
            )}
          </div>
        </div>
      );
    }

    if (sourceType === 'folder') {
      return (
        <div className="space-y-5">
          <section className="setup-plum-surface rounded-[30px] border p-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-400">Local Workspace</p>
                <h3 className="font-display-serif mt-2 text-[1.75rem] font-semibold leading-none text-slate-950">Connect an existing folder</h3>
                <p className="mt-2 max-w-2xl text-[15px] leading-8 text-slate-700">
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
                <span className="text-[15px] font-semibold text-slate-800">Local Folder Path</span>
                <input
                  value={form.local_path}
                  onChange={(event) => updateForm('local_path', event.target.value)}
                  placeholder="C:\\Users\\USER\\Desktop\\my-project"
                  className="setup-plum-input w-full rounded-2xl border px-4 py-3 text-[15px] text-slate-900 outline-none transition focus:border-[rgba(112,67,79,0.16)]"
                />
              </label>

              <p className="setup-plum-card rounded-[22px] border px-4 py-3 text-[15px] leading-8 text-slate-700">
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
        <section className="setup-plum-surface rounded-[30px] border p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-400">Start Fresh</p>
          <h3 className="font-display-serif mt-2 text-[1.9rem] font-semibold leading-none text-slate-950">Describe the app you want to build</h3>
          <p className="mt-2 max-w-3xl text-[15px] leading-8 text-slate-700">
            DevHub will infer the project name, stack, and starter type automatically from your idea, then create a runnable mini app you can keep evolving.
          </p>

          <div className="mt-6 grid gap-5 xl:grid-cols-[minmax(0,1.28fr)_minmax(320px,0.72fr)] xl:items-start">
            <label className="grid gap-3">
              <span className="text-[15px] font-semibold text-slate-800">What are you building?</span>
              <textarea
                value={form.idea}
                onChange={(event) => updateForm('idea', event.target.value)}
                rows={4}
                placeholder="Example: A white-dominant AI coding workspace that imports GitHub repos, plans features, and shows live implementation progress."
                className="setup-plum-input min-h-[182px] w-full rounded-[24px] border px-4 py-4 text-[15px] leading-8 text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-[rgba(112,67,79,0.16)]"
              />
            </label>

            <div className="setup-plum-card rounded-[24px] border p-5">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">What DevHub Will Shape</p>
              <div className="mt-4 space-y-3 text-[15px] leading-7 text-slate-700">
                <p>Project name and summary from your prompt.</p>
                <p>Starter stack and runnable first version.</p>
                <p>Initial context for blueprint, planning, and implementation.</p>
              </div>
            </div>
          </div>

          <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
            <label className="grid gap-2">
              <span className="text-[15px] font-semibold text-slate-800">Project Name</span>
              <input
                value={form.name}
                onChange={(event) => updateForm('name', event.target.value)}
                placeholder="My Project"
                className="setup-plum-input w-full rounded-2xl border px-4 py-3 text-[15px] text-slate-900 outline-none transition focus:border-[rgba(112,67,79,0.16)]"
              />
            </label>

            <div className="setup-plum-card rounded-[24px] border p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">Starter Output</p>
              <p className="mt-3 text-[15px] leading-7 text-slate-700">
                DevHub will infer the description and generate a working starter from your idea.
              </p>
            </div>
          </div>

          <div className="mt-6">
            <p className="text-[15px] font-semibold text-slate-800">Tech Stack</p>
            <p className="mt-2 text-[15px] leading-7 text-slate-700">Pick the stack if you know it, or leave it minimal and DevHub will infer the rest.</p>
            {renderStackSelector()}
          </div>
        </section>
      </div>
    );
  };

  return (
    <div className="devhub-dashboard min-h-[var(--app-vh)] bg-[linear-gradient(180deg,#ffffff_0%,#ffffff_74%,rgba(140,84,98,0.035)_100%)] text-slate-900">
      <ToastStack
        items={[
          ...(error ? [{ id: 'dashboard-error', type: 'error' as const, text: error }] : []),
          ...(success ? [{ id: 'dashboard-success', type: 'success' as const, text: success }] : []),
        ]}
        onDismiss={(toastId) => {
          if (toastId === 'dashboard-error') setError('');
          if (toastId === 'dashboard-success') setSuccess('');
        }}
      />
      <div className="mx-auto flex min-h-[var(--app-vh)] max-w-[1680px] flex-col px-6 py-8 lg:px-10">
        <header className="setup-plum-surface rounded-[28px] border px-7 py-6">
          <div className="flex flex-col gap-8 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <p className="text-xs font-semibold uppercase tracking-[0.36em] text-slate-400">DevHub</p>
              <h1 className="mt-3 text-4xl font-semibold tracking-tight text-slate-950">
                Create, import, or connect projects without the messy setup.
              </h1>
              <p className="mt-4 text-base leading-8 text-slate-600">
                Start from an idea, import an existing repository, or attach a local folder. DevHub keeps blueprint, features, pipeline, onboarding, and workspace tied to the same project source.
              </p>
            </div>

            <div className="flex w-full max-w-[420px] items-stretch">
              <button
                type="button"
                onClick={() => openCreateModal()}
                className="smooth-hover-lift group w-full rounded-[26px] border border-slate-950/10 bg-[linear-gradient(145deg,#111827,#70434f)] p-6 text-left text-white shadow-[0_24px_60px_rgba(112,67,79,0.16),0_12px_28px_rgba(15,23,42,0.1)] hover:-translate-y-1.5 hover:shadow-[0_30px_72px_rgba(112,67,79,0.2),0_16px_34px_rgba(15,23,42,0.12)]"
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="rounded-[16px] bg-white p-3 text-slate-950 shadow-[0_12px_24px_rgba(15,23,42,0.16)]">
                    <Plus className="h-5 w-5" />
                  </div>
                  <ArrowRight className="h-5 w-5 text-slate-300 transition duration-300 group-hover:translate-x-1 group-hover:text-white" />
                </div>
                <h2 className="mt-8 text-[clamp(1.45rem,2vw,2rem)] font-semibold tracking-tight">New Project</h2>
                <p className="mt-3 text-sm leading-7 text-slate-300">
                  Start fresh, import GitHub, connect private repos, or attach a local folder from one clean setup flow.
                </p>
                <div className="mt-6 inline-flex items-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-semibold text-slate-950 shadow-[0_10px_20px_rgba(15,23,42,0.16)]">
                  Open Setup
                  <ArrowRight className="h-4 w-4 transition duration-300 group-hover:translate-x-1" />
                </div>
              </button>
            </div>
          </div>
        </header>

        <section className="mt-8 grid gap-6 xl:grid-cols-[minmax(0,1fr)_21rem]">
          <div className="setup-plum-surface rounded-[28px] border p-6">
            <div className="flex flex-col gap-4 border-b border-slate-100 pb-5 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Projects</p>
                <h2 className="mt-2 text-2xl font-semibold text-slate-950">Your workspaces</h2>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <AppSettingsButton />
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
                  onClick={() => openCreateModal()}
                  className="inline-flex items-center justify-center gap-2 rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white shadow-[0_18px_32px_rgba(15,23,42,0.18)] transition hover:-translate-y-0.5"
                >
                  <Plus className="h-4 w-4" />
                  New Project
                </button>
              </div>
            </div>

            {loading ? (
              <div className="setup-plum-card mt-8 flex items-center gap-3 rounded-[24px] border px-5 py-6 text-sm text-slate-500">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading projects...
              </div>
            ) : projects.length === 0 ? (
              <div className="setup-plum-card mt-8 rounded-[24px] border border-dashed p-10 text-center">
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
              <div className="mt-8 grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
                {projects.map((project) => {
                  const busy = isBusyProject(project);
                  const failed = project.scaffold_progress?.status === 'failed';
                  const task = currentScaffoldTask(project.scaffold_progress);
                  const progressPct = Math.max(0, Math.min(100, Number(project.scaffold_progress?.progress_pct || (busy ? 8 : 100))));
                  return (
                  <article
                    key={project.id}
                    className={`setup-plum-card overflow-hidden rounded-[24px] border p-4 transition hover:-translate-y-1 hover:shadow-[0_26px_54px_rgba(112,67,79,0.12),0_14px_30px_rgba(15,23,42,0.06)] ${busy ? 'border-amber-200 shadow-[0_22px_50px_rgba(245,158,11,0.12)]' : ''}`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-500">
                            {getSourceLabel((project.source_type as SourceType) || 'starter')}
                          </span>
                          <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
                            failed
                              ? 'bg-rose-50 text-rose-700'
                              : busy
                                ? 'bg-amber-50 text-amber-700'
                                : 'bg-emerald-50 text-emerald-700'
                          }`}>
                            {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : failed ? <X className="h-3 w-3" /> : <CheckCircle2 className="h-3 w-3" />}
                            {projectStatusLabel(project)}
                          </span>
                        </div>
                        <h3 className="mt-3 break-words text-lg font-semibold text-slate-950">{project.name}</h3>
                        <p className="mt-2 line-clamp-2 break-words text-sm leading-6 text-slate-500">
                          {project.description || 'Workspace ready for blueprint, pipeline, and implementation.'}
                        </p>
                        {busy ? (
                          <div className="mt-4 rounded-2xl border border-amber-100 bg-amber-50/60 p-3">
                            <div className="flex items-center justify-between gap-3 text-xs">
                              <span className="min-w-0 truncate font-semibold text-amber-800">
                                {project.scaffold_progress?.message || (isScaffoldingProject(project) ? 'Generating starter project...' : 'Preparing workspace context...')}
                              </span>
                              <span className="shrink-0 font-mono text-amber-700">{progressPct}%</span>
                            </div>
                            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white">
                              <div className="h-full rounded-full bg-amber-500 transition-all duration-500" style={{ width: `${progressPct}%` }} />
                            </div>
                            <div className="mt-2 flex items-center gap-2 text-[11px] font-medium text-amber-700">
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              <span className="truncate">{task?.label || 'Working through setup steps'}</span>
                            </div>
                          </div>
                        ) : null}
                      </div>

                      <button
                        type="button"
                        onClick={() => deleteProject(project.id)}
                        disabled={deletingId === project.id}
                        className="rounded-2xl border border-rose-200 bg-white p-2 text-rose-500 transition hover:bg-rose-50 disabled:opacity-60"
                        aria-label={`Delete ${project.name}`}
                      >
                        {deletingId === project.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                      </button>
                    </div>

                    <div className="mt-4 flex flex-wrap gap-2">
                      {(project.tech_stack || []).slice(0, 3).map((stack) => (
                        <span key={stack} className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600">
                          {stack}
                        </span>
                      ))}
                      {(project.tech_stack || []).length > 3 ? (
                        <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-500">
                          +{(project.tech_stack || []).length - 3} more
                        </span>
                      ) : null}
                    </div>

                    <div className="mt-4 flex items-center justify-between gap-4">
                      <div className="min-w-0 flex-1 overflow-hidden">
                        <span className="block truncate text-xs text-slate-400">{getProjectLocation(project)}</span>
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
                  );
                })}
              </div>
            )}
          </div>

          <aside className="grid gap-5">
            <div className="setup-plum-surface rounded-[24px] border p-6">
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">How it connects</p>
              <h3 className="mt-3 text-xl font-semibold text-slate-950">One project, one shared system.</h3>
              <ul className="mt-5 space-y-4 text-sm leading-7 text-slate-600">
                <li>Blueprint captures intent and architecture from the same project source.</li>
                <li>Features and pipeline track implementation work against that shared blueprint.</li>
                <li>Workspace and chat operate on the same codebase and runtime, not a disconnected copy.</li>
              </ul>
            </div>

            <div className="setup-plum-surface rounded-[24px] border p-6">
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Recommended first step</p>
              <h3 className="mt-3 text-xl font-semibold text-slate-950">Use the right setup path.</h3>
              <p className="mt-3 text-sm leading-7 text-slate-600">
                New product? Use <span className="font-semibold text-slate-900">Start Fresh</span>. Public repo URL? Use <span className="font-semibold text-slate-900">Import GitHub</span>. Private or account-backed repo? Use <span className="font-semibold text-slate-900">Connect GitHub</span>. Existing local codebase? Use <span className="font-semibold text-slate-900">Open Folder</span>.
              </p>
            </div>
          </aside>
        </section>
      </div>

      {showAiSettings ? (
        <div className="setup-plum-overlay smooth-overlay-enter fixed inset-0 z-[55] flex items-center justify-center px-4 py-4">
          <div className="setup-plum-modal smooth-panel-enter max-h-[calc(var(--app-vh)-2rem)] w-full max-w-3xl overflow-y-auto rounded-[28px] border">
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
                className="setup-plum-button smooth-hover-lift rounded-2xl border p-2 text-slate-500 hover:-translate-y-0.5 hover:text-slate-900"
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
                      placeholder="noted-computing-459609-n2"
                      className="h-11 w-full rounded-2xl border border-slate-200 bg-white px-4 text-sm text-slate-700 outline-none transition focus:border-slate-400"
                    />
                  </div>
                  <div>
                    <label className="mb-2 block text-sm font-medium text-slate-700">Vertex Location</label>
                    <input
                      type="text"
                      value={aiConfig.vertex_location}
                      onChange={(event) => updateAiConfig({ vertex_location: event.target.value })}
                      placeholder="global"
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
        <div className="setup-plum-overlay smooth-overlay-enter fixed inset-0 z-50 flex items-start justify-center px-4 py-4 lg:items-center">
          <div data-create-modal-surface="true" className={`setup-plum-modal smooth-panel-enter font-sans flex max-h-[calc(var(--app-vh)-2rem)] w-full flex-col overflow-hidden rounded-[22px] border ${createStep === 'source' ? 'max-w-[1280px]' : 'max-w-[1540px]'}`}>
            <div className={`flex items-start justify-between gap-4 border-b border-slate-950/6 transition-all duration-500 ${createHeaderCompact ? 'px-6 py-3 lg:px-8 lg:py-3.5' : 'px-6 py-6 lg:px-8 lg:py-7'}`}>
              <div>
                <p className={`text-xs font-semibold uppercase tracking-[0.32em] text-slate-400 transition-all duration-500 ${createHeaderCompact ? 'opacity-80' : ''}`}>Project Setup</p>
                <h2 className={`font-display-serif font-semibold tracking-tight text-slate-950 transition-all duration-500 ${createHeaderCompact ? 'mt-1 text-lg lg:text-xl' : 'mt-3 text-2xl lg:text-3xl'}`}>
                  {createStep === 'source' ? 'Choose how you want to start' : 'Create a project the clean way'}
                </h2>
                {createStep !== 'source' ? (
                  <button
                    type="button"
                    onClick={() => setCreateStep('source')}
                    className={`setup-plum-button smooth-hover-lift inline-flex items-center gap-2 rounded-[10px] border px-4 text-sm font-semibold text-slate-700 transition-all duration-500 hover:-translate-y-0.5 ${
                      createHeaderCompact ? 'mt-2 py-1.5 opacity-0 pointer-events-none h-0 overflow-hidden border-transparent px-0' : 'mt-4 py-2 opacity-100'
                    }`}
                  >
                    <ChevronLeft className="h-4 w-4" />
                    Back To Source Picker
                  </button>
                ) : null}
              </div>
              <div className="flex items-center gap-3">
                {createStep !== 'source' ? (
                  <button
                    type="button"
                    onClick={() => setCreateStep('source')}
                    className="setup-plum-button smooth-hover-lift inline-flex items-center gap-2 rounded-[10px] border px-4 py-2 text-sm font-semibold text-slate-700 hover:-translate-y-0.5 lg:hidden"
                  >
                    <ChevronLeft className="h-4 w-4" />
                    Sources
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={closeCreateModal}
                  className="setup-plum-button smooth-hover-lift rounded-[10px] border p-2 text-slate-500 hover:-translate-y-0.5 hover:text-slate-900"
                  aria-label="Close project setup"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>

            <div
              ref={createBodyRef}
              onScroll={(event) => setCreateHeaderCompact(event.currentTarget.scrollTop > 40)}
              className="min-h-0 flex-1 overflow-y-auto scroll-smooth"
            >
              {createStep === 'source' ? (
                <div key="create-step-source" className="smooth-step-enter px-6 py-6 lg:px-8 lg:py-8">
                  <div className="setup-plum-surface rounded-[16px] border px-6 py-5">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                      <div>
                        <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-400">Choose Source</p>
                        <p className="mt-2 text-[15px] leading-8 text-slate-700">
                          Pick a starting point and DevHub will open the deeper setup flow for that source.
                        </p>
                      </div>
                      <div className="setup-plum-chip inline-flex items-center gap-2 self-start rounded-[10px] border px-4 py-2 text-[14px] font-semibold text-slate-700">
                        4 ways to begin
                      </div>
                    </div>
                  </div>
                  <div className="mt-7 grid gap-5 md:grid-cols-2 xl:grid-cols-4">
                    {SOURCE_OPTIONS.map((option, index) => {
                      const Icon = getSourceIcon(option.id);
                      return (
                        <button
                          key={option.id}
                          type="button"
                          onClick={() => beginCreateSetup(option.id)}
                          className="setup-plum-card smooth-card-enter smooth-hover-lift group relative flex min-h-[276px] flex-col overflow-hidden rounded-[16px] border p-6 text-left hover:-translate-y-1.5 hover:shadow-[0_30px_58px_rgba(112,67,79,0.14)]"
                          style={{ animationDelay: `${index * 55}ms` }}
                        >
                          <div className="flex items-start justify-between gap-4">
                            <div className="setup-plum-chip rounded-[10px] border p-3 text-slate-900 transition duration-300 group-hover:scale-105 group-hover:shadow-[0_18px_30px_rgba(112,67,79,0.12)]">
                              <Icon className="h-5 w-5" />
                            </div>
                            <div className="setup-plum-chip rounded-[10px] border p-2 text-slate-400 transition duration-300 group-hover:text-slate-900 group-hover:translate-x-1">
                              <ArrowRight className="h-4 w-4" />
                            </div>
                          </div>
                          <h3 className="font-display-serif mt-7 text-[1.55rem] font-semibold tracking-tight text-slate-950">{option.title}</h3>
                          <p className="mt-2 text-[15px] font-semibold leading-7 text-slate-800">{option.eyebrow}</p>
                          <p className="mt-4 text-[15px] leading-8 text-slate-700">{option.summary}</p>
                          <div className="mt-auto pt-6">
                            <div className="flex items-center justify-between">
                              <span className="rounded-[8px] bg-slate-100 px-3 py-1.5 text-[12px] font-semibold uppercase tracking-[0.18em] text-slate-600">
                              {option.id === 'github_connect' ? 'Private Friendly' : option.id === 'starter' ? 'Scaffold' : option.id === 'github' ? 'Import' : 'Local'}
                              </span>
                              <span className="text-[15px] font-semibold text-slate-950 transition duration-300 group-hover:translate-x-1">
                                Continue
                              </span>
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div key={`create-step-details-${sourceType}`} className="smooth-step-enter px-5 py-5 lg:px-7 lg:py-7">
                  {sourceType === 'github_connect' ? (
                    <div className="grid gap-6 xl:grid-cols-[240px_minmax(0,1fr)]">
                      <div>{renderFlowSidebar()}</div>
                      <div>
                        <div className="setup-plum-surface flex items-center justify-between gap-3 rounded-[12px] border px-5 py-4">
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">Selected Source</p>
                            <p className="mt-1 text-[15px] font-semibold text-slate-950">{getSourceLabel(sourceType)}</p>
                            <p className="mt-1 text-[15px] leading-7 text-slate-700">You can switch back and choose another setup path at any time.</p>
                          </div>
                          <button
                            type="button"
                            onClick={() => setCreateStep('source')}
                            className="setup-plum-button smooth-hover-lift rounded-[10px] border px-4 py-2 text-[15px] font-semibold text-slate-700 hover:-translate-y-0.5"
                          >
                            Change Source
                          </button>
                        </div>

                        <div className="mt-5">
                          {renderSourceFields()}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <>
                      {renderFlowStrip()}

                      <div className="setup-plum-surface mt-6 flex items-center justify-between gap-3 rounded-[24px] border px-5 py-4">
                        <div>
                          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">Selected Source</p>
                          <p className="mt-1 text-[15px] font-semibold text-slate-950">{getSourceLabel(sourceType)}</p>
                          <p className="mt-1 text-[15px] leading-7 text-slate-700">You can switch back and choose another setup path at any time.</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => setCreateStep('source')}
                          className="setup-plum-button smooth-hover-lift rounded-full border px-4 py-2 text-[15px] font-semibold text-slate-700 hover:-translate-y-0.5"
                        >
                          Change Source
                        </button>
                      </div>

                      <div className="mt-6">
                        {renderSourceFields()}
                      </div>
                    </>
                  )}

                  <div className="mt-7 flex flex-col gap-3 border-t border-slate-100 pt-6 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-[15px] leading-7 text-slate-700">
                      {sourceType === 'starter'
                        ? 'A managed project folder and a working starter app will be created from your input.'
                        : sourceType === 'github'
                          ? inspection
                            ? 'Repository detected. Import will clone it into a managed DevHub workspace.'
                            : 'Paste a valid repository URL and DevHub will detect the project details automatically.'
                          : sourceType === 'github_connect'
                            ? inspection
                              ? 'Connected repository detected. Import will clone it with linked GitHub access and keep repo metadata connected.'
                              : 'Connect GitHub and select a repository to detect the project details automatically.'
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
                            : sourceType === 'github_connect'
                              ? 'Import Connected GitHub Project'
                              : 'Connect Folder Project'}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
