import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  CheckCircle2,
  Copy,
  ExternalLink,
  Github,
  Loader2,
  Lock,
  RefreshCw,
  Search,
  ShieldCheck,
  Unplug,
} from 'lucide-react';

type GitHubConnectSelection = {
  github_connection_id: number | null;
  github_repository_full_name: string;
  github_url?: string;
};

type Props = {
  apiBase: string;
  idea: string;
  inspecting: boolean;
  onInspection: (data: any) => void;
  onSelectionChange: (selection: GitHubConnectSelection) => void;
  onError: (message: string) => void;
};

type GitHubSettings = {
  configured: boolean;
  app_name?: string;
  scopes?: string;
  callback_url?: string;
  create_oauth_app_url?: string;
  developer_settings_url?: string;
};

type GitHubConnection = {
  id: number;
  login: string;
  name?: string;
  avatar_url?: string;
  profile_url?: string;
  token_scope?: string;
};

type GitHubRepository = {
  connection_id?: number | null;
  repository_id?: number | null;
  owner_login?: string;
  repository_name?: string;
  full_name: string;
  default_branch?: string;
  html_url?: string;
  clone_url?: string;
  description?: string;
  language?: string;
  visibility?: string;
  homepage?: string;
  topics?: string[];
  private?: boolean;
  archived?: boolean;
  fork?: boolean;
  stargazers_count?: number;
  watchers_count?: number;
  forks_count?: number;
  updated_at?: string;
  pushed_at?: string;
  permissions?: Record<string, boolean>;
  open_issues_count?: number;
};

type HoverAnchorRect = {
  left: number;
  top: number;
  width: number;
  height: number;
};

type HoverCardPosition = {
  left: number;
  top: number;
  width: number;
  maxHeight: number;
};

const compactNumberFormatter = new Intl.NumberFormat('en', {
  notation: 'compact',
  maximumFractionDigits: 1,
});

function formatCompactNumber(value?: number | null) {
  if (typeof value !== 'number' || Number.isNaN(value)) return null;
  return compactNumberFormatter.format(value);
}

