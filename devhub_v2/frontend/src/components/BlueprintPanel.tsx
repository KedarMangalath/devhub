import { useState } from 'react';
import MermaidDiagram from './MermaidDiagram';

interface Props { blueprint: any; }

const SUB_TABS = [
  { id: 'overview', label: 'Overview', icon: '📋' },
  { id: 'components', label: 'Components', icon: '🧩' },
  { id: 'services', label: 'Services', icon: '🔧' },
  { id: 'api', label: 'API Reference', icon: '🔌' },
  { id: 'database', label: 'Database', icon: '🗄️' },
  { id: 'setup', label: 'Setup Guide', icon: '⚙️' },
  { id: 'security', label: 'Security & Perf', icon: '🛡️' },
  { id: 'workflows', label: 'Workflows', icon: '📝' },
];

/* ── tiny reusable badges ── */
const MethodBadge = ({ method }: { method: string }) => {
  const c: Record<string, string> = {
    GET: 'bg-emerald-100 text-emerald-700', POST: 'bg-blue-100 text-blue-700',
    PUT: 'bg-amber-100 text-amber-700', DELETE: 'bg-red-100 text-red-700',
    PATCH: 'bg-purple-100 text-purple-700',
  };
  return <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${c[method] || 'bg-slate-100'}`}>{method}</span>;
};

const ComplexityBadge = ({ level }: { level: string }) => {
  const c = level === 'high' ? 'bg-red-100 text-red-700' : level === 'medium' ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700';
  return <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${c}`}>{level}</span>;
};

const SeverityDot = ({ level }: { level: string }) => {
  const c = level === 'high' ? 'bg-red-500' : level === 'medium' ? 'bg-amber-500' : 'bg-emerald-500';
  return <span className={`w-2 h-2 rounded-full ${c} inline-block`} />;
};

const CopyButton = ({ text }: { text: string }) => {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
      className="text-[9px] px-1.5 py-0.5 rounded bg-slate-200 text-slate-600 hover:bg-slate-300 shrink-0"
    >{copied ? '✓ Copied' : 'Copy'}</button>
  );
};

const Section = ({ title, children, className = '' }: { title: string; children: React.ReactNode; className?: string }) => (
  <div className={`bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden ${className}`}>
    <div className="px-5 py-3 border-b border-slate-100 bg-slate-50/60">
      <h3 className="font-semibold text-sm text-slate-800">{title}</h3>
    </div>
    <div className="p-5">{children}</div>
  </div>
);

