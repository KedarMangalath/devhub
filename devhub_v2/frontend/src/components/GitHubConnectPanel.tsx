import { useEffect, useState } from 'react';
import { CheckCircle2, Copy, ExternalLink, Github, Loader2, RefreshCw, ShieldCheck, Unplug } from 'lucide-react';

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
  const [savingSetup, setSavingSetup] = useState(false);
  const [resettingSetup, setResettingSetup] = useState(false);
  const [copiedCallback, setCopiedCallback] = useState(false);
  const [selectedRepository, setSelectedRepository] = useState('');
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
              OAuth credentials are saved locally
            </span>
          ) : (
            <span className="rounded-full bg-amber-50 px-3 py-1.5 font-medium text-amber-700">
              One-time local setup still needed: add the GitHub OAuth client id and client secret below.
            </span>
          )}
          {settings?.scopes ? (
            <span className="rounded-full bg-slate-50 px-3 py-1.5 font-medium text-slate-600">
              Scopes: {settings.scopes}
            </span>
          ) : null}
          {settings?.configured && !connection ? (
            <span className="rounded-full bg-amber-50 px-3 py-1.5 font-medium text-amber-700">
              If you deleted the GitHub OAuth app, reset this setup and create a new one before connecting again.
            </span>
          ) : null}
        </div>

        {!settings?.configured ? (
          <div className="mt-6 rounded-[26px] border border-amber-200/70 bg-[linear-gradient(180deg,rgba(255,251,235,0.92),rgba(255,255,255,0.96))] p-5">
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-700/70">One-Time OAuth Setup</p>
                <h4 className="mt-2 text-lg font-semibold text-slate-900">Register one GitHub OAuth app, then every repo import can use browser auth</h4>
                <p className="mt-2 max-w-2xl text-sm leading-7 text-slate-600">
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
                  className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-400"
                />
              </label>
              <label className="grid gap-2">
                <span className="text-sm font-medium text-slate-700">GitHub Client Secret</span>
                <input
                  type="password"
                  value={setupForm.client_secret}
                  onChange={(event) => setSetupForm((current) => ({ ...current, client_secret: event.target.value }))}
                  placeholder="Paste the OAuth app secret"
                  className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-400"
                />
              </label>
              <label className="grid gap-2">
                <span className="text-sm font-medium text-slate-700">Display Name</span>
                <input
                  value={setupForm.app_name}
                  onChange={(event) => setSetupForm((current) => ({ ...current, app_name: event.target.value }))}
                  placeholder="DevHub"
                  className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-400"
                />
              </label>
              <label className="grid gap-2">
                <span className="text-sm font-medium text-slate-700">Scopes</span>
                <input
                  value={setupForm.scopes}
                  onChange={(event) => setSetupForm((current) => ({ ...current, scopes: event.target.value }))}
                  placeholder="repo read:org"
                  className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-slate-400"
                />
              </label>
            </div>

            <div className="mt-5 rounded-2xl border border-slate-200 bg-white px-4 py-4">
              <p className="text-sm font-medium text-slate-800">GitHub OAuth callback URL</p>
              <p className="mt-2 break-all text-sm text-slate-600">{settings?.callback_url || `${apiBase}/integrations/github/callback/`}</p>
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={copyCallbackUrl}
                  className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700"
                >
                  {copiedCallback ? <CheckCircle2 className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  {copiedCallback ? 'Copied' : 'Copy Callback URL'}
                </button>
                <a
                  href={settings?.create_oauth_app_url || 'https://github.com/settings/applications/new'}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700"
                >
                  <ExternalLink className="h-4 w-4" />
                  Create OAuth App
                </a>
                <a
                  href={settings?.developer_settings_url || 'https://github.com/settings/developers'}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700"
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
                className="inline-flex items-center gap-2 rounded-full bg-slate-950 px-4 py-2 text-sm font-semibold text-white shadow-[0_14px_30px_rgba(15,23,42,0.16)] disabled:opacity-60"
              >
                {savingSetup ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
                {savingSetup ? 'Saving...' : 'Save OAuth Setup'}
              </button>
              <p className="text-sm text-slate-500">
                After saving, click <span className="font-medium text-slate-800">Connect GitHub</span> to start browser auth.
              </p>
            </div>
          </div>
        ) : null}

        {settings?.configured && !connection ? (
          <div className="mt-6 rounded-[26px] border border-amber-200/70 bg-[linear-gradient(180deg,rgba(255,248,240,0.92),rgba(255,255,255,0.96))] p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-700/70">Recovery</p>
            <h4 className="mt-2 text-lg font-semibold text-slate-900">Reconnect or recreate the OAuth app</h4>
            <p className="mt-2 max-w-2xl text-sm leading-7 text-slate-600">
              Connect GitHub should open GitHub's authorization screen for an existing OAuth app. If it opens a 404 page, the saved client id usually points to a deleted or invalid app.
            </p>
            <div className="mt-5 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={resetSetup}
                disabled={resettingSetup}
                className="inline-flex items-center gap-2 rounded-full border border-rose-200 bg-white px-4 py-2 text-sm font-semibold text-rose-700 disabled:opacity-60"
              >
                {resettingSetup ? <Loader2 className="h-4 w-4 animate-spin" /> : <Unplug className="h-4 w-4" />}
                {resettingSetup ? 'Resetting...' : 'Reset GitHub Setup'}
              </button>
              <a
                href={settings?.create_oauth_app_url || 'https://github.com/settings/applications/new'}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700"
              >
                <ExternalLink className="h-4 w-4" />
                Create OAuth App
              </a>
            </div>
          </div>
        ) : null}

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
            <h3 className="mt-2 text-xl font-semibold text-slate-900">
              {connection ? 'Choose a connected repository' : 'Finish GitHub sign-in first'}
            </h3>
            <p className="mt-2 max-w-2xl text-sm leading-7 text-slate-500">
              {connection
                ? 'DevHub lists repositories available to the connected GitHub account and inspects the selected repo before import.'
                : 'OAuth app setup is done, but no GitHub user has completed browser sign-in yet. Click Connect GitHub above, approve access, and then return here to load repos.'}
            </p>
          </div>
          {connection ? (
            <button
              type="button"
              onClick={() => void loadRepositories()}
              disabled={!connection || loadingRepositories}
              className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:-translate-y-0.5 disabled:opacity-60"
            >
              {loadingRepositories ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              Refresh Repos
            </button>
          ) : (
            <button
              type="button"
              onClick={connectGitHub}
              className="inline-flex items-center gap-2 rounded-full bg-slate-950 px-4 py-2 text-sm font-semibold text-white shadow-[0_14px_30px_rgba(15,23,42,0.16)]"
            >
              <Github className="h-4 w-4" />
              Connect GitHub
            </button>
          )}
        </div>

        {connection ? (
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
        ) : (
          <div className="mt-6 rounded-2xl border border-dashed border-slate-200 bg-[#fafbfc] px-4 py-6 text-sm leading-7 text-slate-500">
            No GitHub account token is connected yet, so DevHub has nothing to list here. After you complete browser sign-in, this section will populate automatically.
          </div>
        )}

        <div className="mt-5 flex flex-wrap items-center gap-3 text-xs text-slate-500">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-50 px-3 py-1.5">
            <Github className="h-3.5 w-3.5" />
            {connection ? `${repositories.length} repos available to this connection` : 'No connected GitHub account yet'}
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
