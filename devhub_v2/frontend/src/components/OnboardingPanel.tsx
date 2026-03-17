import { useState } from 'react';
import MermaidDiagram from './MermaidDiagram';

interface Props { blueprint: any; projectName: string; }

const CopyBtn = ({ text }: { text: string }) => {
  const [ok, setOk] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setOk(true); setTimeout(() => setOk(false), 1500); }}
      className="text-[9px] px-1.5 py-0.5 rounded bg-slate-200 text-slate-600 hover:bg-slate-300 shrink-0"
    >{ok ? '✓' : 'Copy'}</button>
  );
};

/* ── Sections nav ── */
const SECTIONS = [
  { id: 'welcome', label: '👋 Welcome', icon: '1' },
  { id: 'setup', label: '⚙️ Environment Setup', icon: '2' },
  { id: 'codebase', label: '📂 Codebase Tour', icon: '3' },
  { id: 'architecture', label: '🏗️ Architecture', icon: '4' },
  { id: 'concepts', label: '💡 Key Concepts', icon: '5' },
  { id: 'workflows', label: '📋 Common Workflows', icon: '6' },
  { id: 'gotchas', label: '⚠️ Gotchas & FAQ', icon: '7' },
  { id: 'progress', label: '✅ Progress Tracker', icon: '8' },
];