export default function BlueprintPanel({ blueprint }: Props) {
  const [tab, setTab] = useState('overview');
  const [openApi, setOpenApi] = useState(-1);
  const [openComponent, setOpenComponent] = useState(-1);
  const [openWorkflow, setOpenWorkflow] = useState(-1);

  if (!blueprint || Object.keys(blueprint).length === 0) {
    return (
      <div className="h-64 flex flex-col items-center justify-center text-center">
        <p className="text-slate-400 font-medium">No blueprint generated yet</p>
        <p className="text-xs text-slate-400 mt-1">Click "Refresh Blueprint" to generate the architecture wiki.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Sub-nav */}
      <div className="flex gap-1 bg-slate-100 rounded-xl p-1 flex-wrap">
        {SUB_TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-3 py-1.5 text-xs rounded-lg transition-all ${tab === t.id ? 'bg-white shadow-sm font-semibold text-slate-900' : 'text-slate-500 hover:text-slate-700 hover:bg-white/50'}`}>
            <span className="mr-1">{t.icon}</span>{t.label}
          </button>
        ))}
      </div>

      {/* ═══════════════════════════════════ OVERVIEW ═══════════════════════════════════ */}
      {tab === 'overview' && (
        <div className="space-y-4">
          {/* Project Summary */}
          {blueprint.project_summary && (
            <div className="bg-gradient-to-r from-indigo-500 to-violet-600 rounded-xl p-6 text-white">
              <h2 className="text-lg font-bold mb-2">Project Summary</h2>
              <p className="text-sm leading-relaxed text-indigo-100">{blueprint.project_summary}</p>
            </div>
          )}

          {/* Architecture Overview */}
          <Section title="Architecture Overview">
            <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-line">{blueprint.architecture_overview}</p>
          </Section>

          {/* Architecture Diagram */}
          {blueprint.mermaid_architecture && (
            <Section title="System Architecture Diagram">
              <MermaidDiagram chart={blueprint.mermaid_architecture} id="arch" />
            </Section>
          )}

          {/* Data Flow */}
          {blueprint.data_flow && (
            <Section title="Data Flow">
              <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-line">{blueprint.data_flow}</p>
            </Section>
          )}

          {/* Tech Stack */}
          <Section title="Technology Stack">
            <div className="grid grid-cols-2 gap-3">
              {(blueprint.tech_stack_details || []).map((t: any, i: number) => (
                <div key={i} className="border border-slate-100 rounded-lg p-4 hover:shadow-md transition-shadow">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="font-semibold text-sm">{t.tech}</span>
                    {t.version && t.version !== 'unknown' && <span className="text-[10px] font-mono bg-slate-100 px-1.5 py-0.5 rounded">{t.version}</span>}
                    {t.category && <span className="text-[10px] bg-indigo-50 text-indigo-600 px-1.5 py-0.5 rounded-full">{t.category}</span>}
                  </div>
                  <p className="text-xs text-slate-600 mb-1">{t.purpose}</p>
                  {t.why_chosen && <p className="text-[11px] text-blue-700 bg-blue-50 px-2 py-1 rounded mt-1 italic">{t.why_chosen}</p>}
                </div>
              ))}
            </div>
          </Section>

          {/* Key Components Table */}
          {(blueprint.key_components || []).length > 0 && (
            <Section title="Key Components">
              <table className="w-full text-xs">
                <thead className="bg-slate-50 text-slate-500 uppercase text-[10px]">
                  <tr><th className="px-4 py-2 text-left">Component</th><th className="px-4 py-2 text-left">Path</th><th className="px-4 py-2 text-left">Purpose</th><th className="px-4 py-2 text-left">Complexity</th></tr>
                </thead>
                <tbody>
                  {(blueprint.key_components || []).map((c: any, i: number) => (
                    <tr key={i} className="border-t border-slate-50 hover:bg-slate-50">
                      <td className="px-4 py-2.5 font-medium">{c.name}</td>
                      <td className="px-4 py-2.5 font-mono text-slate-500 text-[10px]">{c.file_path}</td>
                      <td className="px-4 py-2.5 text-slate-600">{c.purpose}</td>
                      <td className="px-4 py-2.5"><ComplexityBadge level={c.complexity} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Section>
          )}
        </div>
      )}

      {/* ═══════════════════════════════════ COMPONENTS ═══════════════════════════════════ */}
      {tab === 'components' && (
        <div className="space-y-4">
          {/* Directory Guide */}
          {(blueprint.directory_guide || []).length > 0 && (
            <Section title="Directory Structure Guide">
              <div className="space-y-3">
                {(blueprint.directory_guide || []).map((d: any, i: number) => (
                  <div key={i} className="border border-slate-100 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-blue-500">📁</span>
                      <span className="font-mono font-semibold text-sm text-slate-800">{d.path}</span>
                      {d.pattern && <span className="text-[10px] bg-violet-50 text-violet-600 px-1.5 py-0.5 rounded">{d.pattern}</span>}
                    </div>
                    <p className="text-xs text-slate-600 mb-2">{d.purpose}</p>
                    {(d.key_files || []).length > 0 && (
                      <div className="bg-slate-50 rounded p-2 space-y-1">
                        {(d.key_files || []).map((f: string, j: number) => (
                          <div key={j} className="text-[11px] text-slate-600 font-mono flex items-start gap-1.5">
                            <span className="text-slate-400 shrink-0">└</span>{f}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Component Detail Cards */}
          {(blueprint.key_components || []).length > 0 && (
            <Section title="Component Details">
              <div className="space-y-2">
                {(blueprint.key_components || []).map((c: any, i: number) => (
                  <div key={i} className="border border-slate-100 rounded-lg overflow-hidden">
                    <button
                      onClick={() => setOpenComponent(openComponent === i ? -1 : i)}
                      className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-50 text-left"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <span className="font-medium text-sm">{c.name}</span>
                        <span className="text-[10px] font-mono bg-slate-100 px-1.5 py-0.5 rounded text-slate-500 truncate max-w-[200px]">{c.file_path}</span>
                        <ComplexityBadge level={c.complexity} />
                      </div>
                      <span className="text-slate-300 text-xs shrink-0 ml-2">{openComponent === i ? '▲' : '▼'}</span>
                    </button>
                    {openComponent === i && (
                      <div className="px-4 pb-4 space-y-2 bg-slate-50/50 border-t border-slate-100">
                        <p className="text-xs text-slate-700 pt-2">{c.purpose}</p>
                        {c.exports && (
                          <div className="text-[11px]"><b className="text-slate-500">Exports:</b> <code className="bg-slate-100 px-1 rounded">{c.exports}</code></div>
                        )}
                        {c.lines_estimate && (
                          <div className="text-[11px] text-slate-500">≈ {c.lines_estimate} lines</div>
                        )}
                        {(c.dependencies || []).length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1">
                            <span className="text-[10px] text-slate-400 mr-1">Depends on:</span>
                            {(c.dependencies || []).map((dep: string, j: number) => (
                              <span key={j} className="text-[10px] bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded">{dep}</span>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Section>
          )}
        </div>
      )}

      {/* ═══════════════════════════════════ SERVICES ═══════════════════════════════════ */}
      {tab === 'services' && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            {(blueprint.services || []).map((s: any, i: number) => (
              <div key={i} className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md transition-shadow">
                <div className="flex items-center gap-2 mb-2 flex-wrap">
                  <span className="font-semibold text-sm">{s.name}</span>
                  <span className="text-[10px] bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded-full font-medium">{s.type}</span>
                  {s.port && <span className="text-[10px] font-mono bg-emerald-50 text-emerald-700 px-1.5 py-0.5 rounded">:{s.port}</span>}
                </div>
                <p className="text-xs text-slate-600 mb-3 leading-relaxed">{s.description}</p>
                {s.tech && <div className="text-[10px] mb-2"><b className="text-slate-400">Tech:</b> <span className="font-mono bg-slate-50 px-1.5 py-0.5 rounded">{s.tech}</span></div>}
                {(s.dependencies || []).length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-2">
                    <span className="text-[10px] text-slate-400">Deps:</span>
                    {(s.dependencies || []).map((d: string, j: number) => (
                      <span key={j} className="text-[10px] bg-orange-50 text-orange-700 px-1.5 py-0.5 rounded">{d}</span>
                    ))}
                  </div>
                )}
                {(s.key_files || []).length > 0 && (
                  <div className="bg-slate-50 rounded p-2 mt-2 space-y-0.5">
                    {(s.key_files || []).map((f: string, j: number) => (
                      <div key={j} className="text-[10px] font-mono text-slate-500">• {f}</div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
          {(blueprint.services || []).length === 0 && <p className="text-sm text-slate-400 text-center py-8">No service architecture data available</p>}
        </div>
      )}

      {/* ═══════════════════════════════════ API ═══════════════════════════════════ */}
      {tab === 'api' && (
        <Section title={`API Reference · ${(blueprint.api_endpoints || []).length} endpoints`}>
          <div className="divide-y divide-slate-100">
            {(blueprint.api_endpoints || []).map((e: any, i: number) => (
              <div key={i}>
                <button
                  onClick={() => setOpenApi(openApi === i ? -1 : i)}
                  className="w-full flex items-center gap-3 py-3 hover:bg-slate-50 text-left text-xs px-1"
                >
                  <MethodBadge method={e.method} />
                  <span className="font-mono text-slate-700 w-52 truncate shrink-0">{e.path}</span>
                  <span className="text-slate-500 flex-1 truncate">{e.description}</span>
                  {e.auth_required && <span className="text-[9px] bg-red-50 text-red-600 px-1.5 py-0.5 rounded">🔒 Auth</span>}
                  <span className="text-slate-300 shrink-0">{openApi === i ? '▲' : '▼'}</span>
                </button>
                {openApi === i && (
                  <div className="px-1 pb-4 space-y-3 bg-slate-50/50 rounded-lg mx-1 mb-2 p-3">
                    <div className="grid grid-cols-2 gap-3">
                      {e.request_body && (
                        <div>
                          <div className="text-[10px] font-semibold text-slate-400 uppercase mb-1">Request Body</div>
                          <pre className="text-[10px] bg-slate-800 text-green-400 p-3 rounded-lg overflow-x-auto whitespace-pre-wrap">{typeof e.request_body === 'string' ? e.request_body : JSON.stringify(e.request_body, null, 2)}</pre>
                        </div>
                      )}
                      {e.response && (
                        <div>
                          <div className="text-[10px] font-semibold text-slate-400 uppercase mb-1">Response</div>
                          <pre className="text-[10px] bg-slate-800 text-blue-400 p-3 rounded-lg overflow-x-auto whitespace-pre-wrap">{typeof e.response === 'string' ? e.response : JSON.stringify(e.response, null, 2)}</pre>
                        </div>
                      )}
                    </div>
                    {e.curl_example && (
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-[10px] font-semibold text-slate-400 uppercase">curl Example</span>
                          <CopyButton text={e.curl_example} />
                        </div>
                        <pre className="text-[10px] bg-slate-900 text-amber-300 p-3 rounded-lg overflow-x-auto font-mono">{e.curl_example}</pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
          {(blueprint.api_endpoints || []).length === 0 && <p className="text-sm text-slate-400 text-center py-8">No API endpoint data available</p>}
        </Section>
      )}

      {/* ═══════════════════════════════════ DATABASE ═══════════════════════════════════ */}
      {tab === 'database' && (
        <div className="space-y-4">
          {blueprint.mermaid_erd && (
            <Section title="Entity Relationship Diagram">
              <MermaidDiagram chart={blueprint.mermaid_erd} id="erd" />
            </Section>
          )}
          <Section title="Schema Reference">
            <div className="grid grid-cols-2 gap-3">
              {(blueprint.database_schema || []).map((t: any, i: number) => (
                <div key={i} className="border border-slate-200 rounded-xl p-4 hover:shadow-md transition-shadow">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-orange-500">🗄️</span>
                    <span className="font-semibold font-mono text-sm">{t.table}</span>
                  </div>
                  <p className="text-xs text-slate-600 mb-3">{t.description}</p>
                  {(Array.isArray(t.key_fields) ? t.key_fields : []).length > 0 && (
                    <table className="w-full text-[10px] border-collapse">
                      <thead>
                        <tr className="border-b border-slate-100 text-slate-400">
                          <th className="text-left py-1 pr-2">Field</th>
                          <th className="text-left py-1 pr-2">Type</th>
                          <th className="text-left py-1">Constraint</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(t.key_fields || []).map((f: any, j: number) => (
                          <tr key={j} className="border-b border-slate-50">
                            <td className="py-1 pr-2 font-mono font-medium">{typeof f === 'string' ? f : f.name}</td>
                            <td className="py-1 pr-2 text-slate-500">{typeof f === 'string' ? '' : f.type}</td>
                            <td className="py-1">
                              {typeof f !== 'string' && f.constraints && (
                                <span className={`px-1 py-0.5 rounded text-[9px] font-medium ${f.constraints?.includes('PK') ? 'bg-amber-100 text-amber-700' : f.constraints?.includes('FK') ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-600'}`}>
                                  {f.constraints}
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                  {t.relationships && <p className="text-[10px] text-indigo-600 bg-indigo-50 px-2 py-1 rounded mt-2">{t.relationships}</p>}
                </div>
              ))}
            </div>
            {(blueprint.database_schema || []).length === 0 && <p className="text-sm text-slate-400 text-center py-8">No database schema data available</p>}
          </Section>
        </div>
      )}

      {/* ═══════════════════════════════════ SETUP ═══════════════════════════════════ */}
      {tab === 'setup' && (
        <div className="space-y-4">
          <Section title="Setup Guide">
            <div className="space-y-4">
              {(blueprint.setup_steps || []).map((s: any, i: number) => {
                const stepObj = typeof s === 'string' ? { step: s, command: '', explanation: '', os_note: '' } : s;
                return (
                  <div key={i} className="flex gap-4 items-start">
                    <div className="w-8 h-8 bg-black text-white rounded-full flex items-center justify-center text-xs font-bold shrink-0">{i + 1}</div>
                    <div className="flex-1 min-w-0">
                      <h4 className="font-medium text-sm">{stepObj.step}</h4>
                      {stepObj.explanation && <p className="text-xs text-slate-500 mt-0.5">{stepObj.explanation}</p>}
                      {stepObj.command && (
                        <div className="flex items-center gap-2 mt-2">
                          <pre className="flex-1 text-[11px] bg-slate-800 text-green-400 px-3 py-2 rounded-lg font-mono overflow-x-auto">{stepObj.command}</pre>
                          <CopyButton text={stepObj.command} />
                        </div>
                      )}
                      {stepObj.os_note && <p className="text-[10px] text-slate-400 mt-1">💡 {stepObj.os_note}</p>}
                    </div>
                  </div>
                );
              })}
            </div>
          </Section>

          <div className="grid grid-cols-2 gap-4">
            {/* Environment Variables */}
            <Section title="Environment Variables">
              <div className="space-y-3">
                {(blueprint.environment_variables || []).map((v: any, i: number) => (
                  <div key={i} className="border-b border-slate-50 pb-3 last:border-0 last:pb-0">
                    <div className="flex items-center gap-2 mb-1">
                      <code className="bg-slate-100 px-2 py-0.5 rounded font-mono text-xs font-medium">{v.name}</code>
                      {v.required && <span className="text-[9px] bg-red-100 text-red-600 px-1.5 py-0.5 rounded font-medium">Required</span>}
                      {v.category && <span className="text-[9px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">{v.category}</span>}
                    </div>
                    <p className="text-[11px] text-slate-600">{v.description}</p>
                    {v.example && v.example !== 'null' && (
                      <div className="flex items-center gap-1 mt-1">
                        <span className="text-[10px] text-slate-400">Example:</span>
                        <code className="text-[10px] bg-emerald-50 text-emerald-700 px-1.5 py-0.5 rounded">{v.example}</code>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Section>

            {/* Testing + Code Quality */}
            <div className="space-y-4">
              {blueprint.testing_strategy && (
                <Section title="Testing Strategy">
                  <div className="space-y-2 text-xs text-slate-700">
                    {blueprint.testing_strategy.unit && <div><b className="text-slate-500">Unit:</b> {blueprint.testing_strategy.unit}</div>}
                    {blueprint.testing_strategy.integration && <div><b className="text-slate-500">Integration:</b> {blueprint.testing_strategy.integration}</div>}
                    {blueprint.testing_strategy.e2e && <div><b className="text-slate-500">E2E:</b> {blueprint.testing_strategy.e2e}</div>}
                    {blueprint.testing_strategy.coverage_target && <div><b className="text-slate-500">Coverage Target:</b> {blueprint.testing_strategy.coverage_target}</div>}
                    {blueprint.testing_strategy.run_command && (
                      <div className="flex items-center gap-2 mt-2">
                        <pre className="flex-1 text-[10px] bg-slate-800 text-green-400 px-2 py-1.5 rounded font-mono">{blueprint.testing_strategy.run_command}</pre>
                        <CopyButton text={blueprint.testing_strategy.run_command} />
                      </div>
                    )}
                  </div>
                </Section>
              )}

              {(blueprint.code_quality_standards || []).length > 0 && (
                <Section title="Code Quality">
                  <div className="space-y-2">
                    {(blueprint.code_quality_standards || []).map((s: any, i: number) => {
                      const obj = typeof s === 'string' ? { tool: s, purpose: '', config_file: '' } : s;
                      return (
                        <div key={i} className="flex items-start gap-2 text-xs">
                          <span className="text-green-500 shrink-0 mt-0.5">✓</span>
                          <div>
                            <span className="font-medium">{obj.tool}</span>
                            {obj.purpose && <span className="text-slate-500"> — {obj.purpose}</span>}
                            {obj.config_file && <span className="text-[10px] font-mono text-slate-400 ml-2">({obj.config_file})</span>}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </Section>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════ SECURITY & PERF ═══════════════════════════════════ */}
      {tab === 'security' && (
        <div className="grid grid-cols-2 gap-4">
          <Section title="Security Considerations">
            <div className="space-y-3">
              {(blueprint.security_considerations || []).map((s: any, i: number) => {
                const obj = typeof s === 'string' ? { area: 'Security', description: s, severity: 'medium' } : s;
                return (
                  <div key={i} className="flex gap-3 items-start border border-slate-100 rounded-lg p-3">
                    <SeverityDot level={obj.severity || 'medium'} />
                    <div className="flex-1 min-w-0">
                      <span className="font-medium text-xs">{obj.area}</span>
                      <p className="text-[11px] text-slate-600 mt-0.5">{obj.description}</p>
                    </div>
                  </div>
                );
              })}
              {(blueprint.security_considerations || []).length === 0 && <p className="text-xs text-slate-400">No security data</p>}
            </div>
          </Section>

          <Section title="Performance Notes">
            <div className="space-y-3">
              {(blueprint.performance_notes || []).map((p: any, i: number) => {
                const obj = typeof p === 'string' ? { area: 'Performance', description: p, impact: 'medium' } : p;
                return (
                  <div key={i} className="flex gap-3 items-start border border-slate-100 rounded-lg p-3">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium shrink-0 ${obj.impact === 'high' ? 'bg-red-100 text-red-700' : obj.impact === 'low' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>{obj.impact}</span>
                    <div className="flex-1 min-w-0">
                      <span className="font-medium text-xs">{obj.area}</span>
                      <p className="text-[11px] text-slate-600 mt-0.5">{obj.description}</p>
                    </div>
                  </div>
                );
              })}
              {(blueprint.performance_notes || []).length === 0 && <p className="text-xs text-slate-400">No performance data</p>}
            </div>
          </Section>

          {(blueprint.gotchas || []).length > 0 && (
            <Section title="⚠️ Gotchas" className="col-span-2">
              <div className="space-y-2">
                {(blueprint.gotchas || []).map((g: string, i: number) => (
                  <div key={i} className="flex gap-2 text-xs bg-yellow-50/80 border border-yellow-100 rounded-lg p-3">
                    <span className="shrink-0">⚠️</span>
                    <span className="text-slate-700">{g}</span>
                  </div>
                ))}
              </div>
            </Section>
          )}
        </div>
      )}

      {/* ═══════════════════════════════════ WORKFLOWS ═══════════════════════════════════ */}
      {tab === 'workflows' && (
        <div className="space-y-4">
          {(blueprint.common_workflows || []).length > 0 ? (
            <Section title="Common Developer Workflows">
              <div className="space-y-2">
                {(blueprint.common_workflows || []).map((w: any, i: number) => (
                  <div key={i} className="border border-slate-100 rounded-lg overflow-hidden">
                    <button
                      onClick={() => setOpenWorkflow(openWorkflow === i ? -1 : i)}
                      className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-50 text-left"
                    >
                      <span className="font-medium text-sm flex items-center gap-2">
                        <span className="text-blue-500">📋</span> {w.title}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-slate-400">{(w.steps || []).length} steps</span>
                        <span className="text-slate-300">{openWorkflow === i ? '▲' : '▼'}</span>
                      </div>
                    </button>
                    {openWorkflow === i && (
                      <div className="px-4 pb-4 bg-slate-50/50 border-t border-slate-100 pt-3 space-y-2">
                        {(w.steps || []).map((step: string, j: number) => (
                          <div key={j} className="flex gap-3 items-start">
                            <div className="w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center text-[10px] font-bold shrink-0">{j + 1}</div>
                            <p className="text-xs text-slate-700 pt-1">{step}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Section>
          ) : (
            <p className="text-sm text-slate-400 text-center py-8">No workflow data available. Regenerate the blueprint for workflow guides.</p>
          )}

          {/* FAQ */}
          {(blueprint.faq || []).length > 0 && (
            <Section title="Frequently Asked Questions">
              <div className="space-y-3">
                {(blueprint.faq || []).map((f: any, i: number) => (
                  <div key={i} className="border-b border-slate-50 pb-3 last:border-0 last:pb-0">
                    <h4 className="font-medium text-xs text-slate-800 mb-1">Q: {f.question}</h4>
                    <p className="text-[11px] text-slate-600 leading-relaxed">{f.answer}</p>
                  </div>
                ))}
              </div>
            </Section>
          )}
        </div>
      )}
    </div>
  );
}