function formatRepositoryDate(value?: string) {
  if (!value) return 'No recent activity data';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'No recent activity data';
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function getPermissionLabel(repository: GitHubRepository) {
  const permissions = repository.permissions || {};
  if (permissions.admin) return 'Admin access';
  if (permissions.maintain) return 'Maintain access';
  if (permissions.push) return 'Write access';
  if (permissions.pull) return 'Read access';
  return 'Access inherited';
}

function getRepositoryVisibilityClasses(repository: GitHubRepository, isSelected: boolean) {
  if (repository.private) {
    return isSelected
      ? 'border border-rose-300/90 bg-rose-50 text-rose-900 shadow-[0_8px_18px_rgba(244,63,94,0.06)]'
      : 'border border-rose-200/90 bg-rose-50/80 text-rose-800 shadow-[0_6px_14px_rgba(244,63,94,0.04)]';
  }
  return isSelected
    ? 'border border-emerald-300/90 bg-emerald-50 text-emerald-900 shadow-[0_8px_18px_rgba(16,185,129,0.06)]'
    : 'border border-emerald-200/90 bg-emerald-50/80 text-emerald-800 shadow-[0_6px_14px_rgba(16,185,129,0.04)]';
}

function getRepositoryOwnershipClasses(isSharedRepo: boolean, isSelected: boolean) {
  if (isSharedRepo) {
    return isSelected
      ? 'border border-sky-300/90 bg-sky-50 text-sky-900 shadow-[0_8px_18px_rgba(14,165,233,0.06)]'
      : 'border border-sky-200/90 bg-sky-50/80 text-sky-800 shadow-[0_6px_14px_rgba(14,165,233,0.04)]';
  }
  return isSelected
    ? 'border border-amber-300/90 bg-amber-50 text-amber-900 shadow-[0_8px_18px_rgba(245,158,11,0.06)]'
    : 'border border-amber-200/90 bg-amber-50/80 text-amber-800 shadow-[0_6px_14px_rgba(245,158,11,0.04)]';
}

function getNeutralMetaChipClasses() {
  return 'setup-plum-chip border text-slate-950';
}

export default function GitHubConnectPanel({
  apiBase,
  idea,
  inspecting,
  onInspection,
  onSelectionChange,
  onError,
}: Props) {
  const repositoryScrollRef = useRef<HTMLDivElement | null>(null);
  const hoverCardRef = useRef<HTMLDivElement | null>(null);
  const [settings, setSettings] = useState<GitHubSettings | null>(null);
  const [connection, setConnection] = useState<GitHubConnection | null>(null);
  const [repositories, setRepositories] = useState<GitHubRepository[]>([]);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [loadingRepositories, setLoadingRepositories] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [savingSetup, setSavingSetup] = useState(false);
  const [resettingSetup, setResettingSetup] = useState(false);
  const [copiedCallback, setCopiedCallback] = useState(false);
  const [selectedRepository, setSelectedRepository] = useState('');
  const [inspectedRepository, setInspectedRepository] = useState('');
  const [hoveredRepository, setHoveredRepository] = useState('');
  const [hoverAnchorRect, setHoverAnchorRect] = useState<HoverAnchorRect | null>(null);
  const [hoverCardPosition, setHoverCardPosition] = useState<HoverCardPosition>({
    left: 12,
    top: 12,
    width: 300,
    maxHeight: 320,
  });
  const [repositoryQuery, setRepositoryQuery] = useState('');
  const [setupForm, setSetupForm] = useState({
    client_id: '',
    client_secret: '',
    app_name: 'DevHub',
    scopes: 'repo read:org',
  });

  const loadStatus = async () => {
    setLoadingStatus(true);
    try {
      const response = await fetch(`${apiBase}/integrations/github/`);
      const data = await response.json();
      if (!response.ok) {
        onError(data.error || 'Could not load GitHub connection status.');
        return;
      }
      const nextSettings = data.github || null;
      setSettings(nextSettings);
      setConnection(data.connection || null);
      setSetupForm((current) => ({
        client_id: current.client_id,
        client_secret: current.client_secret,
        app_name: nextSettings?.app_name || current.app_name,
        scopes: nextSettings?.scopes || current.scopes,
      }));
    } catch {
      onError('Could not load GitHub connection status.');
    } finally {
      setLoadingStatus(false);
    }
  };

  const loadRepositories = async () => {
    if (!connection?.id) return;
    setLoadingRepositories(true);
    try {
      const response = await fetch(`${apiBase}/integrations/github/repositories/`);
      const data = await response.json();
      if (!response.ok) {
        onError(data.error || 'Could not load GitHub repositories.');
        return;
      }
      setConnection(data.connection || connection);
      const nextRepositories: GitHubRepository[] = Array.isArray(data.repositories) ? data.repositories : [];
      setRepositories(nextRepositories);
      if (selectedRepository && !nextRepositories.some((repository: GitHubRepository) => repository.full_name === selectedRepository)) {
        setSelectedRepository('');
        setInspectedRepository('');
        onSelectionChange({ github_connection_id: connection.id, github_repository_full_name: '', github_url: '' });
      }
      if (hoveredRepository && !nextRepositories.some((repository: GitHubRepository) => repository.full_name === hoveredRepository)) {
        setHoveredRepository('');
      }
    } catch {
      onError('Could not load GitHub repositories.');
    } finally {
      setLoadingRepositories(false);
    }
  };

  const connectGitHub = () => {
    const returnTo = `${window.location.origin}/?create=1&source=github_connect`;
    window.location.href = `${apiBase}/integrations/github/connect/?return_to=${encodeURIComponent(returnTo)}`;
  };

  const positionHoverCard = (anchorRect: HoverAnchorRect, measuredHeight?: number, measuredWidth?: number) => {
    const gap = 12;
    const modalBounds = document.querySelector('[data-create-modal-surface="true"]')?.getBoundingClientRect();
    const boundsLeft = modalBounds?.left ?? 0;
    const boundsTop = modalBounds?.top ?? 0;
    const boundsRight = modalBounds?.right ?? window.innerWidth;
    const boundsBottom = modalBounds?.bottom ?? window.innerHeight;
    const boundsWidth = boundsRight - boundsLeft;
    const boundsHeight = boundsBottom - boundsTop;
    const maxHeight = Math.max(220, boundsHeight - 24);
    const width = Math.min(measuredWidth ?? 300, Math.max(260, boundsWidth - 24));
    const height = Math.min(measuredHeight ?? 300, maxHeight);
    const minLeft = boundsLeft + gap;
    const maxLeft = Math.max(minLeft, boundsRight - width - gap);
    const anchorRight = anchorRect.left + anchorRect.width;
    const spaceOnRight = boundsRight - anchorRight - gap;
    const spaceOnLeft = anchorRect.left - boundsLeft - gap;
    const preferredLeft =
      spaceOnRight >= width
        ? anchorRight + gap
        : spaceOnLeft >= width
          ? anchorRect.left - width - gap
          : anchorRect.left + (anchorRect.width - width) / 2;
    const left = Math.min(Math.max(preferredLeft, minLeft), maxLeft);

    const minTop = boundsTop + gap;
    const maxTop = Math.max(minTop, boundsBottom - height - gap);
    const alignedTop = anchorRect.top;
    const belowTop = anchorRect.top + anchorRect.height + gap;
    const aboveTop = anchorRect.top - height - gap;
    const preferredTop =
      spaceOnRight >= width || spaceOnLeft >= width
        ? alignedTop
        : belowTop <= maxTop || aboveTop < minTop
          ? belowTop
          : aboveTop;
    const top = Math.min(Math.max(preferredTop, minTop), maxTop);

    setHoverCardPosition({ left, top, width, maxHeight });
  };

  const handleRepositoryHover = (repositoryName: string, target: HTMLElement) => {
    const targetRect = target.getBoundingClientRect();
    const nextAnchorRect = {
      left: targetRect.left,
      top: targetRect.top,
      width: targetRect.width,
      height: targetRect.height,
    };
    setHoveredRepository(repositoryName);
    setHoverAnchorRect(nextAnchorRect);
    positionHoverCard(nextAnchorRect);
  };

  const clearRepositoryHover = (repositoryName: string) => {
    setHoveredRepository((current) => (current === repositoryName ? '' : current));
    setHoverAnchorRect(null);
  };

  const disconnectGitHub = async () => {
    setDisconnecting(true);
    try {
      const response = await fetch(`${apiBase}/integrations/github/disconnect/`, { method: 'POST' });
      const data = await response.json();
      if (!response.ok) {
        onError(data.error || 'Could not disconnect GitHub.');
        return;
      }
      setConnection(null);
      setRepositories([]);
      setSelectedRepository('');
      setInspectedRepository('');
      setHoveredRepository('');
      setRepositoryQuery('');
      onSelectionChange({ github_connection_id: null, github_repository_full_name: '', github_url: '' });
    } catch {
      onError('Could not disconnect GitHub.');
    } finally {
      setDisconnecting(false);
    }
  };

  const saveSetup = async () => {
    setSavingSetup(true);
    try {
      const response = await fetch(`${apiBase}/integrations/github/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          github: {
            client_id: setupForm.client_id.trim(),
            client_secret: setupForm.client_secret.trim(),
            app_name: setupForm.app_name.trim(),
            scopes: setupForm.scopes.trim(),
          },
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        onError(data.error || 'Could not save GitHub OAuth setup.');
        return;
      }
      setSettings(data.github || null);
      setSetupForm((current) => ({ ...current, client_secret: '' }));
    } catch {
      onError('Could not save GitHub OAuth setup.');
    } finally {
      setSavingSetup(false);
    }
  };

  const resetSetup = async () => {
    setResettingSetup(true);
    try {
      const response = await fetch(`${apiBase}/integrations/github/`, { method: 'DELETE' });
      const data = await response.json();
      if (!response.ok) {
        onError(data.error || 'Could not reset GitHub OAuth setup.');
        return;
      }
      setSettings(data.github || null);
      setConnection(null);
      setRepositories([]);
      setSelectedRepository('');
      setInspectedRepository('');
      setHoveredRepository('');
      setRepositoryQuery('');
      setSetupForm({
        client_id: '',
        client_secret: '',
        app_name: 'DevHub',
        scopes: 'repo read:org',
      });
      onSelectionChange({ github_connection_id: null, github_repository_full_name: '', github_url: '' });
    } catch {
      onError('Could not reset GitHub OAuth setup.');
    } finally {
      setResettingSetup(false);
    }
  };

  const copyCallbackUrl = async () => {
    if (!settings?.callback_url) return;
    try {
      await navigator.clipboard.writeText(settings.callback_url);
      setCopiedCallback(true);
      window.setTimeout(() => setCopiedCallback(false), 1800);
    } catch {
      onError('Could not copy the callback URL.');
    }
  };

  const inspectRepository = async (fullName: string) => {
    if (!connection?.id || !fullName) return;
    try {
      const response = await fetch(`${apiBase}/projects/import/github-connect/inspect/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          github_connection_id: connection.id,
          github_repository_full_name: fullName,
          idea: idea.trim(),
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        onError(data.error || 'Could not inspect the selected GitHub repository.');
        return;
      }
      onInspection(data);
      setInspectedRepository(fullName);
    } catch {
      onError('Could not inspect the selected GitHub repository.');
    }
  };

  useEffect(() => {
    void loadStatus();
  }, []);

  useEffect(() => {
    if (!connection?.id) return;
    void loadRepositories();
  }, [connection?.id]);

  useEffect(() => {
    if (!connection?.id) {
      onSelectionChange({ github_connection_id: null, github_repository_full_name: '', github_url: '' });
      return;
    }
    if (!selectedRepository) {
      onSelectionChange({
        github_connection_id: connection.id,
        github_repository_full_name: '',
        github_url: '',
      });
    }
  }, [connection?.id, selectedRepository]);

  useEffect(() => {
    if (!selectedRepository) return;
    setInspectedRepository('');
    const repository = repositories.find((item) => item.full_name === selectedRepository);
    onSelectionChange({
      github_connection_id: connection?.id ?? null,
      github_repository_full_name: selectedRepository,
      github_url: repository?.html_url || '',
    });
    void inspectRepository(selectedRepository);
  }, [selectedRepository]);

  useEffect(() => {
    if (!hoveredRepository || !hoverAnchorRect || !hoverCardRef.current) return;
    positionHoverCard(
      hoverAnchorRect,
      hoverCardRef.current.offsetHeight,
      hoverCardRef.current.offsetWidth,
    );
  }, [hoveredRepository, hoverAnchorRect]);

  const normalizedRepositoryQuery = repositoryQuery.trim().toLowerCase();
  const filteredRepositories = repositories.filter((repository) => {
    if (!normalizedRepositoryQuery) return true;
    const searchableParts = [
      repository.full_name,
      repository.owner_login,
      repository.repository_name,
      repository.description,
      repository.language,
      repository.visibility,
      ...(repository.topics || []),
    ];
    return searchableParts
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(normalizedRepositoryQuery));
  });
  const hoveredRepositoryData = filteredRepositories.find((repository) => repository.full_name === hoveredRepository);
  const hoveredRepositoryIsShared = Boolean(
    hoveredRepositoryData && connection?.login && hoveredRepositoryData.owner_login && hoveredRepositoryData.owner_login !== connection.login
  );
  const hoveredRepositoryPermissionLabel = hoveredRepositoryData ? getPermissionLabel(hoveredRepositoryData) : '';
  const hoveredRepositoryStarCount = formatCompactNumber(hoveredRepositoryData?.stargazers_count);
  const hoveredRepositoryForkCount = formatCompactNumber(hoveredRepositoryData?.forks_count);
  const hoveredRepositoryLastActivity = formatRepositoryDate(hoveredRepositoryData?.pushed_at || hoveredRepositoryData?.updated_at);
  const hoveredRepositoryIssueCount =
    hoveredRepositoryData && typeof hoveredRepositoryData.open_issues_count === 'number'
      ? hoveredRepositoryData.open_issues_count.toLocaleString()
      : 'Unknown';
  const hoveredRepositoryOwner = hoveredRepositoryData?.owner_login || connection?.login || 'Unknown owner';
  const shouldUseSidebarLayout = Boolean(connection);
  const hoverRepositoryPopover =
    hoveredRepositoryData && typeof document !== 'undefined'
      ? createPortal(
          <div
            ref={hoverCardRef}
            className="pointer-events-none fixed z-[120] transition-all duration-500"
            style={{
              left: `${hoverCardPosition.left}px`,
              top: `${hoverCardPosition.top}px`,
              width: `${hoverCardPosition.width}px`,
            }}
          >
            <div
              className="setup-plum-card overflow-y-auto rounded-[12px] border p-4 text-slate-950 shadow-[0_28px_58px_rgba(112,67,79,0.12),0_12px_28px_rgba(15,23,42,0.05)]"
              style={{ maxHeight: `${hoverCardPosition.maxHeight}px` }}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[12px] font-semibold uppercase tracking-[0.18em] text-slate-600">Quick repo details</p>
                  <p className="font-display-serif mt-2 text-lg font-semibold leading-5 text-slate-950">{hoveredRepositoryData.full_name}</p>
                  <p className="mt-1 text-[13px] leading-6 text-slate-800">
                    {hoveredRepositoryIsShared ? `Shared with you by ${hoveredRepositoryOwner}` : `Owned by ${hoveredRepositoryOwner}`}
                  </p>
                </div>
                <div className="setup-plum-chip rounded-[8px] border px-3 py-1.5 text-[12px] font-semibold text-slate-950">
                  {hoveredRepositoryPermissionLabel}
                </div>
              </div>

              <div className="mt-3 flex flex-wrap gap-2 text-[13px]">
                <span className={`rounded-[8px] px-3 py-1.5 font-medium ${getRepositoryVisibilityClasses(hoveredRepositoryData, false)}`}>
                  {hoveredRepositoryData.private ? 'Private' : 'Public'}
                </span>
                <span className={`rounded-[8px] px-3 py-1.5 font-medium ${getRepositoryOwnershipClasses(hoveredRepositoryIsShared, false)}`}>
                  {hoveredRepositoryIsShared ? 'Collaborator repo' : 'Owned repo'}
                </span>
                {hoveredRepositoryData.archived ? (
                  <span className="setup-plum-chip rounded-[8px] border px-3 py-1.5 font-medium text-slate-950">Archived</span>
                ) : null}
                {hoveredRepositoryData.fork ? (
                  <span className="setup-plum-chip rounded-[8px] border px-3 py-1.5 font-medium text-slate-950">Fork</span>
                ) : null}
              </div>

              <p className="mt-3 line-clamp-3 text-[15px] leading-7 text-slate-900">
                {hoveredRepositoryData.description || 'No description is available on GitHub for this repository yet.'}
              </p>

              <div className="mt-4 grid grid-cols-2 gap-3">
                <div className="setup-plum-card rounded-[10px] border px-3 py-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-600">Primary language</p>
                  <p className="mt-1 text-[15px] font-semibold text-slate-950">{hoveredRepositoryData.language || 'Not set'}</p>
                </div>
                <div className="setup-plum-card rounded-[10px] border px-3 py-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-600">Default branch</p>
                  <p className="mt-1 text-[15px] font-semibold text-slate-950">{hoveredRepositoryData.default_branch || 'Unknown'}</p>
                </div>
                <div className="setup-plum-card rounded-[10px] border px-3 py-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-600">Stars</p>
                  <p className="mt-1 text-[15px] font-semibold text-slate-950">{hoveredRepositoryStarCount || '0'}</p>
                </div>
                <div className="setup-plum-card rounded-[10px] border px-3 py-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-600">Forks</p>
                  <p className="mt-1 text-[15px] font-semibold text-slate-950">{hoveredRepositoryForkCount || '0'}</p>
                </div>
              </div>

              <div className="setup-plum-card mt-3 flex items-center justify-between gap-3 rounded-[10px] border px-3 py-3 text-[15px] text-slate-950">
                <span>Issues: {hoveredRepositoryIssueCount}</span>
                <span>{hoveredRepositoryLastActivity}</span>
              </div>

              {hoveredRepositoryData.topics?.length ? (
                <div className="mt-4 flex flex-wrap gap-2">
                  {hoveredRepositoryData.topics.slice(0, 3).map((topic) => (
                    <span key={topic} className="setup-plum-chip rounded-[8px] border px-2.5 py-1 text-[12px] font-semibold text-slate-950">
                      {topic}
                    </span>
                  ))}
                </div>
              ) : null}

              <div className="setup-plum-divider mt-4 flex items-center justify-between gap-3 border-t pt-3 text-[13px] text-slate-800">
                <span>{hoveredRepositoryData.homepage ? 'Homepage linked' : 'No homepage linked'}</span>
                <span>{hoveredRepositoryData.html_url ? 'Ready to inspect' : 'Metadata only'}</span>
              </div>
            </div>
          </div>,
          document.body
        )
      : null;
  return (
    <div className={shouldUseSidebarLayout ? 'grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px] xl:items-start' : 'space-y-5'}>
      <section
        className={`setup-plum-surface rounded-[18px] border p-6 ${
          shouldUseSidebarLayout ? 'xl:order-2 xl:sticky xl:top-0' : ''
        }`}
      >
        <div className={`flex flex-col gap-4 ${shouldUseSidebarLayout ? '' : 'md:flex-row md:items-start md:justify-between'}`}>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-400">GitHub Connection</p>
            <h3 className="font-display-serif mt-2 text-[1.8rem] font-semibold leading-none text-slate-900">Connect GitHub in the browser</h3>
            <p className={`mt-2 text-[15px] leading-8 text-slate-800 ${shouldUseSidebarLayout ? '' : 'max-w-2xl'}`}>
              Sign in once, let DevHub read repositories your account can access, and keep issue and pull request data attached to the imported project.
            </p>
          </div>
          <div className={`flex gap-3 ${shouldUseSidebarLayout ? 'flex-col items-stretch' : 'flex-wrap items-center'}`}>
            <button
              type="button"
              onClick={() => void loadStatus()}
              disabled={loadingStatus}
              className={`setup-plum-button inline-flex items-center gap-2 rounded-[10px] border px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:-translate-y-0.5 disabled:opacity-60 ${
                shouldUseSidebarLayout ? 'justify-center' : ''
              }`}
            >
              {loadingStatus ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              Refresh Status
            </button>
            {connection ? (
              <button
                type="button"
                onClick={disconnectGitHub}
                disabled={disconnecting}
                className={`setup-plum-button inline-flex items-center gap-2 rounded-[10px] border px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:-translate-y-0.5 disabled:opacity-60 ${
                  shouldUseSidebarLayout ? 'justify-center' : ''
                }`}
              >
                {disconnecting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Unplug className="h-4 w-4" />}
                Disconnect
              </button>
            ) : (
              <button
                type="button"
                onClick={connectGitHub}
                disabled={!settings?.configured}
                className={`setup-plum-button-strong inline-flex items-center gap-2 rounded-[10px] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60 ${
                  shouldUseSidebarLayout ? 'justify-center' : ''
                }`}
              >
                <Github className="h-4 w-4" />
                Connect GitHub
              </button>
            )}
          </div>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-3 text-[13px]">
          {settings?.configured ? (
            <span className="setup-plum-chip inline-flex items-center gap-2 rounded-[8px] border px-3 py-1.5 font-medium text-slate-950">
              <ShieldCheck className="h-3.5 w-3.5" />
              OAuth credentials are saved locally
            </span>
          ) : (
            <span className="setup-plum-chip rounded-[8px] border px-3 py-1.5 font-medium text-slate-950">
              One-time local setup still needed: add the GitHub OAuth client id and client secret below.
            </span>
          )}
          {settings?.scopes ? (
            <span className="setup-plum-chip rounded-[8px] border px-3 py-1.5 font-medium text-slate-950">
              Scopes: {settings.scopes}
            </span>
          ) : null}
          {settings?.configured && !connection ? (
            <span className="setup-plum-chip rounded-[8px] border px-3 py-1.5 font-medium text-slate-950">
              If you deleted the GitHub OAuth app, reset this setup and create a new one before connecting again.
            </span>
          ) : null}
        </div>

        {!settings?.configured ? (
          <div className="setup-plum-card mt-6 rounded-[16px] border p-5">
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-700/70">One-Time OAuth Setup</p>
                <h4 className="mt-2 text-lg font-semibold text-slate-900">Register one GitHub OAuth app, then every repo import can use browser auth</h4>
                <p className="mt-2 max-w-2xl text-[15px] leading-8 text-slate-700">
                  This is a one-time local server setup, not something each project or repo owner has to repeat. You only need the GitHub OAuth client id and client secret.
                </p>
              </div>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <label className="grid gap-2">
                <span className="text-sm font-medium text-slate-700">GitHub Client ID</span>
                <input
                  value={setupForm.client_id}
                  onChange={(event) => setSetupForm((current) => ({ ...current, client_id: event.target.value }))}
                  placeholder="Ov23li..."
                  className="setup-plum-input w-full rounded-[10px] border px-4 py-3 text-[15px] text-slate-900 outline-none transition focus:border-[rgba(112,67,79,0.18)]"
                />
              </label>
              <label className="grid gap-2">
                <span className="text-sm font-medium text-slate-700">GitHub Client Secret</span>
                <input
                  type="password"
                  value={setupForm.client_secret}
                  onChange={(event) => setSetupForm((current) => ({ ...current, client_secret: event.target.value }))}
                  placeholder="Paste the OAuth app secret"
                  className="setup-plum-input w-full rounded-[10px] border px-4 py-3 text-[15px] text-slate-900 outline-none transition focus:border-[rgba(112,67,79,0.18)]"
                />
              </label>
              <label className="grid gap-2">
                <span className="text-sm font-medium text-slate-700">Display Name</span>
                <input
                  value={setupForm.app_name}
                  onChange={(event) => setSetupForm((current) => ({ ...current, app_name: event.target.value }))}
                  placeholder="DevHub"
                  className="setup-plum-input w-full rounded-[10px] border px-4 py-3 text-[15px] text-slate-900 outline-none transition focus:border-[rgba(112,67,79,0.18)]"
                />
              </label>
              <label className="grid gap-2">
                <span className="text-sm font-medium text-slate-700">Scopes</span>
                <input
                  value={setupForm.scopes}
                  onChange={(event) => setSetupForm((current) => ({ ...current, scopes: event.target.value }))}
                  placeholder="repo read:org"
                  className="setup-plum-input w-full rounded-[10px] border px-4 py-3 text-[15px] text-slate-900 outline-none transition focus:border-[rgba(112,67,79,0.18)]"
                />
              </label>
            </div>

            <div className="setup-plum-card mt-5 rounded-[12px] border px-4 py-4">
              <p className="text-[15px] font-semibold text-slate-900">GitHub OAuth callback URL</p>
              <p className="mt-2 break-all text-[15px] leading-7 text-slate-700">{settings?.callback_url || `${apiBase}/integrations/github/callback/`}</p>
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={copyCallbackUrl}
                  className="setup-plum-button inline-flex items-center gap-2 rounded-[8px] border px-3 py-2 text-sm font-semibold text-slate-700"
                >
                  {copiedCallback ? <CheckCircle2 className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  {copiedCallback ? 'Copied' : 'Copy Callback URL'}
                </button>
                <a
                  href={settings?.create_oauth_app_url || 'https://github.com/settings/applications/new'}
                  target="_blank"
                  rel="noreferrer"
                  className="setup-plum-button inline-flex items-center gap-2 rounded-[8px] border px-3 py-2 text-sm font-semibold text-slate-700"
                >
                  <ExternalLink className="h-4 w-4" />
                  Create OAuth App
                </a>
                <a
                  href={settings?.developer_settings_url || 'https://github.com/settings/developers'}
                  target="_blank"
                  rel="noreferrer"
                  className="setup-plum-button inline-flex items-center gap-2 rounded-[8px] border px-3 py-2 text-sm font-semibold text-slate-700"
                >
                  <ExternalLink className="h-4 w-4" />
                  Open GitHub Developer Settings
                </a>
              </div>
            </div>

            <div className="mt-5 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={saveSetup}
                disabled={savingSetup || !setupForm.client_id.trim() || !setupForm.client_secret.trim()}
                className="setup-plum-button-strong inline-flex items-center gap-2 rounded-[10px] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
              >
                {savingSetup ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
                {savingSetup ? 'Saving...' : 'Save OAuth Setup'}
              </button>
              <p className="text-[15px] leading-7 text-slate-700">
                After saving, click <span className="font-medium text-slate-800">Connect GitHub</span> to start browser auth.
              </p>
            </div>
          </div>
        ) : null}

        {settings?.configured && !connection ? (
          <div className="setup-plum-card mt-6 rounded-[16px] border p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-700/70">Recovery</p>
            <h4 className="mt-2 text-lg font-semibold text-slate-900">Reconnect or recreate the OAuth app</h4>
            <p className="mt-2 max-w-2xl text-[15px] leading-8 text-slate-700">
              Connect GitHub should open GitHub's authorization screen for an existing OAuth app. If it opens a 404 page, the saved client id usually points to a deleted or invalid app.
            </p>
            <div className="mt-5 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={resetSetup}
                disabled={resettingSetup}
                className="setup-plum-button inline-flex items-center gap-2 rounded-[10px] border px-4 py-2 text-sm font-semibold text-rose-700 disabled:opacity-60"
              >
                {resettingSetup ? <Loader2 className="h-4 w-4 animate-spin" /> : <Unplug className="h-4 w-4" />}
                {resettingSetup ? 'Resetting...' : 'Reset GitHub Setup'}
              </button>
              <a
                href={settings?.create_oauth_app_url || 'https://github.com/settings/applications/new'}
                target="_blank"
                rel="noreferrer"
                className="setup-plum-button inline-flex items-center gap-2 rounded-[10px] border px-4 py-2 text-sm font-semibold text-slate-700"
              >
                <ExternalLink className="h-4 w-4" />
                Create OAuth App
              </a>
            </div>
          </div>
        ) : null}

        {connection ? (
          <div className="setup-plum-card mt-6 overflow-hidden rounded-[14px] border">
            <div className={`flex flex-col gap-5 px-5 py-5 ${shouldUseSidebarLayout ? '' : 'lg:flex-row lg:items-center lg:justify-between'}`}>
              <div className="flex items-start gap-4">
                {connection.avatar_url ? (
                  <img
                    src={connection.avatar_url}
                    alt={connection.login}
                    className="setup-plum-chip h-14 w-14 rounded-[10px] border object-cover"
                  />
                ) : (
                  <div className="setup-plum-chip flex h-14 w-14 items-center justify-center rounded-[10px] border text-slate-950">
                    <Github className="h-5 w-5" />
                  </div>
                )}
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-500">Connected Account</p>
                  <p className="mt-2 text-base font-semibold text-slate-950">{connection.name || connection.login}</p>
                  <p className="mt-1 text-[15px] text-slate-800">@{connection.login}</p>
                  <div className="mt-3 flex flex-wrap gap-2 text-[13px]">
                    <span className="setup-plum-chip rounded-[8px] border px-3 py-1.5 font-medium text-slate-950">
                      {repositories.length} repos available
                    </span>
                    <span className="setup-plum-chip rounded-[8px] border px-3 py-1.5 font-medium text-slate-950">
                      Scope: {connection.token_scope || settings?.scopes || 'repo access'}
                    </span>
                  </div>
                </div>
              </div>
              <div className={`flex flex-wrap items-center gap-3 ${shouldUseSidebarLayout ? '' : ''}`}>
                {connection.profile_url ? (
                  <a
                    href={connection.profile_url}
                    target="_blank"
                    rel="noreferrer"
                    className={`setup-plum-button inline-flex items-center gap-2 rounded-[10px] border px-4 py-2.5 text-sm font-semibold text-slate-950 ${
                      shouldUseSidebarLayout ? 'w-full justify-center' : ''
                    }`}
                  >
                    <ExternalLink className="h-4 w-4" />
                    Open Profile
                  </a>
                ) : null}
              </div>
            </div>
          </div>
        ) : null}
      </section>

      <section className={`setup-plum-surface rounded-[18px] border p-6 ${shouldUseSidebarLayout ? 'xl:order-1' : ''}`}>
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-400">Repository Access</p>
            <h3 className="font-display-serif mt-2 text-[1.9rem] font-semibold leading-none text-slate-900">
              {connection ? 'Choose a connected repository' : 'Finish GitHub sign-in first'}
            </h3>
            <p className="mt-2 max-w-2xl text-[15px] leading-8 text-slate-700">
              {connection
                ? 'DevHub lists repositories available to the connected GitHub account and inspects the selected repo before import.'
                : 'OAuth app setup is done, but no GitHub user has completed browser sign-in yet. Click Connect GitHub above, approve access, and then return here to load repos.'}
            </p>
          </div>
          {connection ? null : (
            <button
              type="button"
              onClick={connectGitHub}
              className="inline-flex items-center gap-2 rounded-[10px] bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white shadow-[0_14px_30px_rgba(15,23,42,0.16)]"
            >
              <Github className="h-4 w-4" />
              Connect GitHub
            </button>
          )}
        </div>

        {connection ? (
          <div className="mt-6">
            <div className="setup-plum-card smooth-panel-enter overflow-hidden rounded-[14px] border">
              <div className="setup-plum-divider border-b px-5 py-5">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
                  <div>
                    <p className="font-display-serif text-[1.45rem] font-semibold leading-none text-slate-950">Browse repositories</p>
                    <p className="mt-1 text-[15px] leading-7 text-slate-700">
                      Pick one repository to inspect. Hover shows quick details, selecting keeps it ready for import.
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="setup-plum-chip rounded-[8px] border px-3 py-1.5 text-[13px] font-semibold text-slate-950">
                      {filteredRepositories.length} shown
                    </span>
                    <span className="setup-plum-chip rounded-[8px] border px-3 py-1.5 text-[13px] font-semibold text-slate-950">
                      {selectedRepository ? '1 selected' : 'No repo selected'}
                    </span>
                    <button
                      type="button"
                      onClick={() => void loadRepositories()}
                      disabled={loadingRepositories}
                      className="setup-plum-button inline-flex items-center gap-2 rounded-[10px] border px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:-translate-y-0.5 disabled:opacity-60"
                    >
                      {loadingRepositories ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                      Refresh Repos
                    </button>
                  </div>
                </div>

                <label className="relative mt-4 block">
                  <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                  <input
                    value={repositoryQuery}
                    onChange={(event) => setRepositoryQuery(event.target.value)}
                    placeholder={loadingRepositories ? 'Loading repositories...' : 'Search repo name, owner, language, or topic'}
                    disabled={loadingRepositories}
                    className="setup-plum-input w-full rounded-[10px] border px-11 py-3 text-[15px] text-slate-950 outline-none transition placeholder:text-slate-500 focus:border-[rgba(112,67,79,0.16)] disabled:opacity-60"
                  />
                </label>
              </div>

              <div
                ref={repositoryScrollRef}
                onScroll={() => {
                  setHoveredRepository('');
                  setHoverAnchorRect(null);
                }}
                className="repo-browser-scroll relative max-h-[620px] overflow-y-auto px-4 py-4 scroll-smooth"
              >
                {loadingRepositories ? (
                  <div className="setup-plum-card flex min-h-[220px] items-center justify-center gap-3 rounded-[12px] border border-dashed px-4 py-8 text-sm text-slate-800">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading repositories from GitHub...
                  </div>
                ) : filteredRepositories.length ? (
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {filteredRepositories.map((repository, index) => {
                      const isSelected = repository.full_name === selectedRepository;
                      const isHovered = repository.full_name === hoveredRepository;
                      const showHoverDetails = isHovered;
                      const isSharedRepo = Boolean(connection?.login && repository.owner_login && repository.owner_login !== connection.login);

                      return (
                        <button
                          key={repository.full_name}
                          type="button"
                          onClick={() => setSelectedRepository(repository.full_name)}
                          onMouseEnter={(event) => handleRepositoryHover(repository.full_name, event.currentTarget)}
                          onMouseLeave={() => clearRepositoryHover(repository.full_name)}
                          onFocus={(event) => handleRepositoryHover(repository.full_name, event.currentTarget)}
                          onBlur={() => clearRepositoryHover(repository.full_name)}
                          className={`smooth-card-enter smooth-hover-lift group relative isolate flex min-h-[110px] flex-col rounded-[10px] border px-4 py-3.5 text-left ${
                            showHoverDetails ? 'z-40' : isSelected ? 'z-10' : 'z-0'
                          } ${
                            isSelected
                              ? 'border-slate-950/10 bg-white text-slate-950 shadow-[0_18px_36px_rgba(112,67,79,0.09),0_8px_20px_rgba(15,23,42,0.04)]'
                              : isHovered
                                ? 'border-slate-950/9 bg-white text-slate-950 shadow-[0_16px_30px_rgba(112,67,79,0.07),0_6px_16px_rgba(15,23,42,0.035)]'
                                : 'border-slate-950/6 bg-white text-slate-950 shadow-[0_12px_22px_rgba(112,67,79,0.05),0_4px_12px_rgba(15,23,42,0.025)] hover:border-slate-950/8 hover:bg-white'
                          }`}
                          style={{ animationDelay: `${index * 28}ms` }}
                        >
                          <div className="flex items-start justify-between gap-4">
                            <div className="min-w-0 flex-1 pr-2">
                              <div className="flex flex-wrap items-center gap-2">
                                <p className="font-display-serif line-clamp-2 break-words text-[1.32rem] leading-6 font-semibold text-slate-950">
                                  {repository.full_name}
                                </p>
                              </div>
                              <div className="mt-2 flex flex-wrap items-center gap-2">
                                <span
                                  className={`rounded-[8px] px-2.5 py-1 text-[12px] font-semibold ${getRepositoryVisibilityClasses(repository, isSelected)}`}
                                >
                                  {repository.private ? 'Private' : 'Public'}
                                </span>
                                <span
                                  className={`rounded-[8px] px-2.5 py-1 text-[12px] font-semibold ${getRepositoryOwnershipClasses(isSharedRepo, isSelected)}`}
                                >
                                  {isSharedRepo ? 'Collaborator' : 'Owned'}
                                </span>
                              </div>
                              <div className="mt-2.5 flex flex-wrap items-center gap-2">
                                {repository.language ? (
                                  <span className={`rounded-[8px] px-2.5 py-1 text-[12px] font-semibold ${getNeutralMetaChipClasses()}`}>
                                    {repository.language}
                                  </span>
                                ) : null}
                                {repository.default_branch ? (
                                  <span className={`rounded-[8px] px-2.5 py-1 text-[12px] font-semibold ${getNeutralMetaChipClasses()}`}>
                                    {repository.default_branch}
                                  </span>
                                ) : null}
                              </div>
                            </div>
                            <div className={`setup-plum-chip mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-[8px] border transition ${isSelected ? 'text-slate-950' : 'text-slate-700 group-hover:text-slate-950'}`}>
                              {repository.private ? <Lock className="h-4 w-4" /> : <Github className="h-4 w-4" />}
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <div className="setup-plum-card rounded-[12px] border border-dashed px-4 py-10 text-center text-sm text-slate-800">
                    No repositories match that search yet. Try owner, repo name, language, or a topic.
                  </div>
                )}

              </div>
            </div>
          </div>
        ) : (
          <div className="setup-plum-card mt-6 rounded-2xl border border-dashed px-4 py-6 text-[15px] leading-8 text-slate-700">
            No GitHub account token is connected yet, so DevHub has nothing to list here. After you complete browser sign-in, this section will populate automatically.
          </div>
        )}

        <div className="mt-5 flex flex-wrap items-center gap-3 text-xs text-slate-800">
          <span className="setup-plum-chip inline-flex items-center gap-1.5 rounded-[8px] border px-3 py-1.5">
            <Github className="h-3.5 w-3.5" />
            {connection ? `${repositories.length} repos available to this connection` : 'No connected GitHub account yet'}
          </span>
          {selectedRepository ? (
            <span className="setup-plum-chip inline-flex items-center gap-1.5 rounded-[8px] border px-3 py-1.5 text-slate-950">
              <Loader2 className={`h-3.5 w-3.5 ${inspecting ? 'animate-spin' : ''}`} />
              {inspecting
                ? 'Inspecting selected repo...'
                : inspectedRepository === selectedRepository
                  ? 'Inspection complete'
                  : 'Repo selected'}
            </span>
          ) : null}
        </div>
      </section>
      {hoverRepositoryPopover}
    </div>
  );
}