export default function OnboardingPanel({ blueprint, projectName }: Props) {
  const [section, setSection] = useState('welcome');
  const [done, setDone] = useState<Set<string>>(new Set());
  const [openConcept, setOpenConcept] = useState(-1);
  const [openWorkflow, setOpenWorkflow] = useState(-1);

  const toggle = (key: string) => {
    setDone(prev => { const n = new Set(prev); n.has(key) ? n.delete(key) : n.add(key); return n; });
  };

  const checkItems = [
    ...(blueprint?.setup_steps || []).map((_: any, i: number) => `setup-${i}`),
    ...(blueprint?.onboarding_checklist || []).map((_: any, i: number) => `check-${i}`),
  ];
  const progress = checkItems.length > 0 ? Math.round(([...checkItems].filter(k => done.has(k)).length / checkItems.length) * 100) : 0;

  const CheckBox = ({ id }: { id: string }) => (
    <button onClick={() => toggle(id)}
      className={`w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 transition-colors ${done.has(id) ? 'bg-emerald-500 border-emerald-500 text-white' : 'border-slate-300 hover:border-emerald-400'}`}>
      {done.has(id) && <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>}
    </button>
  );

  if (!blueprint || Object.keys(blueprint).length === 0) {
    return (
      <div className="h-64 flex flex-col items-center justify-center text-center">
        <p className="text-slate-400 font-medium">No blueprint generated yet</p>
        <p className="text-xs text-slate-400 mt-1">Go to the Blueprint tab and generate one first to unlock the guided walkthrough.</p>
      </div>
    );
  }

  return (
    <div className="flex gap-4" style={{ height: 'calc(100vh - 220px)' }}>
      {/* Left sidebar — section nav */}
      <div className="w-56 shrink-0 border-r border-slate-200 pr-3 overflow-y-auto">
        <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-3">Onboarding Guide</div>
        <div className="space-y-1">
          {SECTIONS.map(s => (
            <button
              key={s.id}
              onClick={() => setSection(s.id)}
              className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-left transition-all ${section === s.id ? 'bg-emerald-600 text-white shadow-md font-semibold' : 'text-slate-600 hover:bg-slate-100'}`}
            >
              <span className={`w-5 h-5 rounded-full text-[10px] font-bold flex items-center justify-center shrink-0 ${section === s.id ? 'bg-white/20' : 'bg-slate-100'}`}>{s.icon}</span>
              {s.label.split(' ').slice(1).join(' ')}
            </button>
          ))}
        </div>
        {/* Mini progress */}
        <div className="mt-6 bg-emerald-50 rounded-lg p-3 border border-emerald-100">
          <div className="text-[10px] text-emerald-700 font-medium mb-1">Onboarding Progress</div>
          <div className="bg-emerald-200 rounded-full h-1.5">
            <div className="bg-emerald-500 rounded-full h-1.5 transition-all" style={{ width: `${progress}%` }} />
          </div>
          <div className="text-[10px] text-emerald-600 mt-1">{progress}% complete</div>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-1">

        {/* ══════════ WELCOME ══════════ */}
        {section === 'welcome' && (
          <div className="space-y-4">
            <div className="bg-gradient-to-r from-emerald-500 to-teal-600 rounded-xl p-6 text-white">
              <h2 className="text-xl font-bold mb-2">Welcome to {projectName}! 👋</h2>
              <p className="text-emerald-100 text-sm leading-relaxed mb-4">
                {blueprint.project_summary || `This is your guided onboarding experience for ${projectName}. Follow each section step by step to get from zero to productive.`}
              </p>
              <div className="flex gap-3">
                <button onClick={() => setSection('setup')} className="px-4 py-2 bg-white/20 hover:bg-white/30 rounded-lg text-sm font-medium backdrop-blur-sm transition-colors">
                  Start Setup →
                </button>
                <button onClick={() => setSection('codebase')} className="px-4 py-2 bg-white/10 hover:bg-white/20 rounded-lg text-sm font-medium backdrop-blur-sm transition-colors">
                  Browse Codebase
                </button>
              </div>
            </div>

            {/* Quick stats */}
            <div className="grid grid-cols-4 gap-3">
              {[
                { label: 'Services', val: (blueprint.services || []).length, color: 'text-blue-600 bg-blue-50' },
                { label: 'API Endpoints', val: (blueprint.api_endpoints || []).length, color: 'text-purple-600 bg-purple-50' },
                { label: 'DB Tables', val: (blueprint.database_schema || []).length, color: 'text-amber-600 bg-amber-50' },
                { label: 'Components', val: (blueprint.key_components || []).length, color: 'text-emerald-600 bg-emerald-50' },
              ].map(s => (
                <div key={s.label} className={`rounded-xl p-4 text-center border border-slate-100 ${s.color.split(' ')[1]}`}>
                  <div className={`text-2xl font-bold ${s.color.split(' ')[0]}`}>{s.val}</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">{s.label}</div>
                </div>
              ))}
            </div>

            {/* Tech Stack overview */}
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h3 className="font-semibold text-sm mb-3">Technology Stack</h3>
              <div className="flex flex-wrap gap-2">
                {(blueprint.tech_stack_details || []).map((t: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 bg-slate-50 border border-slate-100 rounded-lg px-3 py-2">
                    <span className="font-medium text-xs">{t.tech}</span>
                    {t.category && <span className="text-[9px] bg-indigo-50 text-indigo-600 px-1 py-0.5 rounded">{t.category}</span>}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ══════════ ENVIRONMENT SETUP ══════════ */}
        {section === 'setup' && (
          <div className="space-y-4">
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h3 className="font-semibold text-sm mb-4">🔧 Environment Setup</h3>
              <p className="text-xs text-slate-500 mb-4">Follow each step to set up your local development environment. Check each box as you complete it.</p>
              <div className="space-y-5">
                {(blueprint.setup_steps || []).map((s: any, i: number) => {
                  const obj = typeof s === 'string' ? { step: s, command: '', explanation: '', os_note: '' } : s;
                  return (
                    <div key={i} className="flex gap-4 items-start">
                      <CheckBox id={`setup-${i}`} />
                      <div className="flex-1 min-w-0">
                        <h4 className={`font-medium text-sm ${done.has(`setup-${i}`) ? 'line-through text-slate-400' : ''}`}>
                          Step {i + 1}: {obj.step}
                        </h4>
                        {obj.explanation && <p className="text-xs text-slate-500 mt-0.5">{obj.explanation}</p>}
                        {obj.command && (
                          <div className="flex items-center gap-2 mt-2">
                            <pre className="flex-1 text-[11px] bg-slate-800 text-green-400 px-3 py-2 rounded-lg font-mono overflow-x-auto">{obj.command}</pre>
                            <CopyBtn text={obj.command} />
                          </div>
                        )}
                        {obj.os_note && <p className="text-[10px] text-blue-600 bg-blue-50 px-2 py-1 rounded mt-1">💡 {obj.os_note}</p>}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Environment Variables */}
            {(blueprint.environment_variables || []).length > 0 && (
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <h3 className="font-semibold text-sm mb-3">🔑 Environment Variables</h3>
                <p className="text-xs text-slate-500 mb-3">Add these to your <code className="bg-slate-100 px-1 rounded">.env</code> file:</p>
                <div className="bg-slate-800 rounded-lg p-4 space-y-1.5">
                  {(blueprint.environment_variables || []).map((v: any, i: number) => (
                    <div key={i} className="font-mono text-[11px]">
                      <span className="text-slate-500"># {v.description}</span><br />
                      <span className="text-green-400">{v.name}</span><span className="text-slate-400">=</span>
                      <span className="text-amber-300">{v.example || 'your_value_here'}</span>
                    </div>
                  ))}
                </div>
                <div className="mt-2 flex justify-end">
                  <CopyBtn text={(blueprint.environment_variables || []).map((v: any) => `${v.name}=${v.example || ''}`).join('\n')} />
                </div>
              </div>
            )}
          </div>
        )}

        {/* ══════════ CODEBASE TOUR ══════════ */}
        {section === 'codebase' && (
          <div className="space-y-4">
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h3 className="font-semibold text-sm mb-2">📂 Codebase Tour</h3>
              <p className="text-xs text-slate-500 mb-4">Explore the directory structure and understand what each part of the codebase does.</p>

              {(blueprint.directory_guide || []).length > 0 ? (
                <div className="space-y-3">
                  {(blueprint.directory_guide || []).map((d: any, i: number) => (
                    <div key={i} className="border border-slate-100 rounded-xl p-4 hover:shadow-sm transition-shadow">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-blue-500 text-lg">📁</span>
                        <span className="font-mono font-bold text-sm text-slate-800">{d.path}</span>
                        {d.pattern && <span className="text-[10px] bg-violet-50 text-violet-600 px-2 py-0.5 rounded-full">{d.pattern}</span>}
                      </div>
                      <p className="text-xs text-slate-600 mb-3 leading-relaxed">{d.purpose}</p>
                      {(d.key_files || []).length > 0 && (
                        <div className="bg-slate-50 rounded-lg p-3 space-y-1.5">
                          <div className="text-[10px] font-bold text-slate-400 uppercase mb-1">Key Files</div>
                          {(d.key_files || []).map((f: string, j: number) => (
                            <div key={j} className="text-[11px] text-slate-600 font-mono flex items-start gap-2">
                              <span className="text-slate-300 shrink-0">├─</span>
                              <span>{f}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                /* Fallback: show key components if no directory guide */
                <div className="space-y-2">
                  {(blueprint.key_components || []).map((c: any, i: number) => (
                    <div key={i} className="flex items-start gap-3 border-b border-slate-50 pb-2 last:border-0">
                      <span className="text-slate-400 mt-0.5">📄</span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-medium">{c.file_path}</span>
                          <span className="text-[10px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">{c.complexity}</span>
                        </div>
                        <p className="text-[11px] text-slate-500 mt-0.5">{c.purpose}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ══════════ ARCHITECTURE ══════════ */}
        {section === 'architecture' && (
          <div className="space-y-4">
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h3 className="font-semibold text-sm mb-3">🏗️ Architecture Deep Dive</h3>
              <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-line mb-4">{blueprint.architecture_overview}</p>
            </div>

            {blueprint.mermaid_architecture && (
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <h3 className="font-semibold text-sm mb-3">System Architecture Diagram</h3>
                <MermaidDiagram chart={blueprint.mermaid_architecture} id="onboard-arch" />
              </div>
            )}

            {blueprint.data_flow && (
              <div className="bg-blue-50 rounded-xl border border-blue-100 p-5">
                <h3 className="font-semibold text-sm mb-2">Data Flow</h3>
                <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-line">{blueprint.data_flow}</p>
              </div>
            )}

            {blueprint.mermaid_erd && (
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <h3 className="font-semibold text-sm mb-3">Database Schema</h3>
                <MermaidDiagram chart={blueprint.mermaid_erd} id="onboard-erd" />
              </div>
            )}
          </div>
        )}

        {/* ══════════ KEY CONCEPTS ══════════ */}
        {section === 'concepts' && (
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h3 className="font-semibold text-sm mb-4">💡 Key Concepts & Domain Knowledge</h3>
            <p className="text-xs text-slate-500 mb-4">Understand these core concepts before diving into the codebase.</p>
            <div className="space-y-2">
              {(blueprint.key_concepts || []).map((c: any, i: number) => (
                <div key={i} className="border border-slate-100 rounded-xl overflow-hidden">
                  <button
                    onClick={() => setOpenConcept(openConcept === i ? -1 : i)}
                    className="w-full flex justify-between px-4 py-3 hover:bg-slate-50 text-left"
                  >
                    <span className="font-medium text-sm">{c.concept}</span>
                    <span className="text-slate-300 text-xs">{openConcept === i ? '▲' : '▼'}</span>
                  </button>
                  {openConcept === i && (
                    <div className="px-4 pb-4 space-y-2 border-t border-slate-100 bg-slate-50/50 pt-3">
                      <p className="text-xs text-slate-700 leading-relaxed">{c.explanation}</p>
                      {c.why_important && (
                        <div className="text-[11px] text-indigo-700 bg-indigo-50 px-3 py-2 rounded-lg">
                          <b>Why it matters:</b> {c.why_important}
                        </div>
                      )}
                      {c.related_code && (
                        <p className="text-[10px] font-mono text-emerald-700 bg-emerald-50 px-3 py-2 rounded-lg">
                          📄 See: {c.related_code}
                        </p>
                      )}
                      {(c.related_concepts || []).length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          <span className="text-[10px] text-slate-400">Related:</span>
                          {(c.related_concepts || []).map((r: string, j: number) => (
                            <span key={j} className="text-[10px] bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded">{r}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
              {(blueprint.key_concepts || []).length === 0 && <p className="text-xs text-slate-400 text-center py-4">No key concept data available</p>}
            </div>
          </div>
        )}

        {/* ══════════ COMMON WORKFLOWS ══════════ */}
        {section === 'workflows' && (
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h3 className="font-semibold text-sm mb-4">📋 Common Developer Workflows</h3>
            <p className="text-xs text-slate-500 mb-4">Step-by-step guides for the most common tasks you'll perform on this project.</p>
            <div className="space-y-2">
              {(blueprint.common_workflows || []).map((w: any, i: number) => (
                <div key={i} className="border border-slate-100 rounded-xl overflow-hidden">
                  <button
                    onClick={() => setOpenWorkflow(openWorkflow === i ? -1 : i)}
                    className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-50 text-left"
                  >
                    <span className="font-medium text-sm flex items-center gap-2">
                      <span className="w-6 h-6 rounded-full bg-blue-100 text-blue-700 text-[10px] font-bold flex items-center justify-center shrink-0">{i + 1}</span>
                      {w.title}
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">{(w.steps || []).length} steps</span>
                      <span className="text-slate-300">{openWorkflow === i ? '▲' : '▼'}</span>
                    </div>
                  </button>
                  {openWorkflow === i && (
                    <div className="px-4 pb-4 pt-3 bg-slate-50/50 border-t border-slate-100 space-y-3">
                      {(w.steps || []).map((step: string, j: number) => (
                        <div key={j} className="flex gap-3 items-start">
                          <div className="w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center text-[10px] font-bold shrink-0">{j + 1}</div>
                          <p className="text-xs text-slate-700 pt-1 leading-relaxed">{step}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              {(blueprint.common_workflows || []).length === 0 && <p className="text-xs text-slate-400 text-center py-4">No workflow data — regenerate the blueprint for workflow guides.</p>}
            </div>
          </div>
        )}

        {/* ══════════ GOTCHAS & FAQ ══════════ */}
        {section === 'gotchas' && (
          <div className="space-y-4">
            {(blueprint.gotchas || []).length > 0 && (
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <h3 className="font-semibold text-sm mb-3">⚠️ Gotchas & Common Pitfalls</h3>
                <div className="space-y-2">
                  {(blueprint.gotchas || []).map((g: string, i: number) => (
                    <div key={i} className="flex gap-2 text-xs bg-yellow-50/80 border border-yellow-100 rounded-lg p-3">
                      <span className="shrink-0">⚠️</span>
                      <span className="text-slate-700 leading-relaxed">{g}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {(blueprint.faq || []).length > 0 && (
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <h3 className="font-semibold text-sm mb-3">❓ Frequently Asked Questions</h3>
                <div className="space-y-4">
                  {(blueprint.faq || []).map((f: any, i: number) => (
                    <div key={i} className="border-b border-slate-50 pb-4 last:border-0 last:pb-0">
                      <h4 className="font-medium text-xs text-slate-800 mb-1.5">Q: {f.question}</h4>
                      <p className="text-[11px] text-slate-600 leading-relaxed bg-slate-50 p-3 rounded-lg">{f.answer}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ══════════ PROGRESS TRACKER ══════════ */}
        {section === 'progress' && (
          <div className="space-y-4">
            <div className="bg-gradient-to-r from-emerald-500 to-teal-600 rounded-xl p-5 text-white">
              <h3 className="text-lg font-bold mb-1">Your Onboarding Progress</h3>
              <p className="text-emerald-100 text-sm mb-3">Track your progress through the onboarding checklist.</p>
              <div className="bg-white/20 rounded-lg p-3">
                <div className="flex justify-between text-sm mb-1">
                  <span>{[...checkItems].filter(k => done.has(k)).length} of {checkItems.length} completed</span>
                  <span className="font-bold">{progress}%</span>
                </div>
                <div className="bg-white/30 rounded-full h-2.5">
                  <div className="bg-white rounded-full h-2.5 transition-all" style={{ width: `${progress}%` }} />
                </div>
              </div>
            </div>

            {/* Onboarding checklist by category */}
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h3 className="font-semibold text-sm mb-4">Checklist</h3>
              {['environment', 'codebase', 'processes', 'tools', 'team'].map(cat => {
                const items = (blueprint.onboarding_checklist || []).filter((t: any) => t.category === cat);
                if (items.length === 0) return null;
                return (
                  <div key={cat} className="mb-5 last:mb-0">
                    <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-2">
                      <span className={`w-1.5 h-1.5 rounded-full ${cat === 'environment' ? 'bg-blue-500' : cat === 'codebase' ? 'bg-purple-500' : cat === 'processes' ? 'bg-amber-500' : cat === 'tools' ? 'bg-emerald-500' : 'bg-pink-500'}`} />
                      {cat}
                    </div>
                    {items.map((t: any, i: number) => {
                      const idx = (blueprint.onboarding_checklist || []).indexOf(t);
                      return (
                        <div key={i} className="flex gap-3 items-start py-2 border-b border-slate-50 last:border-0">
                          <CheckBox id={`check-${idx}`} />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className={`text-sm ${done.has(`check-${idx}`) ? 'line-through text-slate-400' : 'text-slate-700'}`}>{t.task}</span>
                              {t.estimated_time && <span className="text-[10px] text-slate-400 bg-slate-50 px-1.5 py-0.5 rounded">{t.estimated_time}</span>}
                            </div>
                            {t.why_important && <p className="text-[10px] text-indigo-600 mt-0.5">{t.why_important}</p>}
                            {t.instructions && t.instructions !== 'Detailed step-by-step for this task' && (
                              <p className="text-[10px] text-slate-500 mt-1 bg-slate-50 p-2 rounded">{t.instructions}</p>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
