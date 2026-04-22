interface DocumentationPanelProps {
  documentation: any;
  onGenerate: () => void;
  generating: boolean;
}

function MetaCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[22px] border border-black/5 bg-white p-4 shadow-[0_10px_24px_rgba(15,23,42,0.04)]">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">{label}</p>
      <p className="mt-2 break-words text-sm leading-6 text-slate-700">{value}</p>
    </div>
  );
}

export default function DocumentationPanel({ documentation, onGenerate, generating }: DocumentationPanelProps) {
  const sections = Array.isArray(documentation?.sections) ? documentation.sections : [];
  const hasDocs = Boolean(documentation?.available);

  if (!hasDocs) {
    return (
      <div className="devhub-readable flex min-h-[420px] items-center justify-center rounded-[28px] border border-dashed border-black/5 bg-white/70 text-center shadow-[0_18px_50px_rgba(15,23,42,0.06)]">
        <div className="max-w-2xl px-6">
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">Documentation</p>
          <h3 className="mt-3 text-2xl font-semibold text-slate-900">No codebase reference generated yet</h3>
          <p className="mt-3 text-sm leading-7 text-slate-500">
            Generate the first documentation run to create an evidence-backed codebase reference from the live workspace.
          </p>
          <button
            type="button"
            onClick={onGenerate}
            disabled={generating}
            className="mt-6 inline-flex items-center gap-2 rounded-full bg-black px-5 py-2.5 text-sm font-medium text-white shadow-[0_18px_40px_rgba(15,23,42,0.18)] transition hover:bg-slate-800 disabled:opacity-50"
          >
            {generating ? 'Generating...' : 'Generate Codebase Reference'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="devhub-readable space-y-5">
      <section className="rounded-[28px] border border-black/5 bg-[linear-gradient(145deg,rgba(255,255,255,0.98),rgba(248,250,252,0.9))] p-5 shadow-[0_22px_60px_rgba(15,23,42,0.08)]">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div className="max-w-3xl">
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">Documentation Run</p>
            <h3 className="mt-2 text-2xl font-semibold text-slate-900">Evidence-backed codebase reference</h3>
            <p className="mt-3 text-sm leading-7 text-slate-600">
              {documentation?.summary || 'The latest documentation run captured the current repository shape and wrote a structured codebase reference.'}
            </p>
          </div>
          <button
            type="button"
            onClick={onGenerate}
            disabled={generating}
            className="inline-flex items-center justify-center rounded-full bg-black px-5 py-2.5 text-sm font-medium text-white shadow-[0_18px_40px_rgba(15,23,42,0.18)] transition hover:bg-slate-800 disabled:opacity-50"
          >
            {generating ? 'Regenerating...' : 'Regenerate'}
          </button>
        </div>

        {documentation?.status === 'failed' && (
          <div className="mt-4 rounded-[22px] border border-red-100 bg-[#fff5f5] px-4 py-3 text-sm text-red-700">
            {documentation?.error || 'Documentation generation failed.'}
          </div>
        )}

        <div className="mt-5 grid gap-4 lg:grid-cols-2 xl:grid-cols-4">
          <MetaCard label="Status" value={documentation?.status || 'idle'} />
          <MetaCard label="Sections" value={String(sections.length)} />
          <MetaCard label="Fingerprint" value={documentation?.target_fingerprint || 'Not available'} />
          <MetaCard label="Output Path" value={documentation?.output_path || 'Stored in DevHub only'} />
        </div>
      </section>

      <section className="space-y-4">
        {sections.map((section: any) => (
          <article
            key={section.id || section.key}
            className="overflow-hidden rounded-[28px] border border-black/5 bg-white shadow-[0_20px_52px_rgba(15,23,42,0.08)]"
          >
            <div className="border-b border-black/5 px-5 py-4">
              <div className="flex flex-wrap items-center gap-2">
                <h4 className="text-base font-semibold text-slate-900">{section.title || 'Section'}</h4>
                <span className="rounded-full border border-black/5 bg-[#f8fafc] px-3 py-1 text-[11px] font-medium text-slate-500">
                  {section.status || 'completed'}
                </span>
              </div>
              {section.summary && <p className="mt-2 text-sm leading-6 text-slate-500">{section.summary}</p>}
            </div>
            <div className="space-y-4 p-5">
              <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded-[22px] bg-[#0f172a] p-4 text-xs leading-6 text-slate-100">
                {section.markdown || 'No section body available.'}
              </pre>

              {Array.isArray(section.evidence) && section.evidence.length > 0 && (
                <div className="rounded-[22px] border border-black/5 bg-[#fbfcfe] p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Evidence</p>
                  <div className="mt-3 space-y-2">
                    {section.evidence.map((item: any, index: number) => (
                      <div key={`${section.key}-evidence-${index}`} className="rounded-2xl bg-white px-3 py-2 shadow-[0_8px_20px_rgba(15,23,42,0.04)]">
                        <code className="break-all text-[11px] text-slate-700">{item.path || 'unknown file'}</code>
                        {item.note && <p className="mt-1 text-xs leading-5 text-slate-500">{item.note}</p>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}
