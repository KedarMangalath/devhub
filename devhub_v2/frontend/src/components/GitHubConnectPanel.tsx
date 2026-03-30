import { useEffect, useState } from 'react';
import { ExternalLink, Github, Loader2, RefreshCw, ShieldCheck, Unplug } from 'lucide-react';

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
};

type GitHubConnection = {
  id: number;
  login: string;
  name?: string;
  avatar_url?: string;
  profile_url?: string;
  token_scope?: string;
};

export default function GitHubConnectPanel({
  apiBase,
  idea,
  inspecting,
  onInspection,
  onSelectionChange,
  onError,
}: Props) {
  const [settings, setSettings] = useState<GitHubSettings | null>(null);
  const [connection, setConnection] = useState<GitHubConnection | null>(null);
  const [repositories, setRepositories] = useState<any[]>([]);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [loadingRepositories, setLoadingRepositories] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [selectedRepository, setSelectedRepository] = useState('');

  const loadStatus = async () => {
    setLoadingStatus(true);
    try {
      const response = await fetch(`${apiBase}/integrations/github/`);
      const data = await response.json();
      if (!response.ok) {
        onError(data.error || 'Could not load GitHub connection status.');
        return;
      }
      setSettings(data.github || null);
      setConnection(data.connection || null);
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
      setRepositories(Array.isArray(data.repositories) ? data.repositories : []);
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
      onSelectionChange({ github_connection_id: null, github_repository_full_name: '', github_url: '' });
    } catch {
      onError('Could not disconnect GitHub.');
    } finally {
      setDisconnecting(false);
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
      onSelectionChange({
        github_connection_id: connection.id,
        github_repository_full_name: fullName,
        github_url: data.github_url,
      });
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
    if (!selectedRepository) return;
    onSelectionChange({
      github_connection_id: connection?.id ?? null,
      github_repository_full_name: selectedRepository,
    });
    void inspectRepository(selectedRepository);
  }, [selectedRepository]);

  return (
    <div className="space-y-5">
      <section className="rounded-[30px] border border-slate-200/80 bg-white/88 p-6 shadow-[0_24px_60px_rgba(15,23,42,0.08)] backdrop-blur-xl">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-400">GitHub Connection</p>
            <h3 className="mt-2 text-xl font-semibold text-slate-900">Connect GitHub in the browser</h3>
            <p className="mt-2 max-w-2xl text-sm leading-7 text-slate-500">
              Sign in once, let DevHub read repositories your account can access, and keep issue and pull request data attached to the imported project.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => void loadStatus()}
              disabled={loadingStatus}
              className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:-translate-y-0.5 disabled:opacity-60"
            >
              {loadingStatus ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              Refresh Status
            </button>
            {connection ? (
              <button
                type="button"
                onClick={disconnectGitHub}
                disabled={disconnecting}
                className="inline-flex items-center gap-2 rounded-full border border-rose-200 bg-white px-4 py-2 text-sm font-semibold text-rose-700 transition hover:-translate-y-0.5 disabled:opacity-60"
              >
                {disconnecting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Unplug className="h-4 w-4" />}
                Disconnect
              </button>
            ) : (
              <button
                type="button"
                onClick={connectGitHub}
                disabled={!settings?.configured}
                className="inline-flex items-center gap-2 rounded-full bg-slate-950 px-4 py-2 text-sm font-semibold text-white shadow-[0_14px_30px_rgba(15,23,42,0.16)] disabled:opacity-60"
              >
                <Github className="h-4 w-4" />
                Connect GitHub
              </button>
            )}
          </div>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-3 text-xs">
          {settings?.configured ? (
            <span className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1.5 font-medium text-emerald-700">
              <ShieldCheck className="h-3.5 w-3.5" />
              Server OAuth is configured
            </span>
          ) : (
            <span className="rounded-full bg-amber-50 px-3 py-1.5 font-medium text-amber-700">
              Server setup still needed: add GitHub client id and client secret, then reconnect this screen.
            </span>
          )}
          {settings?.scopes ? (
            <span className="rounded-full bg-slate-50 px-3 py-1.5 font-medium text-slate-600">
              Scopes: {settings.scopes}
            </span>
          ) : null}
        </div>

        {connection ? (
          <div className="mt-6 rounded-[26px] border border-slate-200/80 bg-[#fbfcfe] p-5">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div className="flex items-center gap-4">
                {connection.avatar_url ? (
                  <img
                    src={connection.avatar_url}
                    alt={connection.login}
                    className="h-12 w-12 rounded-2xl border border-slate-200 object-cover"
                  />
                ) : (
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-600">
                    <Github className="h-5 w-5" />
                  </div>
                )}
                <div>
                  <p className="text-sm font-semibold text-slate-900">{connection.name || connection.login}</p>
                  <p className="text-sm text-slate-500">@{connection.login}</p>
                </div>
              </div>
              {connection.profile_url ? (
                <a
                  href={connection.profile_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700"
                >
                  <ExternalLink className="h-4 w-4" />
                  Open Profile
                </a>
              ) : null}
            </div>
          </div>
        ) : null}
      </section>

      <section className="rounded-[30px] border border-slate-200/80 bg-white/88 p-6 shadow-[0_24px_60px_rgba(15,23,42,0.08)] backdrop-blur-xl">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-400">Repository Access</p>
            <h3 className="mt-2 text-xl font-semibold text-slate-900">Choose a connected repository</h3>
            <p className="mt-2 max-w-2xl text-sm leading-7 text-slate-500">
              DevHub lists repositories available to the connected GitHub account and inspects the selected repo before import.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void loadRepositories()}
            disabled={!connection || loadingRepositories}
            className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:-translate-y-0.5 disabled:opacity-60"
          >
            {loadingRepositories ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Refresh Repos
          </button>
        </div>

        <div className="mt-6 grid gap-4">
          <label className="grid gap-2">
            <span className="text-sm font-medium text-slate-700">Repository</span>
            <select
              value={selectedRepository}
              onChange={(event) => setSelectedRepository(event.target.value)}
              disabled={!connection || loadingRepositories}
              className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-400 disabled:opacity-60"
            >
              <option value="">{loadingRepositories ? 'Loading repositories...' : 'Select a repository'}</option>
              {repositories.map((repository) => (
                <option key={repository.full_name} value={repository.full_name}>
                  {repository.full_name}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-3 text-xs text-slate-500">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-50 px-3 py-1.5">
            <Github className="h-3.5 w-3.5" />
            {repositories.length} repos available to this connection
          </span>
          {selectedRepository ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1.5 text-emerald-700">
              <Loader2 className={`h-3.5 w-3.5 ${inspecting ? 'animate-spin' : ''}`} />
              {inspecting ? 'Inspecting selected repo...' : 'Repo selected and ready'}
            </span>
          ) : null}
        </div>
      </section>
    </div>
  );
}
