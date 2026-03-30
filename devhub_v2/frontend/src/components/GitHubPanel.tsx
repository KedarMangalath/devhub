import { useEffect, useState } from 'react';
import { ExternalLink, Github, GitPullRequest, Loader2, RefreshCw } from 'lucide-react';

const API = 'http://localhost:8000/api';

type Props = {
  projectId: string;
  integration?: any;
};

export default function GitHubPanel({ projectId, integration }: Props) {
  const [loading, setLoading] = useState(false);
  const [issues, setIssues] = useState<any[]>([]);
  const [pulls, setPulls] = useState<any[]>([]);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [issueForm, setIssueForm] = useState({ title: '', body: '' });
  const [pullForm, setPullForm] = useState({
    title: '',
    body: '',
    head: '',
    base: integration?.default_branch || 'main',
    draft: false,
  });
  const connected = Boolean(integration?.connection_id && integration?.full_name);

  const loadActivity = async () => {
    if (!connected) return;
    setLoading(true);
    try {
      const [issuesResponse, pullsResponse] = await Promise.all([
        fetch(`${API}/projects/${projectId}/github/issues/`),
        fetch(`${API}/projects/${projectId}/github/pulls/`),
      ]);
      const issuesData = await issuesResponse.json();
      const pullsData = await pullsResponse.json();
      if (!issuesResponse.ok) {
        setFeedback({ type: 'error', text: issuesData.error || 'Could not load GitHub issues.' });
        return;
      }
      if (!pullsResponse.ok) {
        setFeedback({ type: 'error', text: pullsData.error || 'Could not load GitHub pull requests.' });
        return;
      }
      setIssues(Array.isArray(issuesData.issues) ? issuesData.issues : []);
      setPulls(Array.isArray(pullsData.pulls) ? pullsData.pulls : []);
    } catch {
      setFeedback({ type: 'error', text: 'Could not load GitHub activity right now.' });
    } finally {
      setLoading(false);
    }
  };

  const createIssue = async () => {
    if (!issueForm.title.trim()) return;
    try {
      const response = await fetch(`${API}/projects/${projectId}/github/issues/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: issueForm.title.trim(), body: issueForm.body.trim() }),
      });
      const data = await response.json();
      if (!response.ok) {
        setFeedback({ type: 'error', text: data.error || 'Could not create the GitHub issue.' });
        return;
      }
      setIssueForm({ title: '', body: '' });
      setFeedback({ type: 'success', text: `Created issue #${data.issue?.number}.` });
      void loadActivity();
    } catch {
      setFeedback({ type: 'error', text: 'Could not create the GitHub issue.' });
    }
  };

  const createPull = async () => {
    if (!pullForm.title.trim() || !pullForm.head.trim() || !pullForm.base.trim()) return;
    try {
      const response = await fetch(`${API}/projects/${projectId}/github/pulls/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: pullForm.title.trim(),
          body: pullForm.body.trim(),
          head: pullForm.head.trim(),
          base: pullForm.base.trim(),
          draft: pullForm.draft,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        setFeedback({ type: 'error', text: data.error || 'Could not create the pull request.' });
        return;
      }
      setPullForm((current) => ({ ...current, title: '', body: '', head: '' }));
      setFeedback({ type: 'success', text: `Created pull request #${data.pull?.number}.` });
      void loadActivity();
    } catch {
      setFeedback({ type: 'error', text: 'Could not create the pull request.' });
    }
  };

  useEffect(() => {
    setPullForm((current) => ({ ...current, base: integration?.default_branch || current.base || 'main' }));
  }, [integration?.default_branch]);

  useEffect(() => {
    void loadActivity();
  }, [projectId, integration?.connection_id, integration?.full_name]);

  if (!connected) {
    return (
      <div className="rounded-[28px] border border-black/5 bg-white p-6 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
        <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">GitHub</p>
        <h2 className="mt-2 text-xl font-semibold text-slate-900">No connected GitHub repo yet</h2>
        <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-500">
          This project is not linked to a connected GitHub repository yet, so DevHub cannot sync issues or pull requests here.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="rounded-[28px] border border-black/5 bg-[linear-gradient(145deg,rgba(255,255,255,0.96),rgba(248,250,252,0.92))] px-6 py-6 shadow-[0_22px_60px_rgba(15,23,42,0.1)]">
        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">GitHub Integration</p>
            <h2 className="mt-2 text-[clamp(1.45rem,2.3vw,2.2rem)] font-semibold leading-[1.05] text-slate-900">
              {integration.full_name}
            </h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-600">
              DevHub is connected through the signed-in GitHub account <span className="font-semibold text-slate-900">@{integration.connection_login || 'github-user'}</span>, so this project can pull repo metadata, issues, and pull requests without relying on a public-only clone.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => void loadActivity()}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-full border border-black/5 bg-white px-4 py-2 text-sm font-semibold text-slate-700 shadow-[0_12px_30px_rgba(15,23,42,0.06)] disabled:opacity-60"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              Refresh
            </button>
            <a
              href={integration.html_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 rounded-full bg-slate-950 px-4 py-2 text-sm font-semibold text-white shadow-[0_14px_30px_rgba(15,23,42,0.16)]"
            >
              <ExternalLink className="h-4 w-4" />
              Open Repo
            </a>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          <span className="rounded-full border border-black/5 bg-white px-3 py-1 text-[11px] font-medium text-slate-600">
            Default branch: {integration.default_branch || 'unknown'}
          </span>
          <span className="rounded-full border border-black/5 bg-white px-3 py-1 text-[11px] font-medium text-slate-600">
            Visibility: {integration.private ? 'private' : 'public'}
          </span>
        </div>
      </div>

      {feedback ? (
        <div className={`rounded-2xl px-4 py-3 text-sm ${feedback.type === 'error' ? 'bg-[#fff1f1] text-red-700' : 'bg-emerald-50 text-emerald-700'}`}>
          {feedback.text}
        </div>
      ) : null}

      <div className="grid gap-5 xl:grid-cols-2">
        <div className="rounded-[28px] border border-black/5 bg-white p-5 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
          <div className="flex items-center gap-2">
            <Github className="h-4 w-4 text-slate-500" />
            <h3 className="text-sm font-semibold text-slate-900">Issues</h3>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-500">{issues.length}</span>
          </div>
          <div className="mt-4 space-y-3">
            <input
              value={issueForm.title}
              onChange={(event) => setIssueForm((current) => ({ ...current, title: event.target.value }))}
              placeholder="Create an issue title"
              className="h-11 w-full rounded-2xl border border-black/10 bg-white px-4 text-sm text-slate-700 outline-none transition-shadow focus:shadow-[0_0_0_4px_rgba(15,23,42,0.06)]"
            />
            <textarea
              value={issueForm.body}
              onChange={(event) => setIssueForm((current) => ({ ...current, body: event.target.value }))}
              rows={4}
              placeholder="Issue body"
              className="w-full rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm text-slate-700 outline-none transition-shadow focus:shadow-[0_0_0_4px_rgba(15,23,42,0.06)]"
            />
            <button
              type="button"
              onClick={createIssue}
              className="rounded-full bg-slate-950 px-4 py-2 text-sm font-semibold text-white shadow-[0_14px_30px_rgba(15,23,42,0.16)]"
            >
              Create Issue
            </button>
          </div>
          <div className="mt-5 space-y-3">
            {issues.length ? issues.map((issue) => (
              <a
                key={issue.id}
                href={issue.html_url}
                target="_blank"
                rel="noreferrer"
                className="block rounded-2xl border border-black/5 bg-[#fbfcfe] p-4 shadow-[0_10px_24px_rgba(15,23,42,0.05)]"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="text-xs font-semibold text-slate-900">#{issue.number} {issue.title}</span>
                  <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-medium text-slate-500">{issue.state}</span>
                </div>
                <p className="mt-2 text-[11px] text-slate-500">By {issue.author || 'unknown'} | comments: {issue.comments || 0}</p>
              </a>
            )) : (
              <div className="rounded-2xl border border-dashed border-black/10 bg-[#fafbfc] px-4 py-8 text-center text-sm text-slate-500">
                No issues returned from GitHub for this repository.
              </div>
            )}
          </div>
        </div>

        <div className="rounded-[28px] border border-black/5 bg-white p-5 shadow-[0_18px_50px_rgba(15,23,42,0.08)]">
          <div className="flex items-center gap-2">
            <GitPullRequest className="h-4 w-4 text-slate-500" />
            <h3 className="text-sm font-semibold text-slate-900">Pull Requests</h3>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-500">{pulls.length}</span>
          </div>
          <div className="mt-4 space-y-3">
            <input
              value={pullForm.title}
              onChange={(event) => setPullForm((current) => ({ ...current, title: event.target.value }))}
              placeholder="Pull request title"
              className="h-11 w-full rounded-2xl border border-black/10 bg-white px-4 text-sm text-slate-700 outline-none transition-shadow focus:shadow-[0_0_0_4px_rgba(15,23,42,0.06)]"
            />
            <div className="grid gap-3 md:grid-cols-2">
              <input
                value={pullForm.head}
                onChange={(event) => setPullForm((current) => ({ ...current, head: event.target.value }))}
                placeholder="Head branch"
                className="h-11 w-full rounded-2xl border border-black/10 bg-white px-4 text-sm text-slate-700 outline-none transition-shadow focus:shadow-[0_0_0_4px_rgba(15,23,42,0.06)]"
              />
              <input
                value={pullForm.base}
                onChange={(event) => setPullForm((current) => ({ ...current, base: event.target.value }))}
                placeholder="Base branch"
                className="h-11 w-full rounded-2xl border border-black/10 bg-white px-4 text-sm text-slate-700 outline-none transition-shadow focus:shadow-[0_0_0_4px_rgba(15,23,42,0.06)]"
              />
            </div>
            <textarea
              value={pullForm.body}
              onChange={(event) => setPullForm((current) => ({ ...current, body: event.target.value }))}
              rows={4}
              placeholder="Pull request body"
              className="w-full rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm text-slate-700 outline-none transition-shadow focus:shadow-[0_0_0_4px_rgba(15,23,42,0.06)]"
            />
            <label className="inline-flex items-center gap-2 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={pullForm.draft}
                onChange={(event) => setPullForm((current) => ({ ...current, draft: event.target.checked }))}
              />
              Create as draft
            </label>
            <button
              type="button"
              onClick={createPull}
              className="rounded-full bg-slate-950 px-4 py-2 text-sm font-semibold text-white shadow-[0_14px_30px_rgba(15,23,42,0.16)]"
            >
              Create Pull Request
            </button>
          </div>
          <div className="mt-5 space-y-3">
            {pulls.length ? pulls.map((pull) => (
              <a
                key={pull.id}
                href={pull.html_url}
                target="_blank"
                rel="noreferrer"
                className="block rounded-2xl border border-black/5 bg-[#fbfcfe] p-4 shadow-[0_10px_24px_rgba(15,23,42,0.05)]"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="text-xs font-semibold text-slate-900">#{pull.number} {pull.title}</span>
                  <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-medium text-slate-500">{pull.state}</span>
                </div>
                <p className="mt-2 text-[11px] text-slate-500">
                  {pull.head_branch || 'head'} to {pull.base_branch || 'base'} | {pull.draft ? 'draft' : 'ready'} | by {pull.author || 'unknown'}
                </p>
              </a>
            )) : (
              <div className="rounded-2xl border border-dashed border-black/10 bg-[#fafbfc] px-4 py-8 text-center text-sm text-slate-500">
                No pull requests returned from GitHub for this repository.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
