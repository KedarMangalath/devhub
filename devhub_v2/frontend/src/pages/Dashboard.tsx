import { useState, useEffect } from 'react'
import { Plus, Code2, Play, GitBranch, TerminalSquare, MessageSquare, X, Loader2, FolderOpen, Github } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'

const API = 'http://localhost:8000/api';

export default function Dashboard() {
  const navigate = useNavigate();
  const [apps, setApps] = useState<any[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');
  const [form, setForm] = useState({ name: '', description: '', local_path: '', github_url: '', tech_stack: '' });

  const fetchProjects = () => {
    fetch(`${API}/projects/`)
      .then(res => res.json())
      .then(data => { if (data.projects) setApps(data.projects); })
      .catch(err => console.error("Failed to fetch projects:", err));
  };

  useEffect(() => { fetchProjects(); }, []);

  const handleCreate = async () => {
    if (!form.name.trim()) return;
    setCreating(true);
    setCreateError('');
    try {
      const res = await fetch(`${API}/projects/create/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name.trim(),
          description: form.description.trim(),
          local_path: form.local_path.trim(),
          github_url: form.github_url.trim(),
          tech_stack: form.tech_stack ? form.tech_stack.split(',').map(s => s.trim()).filter(Boolean) : [],
        }),
      });
      const data = await res.json();
      if (res.ok) {
        setShowCreate(false);
        setForm({ name: '', description: '', local_path: '', github_url: '', tech_stack: '' });
        fetchProjects();
        if (data.id) navigate(`/project/${data.id}`);
      } else {
        setCreateError(data.error || 'Failed to create project');
      }
    } catch (e) {
      console.error(e);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#f8f9fa] text-slate-900 font-sans selection:bg-purple-200">
      
      {/* Top Header */}
      <header className="sticky top-0 z-50 w-full glass border-b border-slate-200/50">
        <div className="flex h-16 items-center px-6 justify-between max-w-7xl mx-auto">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-black flex items-center justify-center shadow-md">
              <Code2 className="w-5 h-5 text-white" />
            </div>
            <span className="font-semibold text-lg tracking-tight">DevHub</span>
            <span className="px-2 py-0.5 rounded-full bg-slate-100 border border-slate-200 text-xs font-medium text-slate-500 ml-2">
              v2.0
            </span>
          </div>
          
          <div className="flex items-center gap-4">
            <button className="text-sm font-medium text-slate-600 hover:text-black transition-colors">
              Documentation
            </button>
            <div className="h-8 w-8 rounded-full bg-gradient-to-tr from-purple-500 to-blue-500 shadow-inner flex items-center justify-center text-white text-sm font-bold border border-white/20">
              A
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Projects</h1>
            <p className="text-slate-500 mt-1">Manage and orchestrate your autonomous applications.</p>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-white bg-black rounded-lg hover:bg-slate-800 transition-all shadow-md hover:shadow-lg active:scale-95"
          >
            <Plus className="w-4 h-4" />
            New Project
          </button>
        </div>

        {/* Dashboard Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Create New Card */}
          <div
            onClick={() => setShowCreate(true)}
            className="group relative flex flex-col items-center justify-center p-8 rounded-xl border-2 border-dashed border-slate-200 hover:border-black/30 hover:bg-white/50 transition-all cursor-pointer text-center h-48"
          >
             <div className="w-12 h-12 rounded-full bg-slate-100 group-hover:bg-black group-hover:text-white flex items-center justify-center text-slate-400 transition-colors mb-4 shadow-sm">
                <Plus className="w-6 h-6" />
             </div>
             <h3 className="font-medium text-slate-900">Create New Project</h3>
             <p className="text-sm text-slate-500 mt-1">Clone a repo, connect a folder, or generate a working starter app</p>
          </div>

          {/* Existing Apps */}
          {apps.map(app => (
            <Link to={`/project/${app.id}`} key={app.id} className="group relative flex flex-col p-6 rounded-xl bg-white border border-slate-200 hover:border-slate-300 hover:shadow-xl hover:shadow-slate-200/50 transition-all h-48 overflow-hidden">
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-purple-500 to-blue-500 opacity-0 group-hover:opacity-100 transition-opacity" />
              
              <div className="flex justify-between items-start mb-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-center">
                    <TerminalSquare className="w-5 h-5 text-slate-700" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-slate-900 text-lg">{app.name}</h3>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <div className={`w-2 h-2 rounded-full ${app.status === 'active' ? 'bg-emerald-500' : 'bg-amber-400'}`} />
                      <span className="text-xs font-medium text-slate-500 capitalize">{app.status}</span>
                    </div>
                  </div>
                </div>
              </div>

              {app.description && (
                <p className="text-xs text-slate-400 mb-2 line-clamp-2">{app.description}</p>
              )}

              <div className="flex gap-2 mb-auto flex-wrap">
                {(app.tech_stack || []).map((t: string) => (
                  <span key={t} className="px-2 py-0.5 bg-slate-50 border border-slate-100 rounded text-xs text-slate-600 font-medium">
                    {t}
                  </span>
                ))}
              </div>

              <div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-100">
                <div className="flex items-center gap-4 text-slate-400">
                  <div className="flex items-center gap-1">
                    <GitBranch className="w-3.5 h-3.5" />
                    <span className="text-xs font-medium">0</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <MessageSquare className="w-3.5 h-3.5" />
                    <span className="text-xs font-medium">0</span>
                  </div>
                </div>
                <span className="text-sm font-medium text-black group-hover:text-blue-600 flex items-center gap-1 transition-colors">
                  Open Engine <Play className="w-3 h-3" />
                </span>
              </div>
            </Link>
          ))}
        </div>
      </main>

      {/* ── Create Project Modal ── */}
      {showCreate && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setShowCreate(false)} />
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 p-0 overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
              <h2 className="text-lg font-semibold">Create New Project</h2>
              <button onClick={() => setShowCreate(false)} className="p-1 rounded-lg hover:bg-slate-100 transition-colors">
                <X className="w-5 h-5 text-slate-400" />
              </button>
            </div>

            {/* Form */}
            <div className="px-6 py-5 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Project Name *</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={e => setForm({...form, name: e.target.value})}
                  placeholder="My Awesome App"
                  className="w-full h-10 px-3 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Description</label>
                <textarea
                  value={form.description}
                  onChange={e => setForm({...form, description: e.target.value})}
                  placeholder="Brief description of your project..."
                  rows={2}
                  className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent resize-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  <Github className="w-4 h-4 inline mr-1" />
                  GitHub URL
                </label>
                <input
                  type="text"
                  value={form.github_url}
                  onChange={e => setForm({...form, github_url: e.target.value})}
                  placeholder="https://github.com/user/repo.git"
                  className="w-full h-10 px-3 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent font-mono"
                />
                <p className="text-xs text-slate-400 mt-1">Public repo URL — will be cloned via <code className="bg-slate-100 px-1 rounded">git clone</code>.</p>
              </div>
              <div className="flex items-center gap-3 text-xs text-slate-400">
                <div className="flex-1 h-px bg-slate-200" />
                OR
                <div className="flex-1 h-px bg-slate-200" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  <FolderOpen className="w-4 h-4 inline mr-1" />
                  Local Path
                </label>
                <input
                  type="text"
                  value={form.local_path}
                  onChange={e => setForm({...form, local_path: e.target.value})}
                  placeholder="C:/Users/you/projects/my-app"
                  className="w-full h-10 px-3 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent font-mono"
                />
                <p className="text-xs text-slate-400 mt-1">Point to an existing folder to browse files in the Code Explorer. Leave both source fields empty to generate a runnable starter app.</p>
              </div>
              {createError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                  {createError}
                </div>
              )}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Tech Stack (comma-separated)</label>
                <input
                  type="text"
                  value={form.tech_stack}
                  onChange={e => setForm({...form, tech_stack: e.target.value})}
                  placeholder="React, Django, SQLite"
                  className="w-full h-10 px-3 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent"
                />
              </div>
            </div>

            {/* Footer */}
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-slate-100 bg-slate-50/50">
              <button
                onClick={() => setShowCreate(false)}
                className="px-4 py-2 text-sm font-medium text-slate-700 rounded-lg hover:bg-slate-200 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={creating || !form.name.trim()}
                className="px-5 py-2 text-sm font-medium text-white bg-black rounded-lg hover:bg-slate-800 transition-colors shadow-md disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-2"
              >
                {creating && <Loader2 className="w-4 h-4 animate-spin" />}
                {creating ? 'Creating...' : 'Create Project'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
