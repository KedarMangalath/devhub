import { useState } from 'react';
import { ArrowLeft, ArrowRight, CheckCircle2, Loader2, Wand2, X } from 'lucide-react';

const API = 'http://localhost:8000/api';

type Step = 'basics' | 'instructions' | 'confirm' | 'done';

type Props = {
  isWorkspaceMode?: boolean;
  onClose: () => void;
  onCreated?: (slug: string) => void;
};

const STEP_ORDER: Step[] = ['basics', 'instructions', 'confirm', 'done'];

const OUTPUT_TYPES = [
  { value: 'text', label: 'Text / Code' },
  { value: 'pdf', label: 'PDF file' },
  { value: 'docx', label: 'Word document' },
  { value: 'xlsx', label: 'Excel spreadsheet' },
  { value: 'pptx', label: 'PowerPoint presentation' },
  { value: 'html', label: 'HTML artifact' },
  { value: 'gif', label: 'Animated GIF' },
];

function generateSkillBody(name: string, description: string, triggers: string, outputType: string, instructions: string): string {
  const outputNote = outputType !== 'text'
    ? `\n## Output\nProduce a ${outputType} file. Save it to the workspace directory with an appropriate filename.\n`
    : '';
  const triggerNote = triggers
    ? `\n## When to use\nThis skill activates when the user: ${triggers}\n`
    : '';
  return `# ${name}\n${triggerNote}${outputNote}\n## Instructions\n${instructions || 'Follow the user request precisely.'}\n`;
}

export default function SkillCreatorWizard({ isWorkspaceMode, onClose, onCreated }: Props) {
  const [step, setStep] = useState<Step>('basics');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [triggers, setTriggers] = useState('');
  const [outputType, setOutputType] = useState('text');
  const [instructions, setInstructions] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [createdSlug, setCreatedSlug] = useState('');

  const bg = isWorkspaceMode ? 'bg-[#0f0f10]' : 'bg-white';
  const border = isWorkspaceMode ? 'border-white/8' : 'border-slate-200';
  const text = isWorkspaceMode ? 'text-[#dbe4ee]' : 'text-slate-800';
  const sub = isWorkspaceMode ? 'text-[#94a3b8]' : 'text-slate-500';
  const inputBg = isWorkspaceMode ? 'bg-[#1a1a1c] border-white/10 text-[#dbe4ee] placeholder-[#4a5568]' : 'bg-white border-slate-300 text-slate-800 placeholder-slate-400';
  const accent = isWorkspaceMode ? 'bg-[#70434f] hover:bg-[#8c5462] text-white' : 'bg-[#8c5462] hover:bg-[#70434f] text-white';
  const labelCls = `block text-[11px] font-semibold uppercase tracking-[0.14em] mb-1.5 ${sub}`;
  const inputCls = `w-full rounded-xl border px-3 py-2 text-[12px] outline-none focus:ring-1 focus:ring-[#d9a4b2]/50 transition ${inputBg}`;

  const stepIndex = STEP_ORDER.indexOf(step);

  const canAdvance = () => {
    if (step === 'basics') return name.trim().length > 0 && description.trim().length > 0;
    if (step === 'instructions') return true;
    if (step === 'confirm') return true;
    return false;
  };

  const advance = () => {
    const next = STEP_ORDER[stepIndex + 1];
    if (next) setStep(next);
  };

  const back = () => {
    const prev = STEP_ORDER[stepIndex - 1];
    if (prev) setStep(prev);
  };

  const submit = async () => {
    setSubmitting(true);
    setError('');
    try {
      const body = generateSkillBody(name, description, triggers, outputType, instructions);
      const r = await fetch(`${API}/skills/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim(), description: description.trim(), body }),
      });
      const d = await r.json();
      if (!r.ok || d.error) throw new Error(d.error || 'Failed to create skill');
      setCreatedSlug(d.skill?.slug || '');
      setStep('done');
      onCreated?.(d.skill?.slug || '');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create skill');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={`flex h-full flex-col overflow-hidden rounded-2xl border shadow-xl ${bg} ${border}`}>
      {/* Header */}
      <div className={`flex items-center justify-between border-b px-4 py-3 ${border}`}>
        <div className="flex items-center gap-2">
          <Wand2 className={`h-4 w-4 ${isWorkspaceMode ? 'text-[#d9a4b2]' : 'text-[#8c5462]'}`} />
          <span className={`text-[13px] font-semibold ${text}`}>Create New Skill</span>
        </div>
        <button type="button" onClick={onClose} className={`rounded-xl p-1.5 transition ${isWorkspaceMode ? 'hover:bg-white/10 text-[#94a3b8]' : 'hover:bg-slate-100 text-slate-500'}`}>
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Step indicator */}
      {step !== 'done' && (
        <div className={`flex items-center gap-1 border-b px-4 py-2 ${border}`}>
          {(['basics', 'instructions', 'confirm'] as Step[]).map((s, i) => (
            <div key={s} className="flex items-center gap-1">
              <div className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold transition ${
                STEP_ORDER.indexOf(s) < stepIndex
                  ? (isWorkspaceMode ? 'bg-[#70434f] text-white' : 'bg-[#8c5462] text-white')
                  : s === step
                    ? (isWorkspaceMode ? 'bg-[#d9a4b2]/30 text-[#d9a4b2]' : 'bg-[#f5ecf0] text-[#8c5462]')
                    : (isWorkspaceMode ? 'bg-white/5 text-[#64748b]' : 'bg-slate-100 text-slate-400')
              }`}>{i + 1}</div>
              {i < 2 && <div className={`h-px w-8 ${isWorkspaceMode ? 'bg-white/10' : 'bg-slate-200'}`} />}
            </div>
          ))}
          <span className={`ml-2 text-[11px] ${sub}`}>
            {step === 'basics' ? 'Name & Description' : step === 'instructions' ? 'Instructions' : 'Review'}
          </span>
        </div>
      )}

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">

        {step === 'basics' && (
          <>
            <div>
              <label className={labelCls}>Skill Name *</label>
              <input
                className={inputCls}
                placeholder="e.g. invoice-generator"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              <p className={`mt-1 text-[10px] ${sub}`}>Use lowercase letters and hyphens.</p>
            </div>
            <div>
              <label className={labelCls}>Description (used for auto-detection) *</label>
              <textarea
                className={`${inputCls} resize-none`}
                rows={3}
                placeholder="Use this skill when the user wants to generate invoices, billing documents, or payment summaries…"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
              <p className={`mt-1 text-[10px] ${sub}`}>Be specific. This text is what the AI reads to decide when to activate your skill.</p>
            </div>
            <div>
              <label className={labelCls}>Trigger phrases (optional)</label>
              <input
                className={inputCls}
                placeholder="invoice, billing, payment, receipt"
                value={triggers}
                onChange={(e) => setTriggers(e.target.value)}
              />
              <p className={`mt-1 text-[10px] ${sub}`}>Comma-separated keywords that should activate this skill.</p>
            </div>
            <div>
              <label className={labelCls}>Output type</label>
              <select
                className={`${inputCls} cursor-pointer`}
                value={outputType}
                onChange={(e) => setOutputType(e.target.value)}
              >
                {OUTPUT_TYPES.map((ot) => (
                  <option key={ot.value} value={ot.value}>{ot.label}</option>
                ))}
              </select>
            </div>
          </>
        )}

        {step === 'instructions' && (
          <>
            <div>
              <label className={labelCls}>Skill Instructions</label>
              <textarea
                className={`${inputCls} resize-y`}
                rows={12}
                placeholder={`Describe exactly what the AI should do when this skill is active.\n\nExample:\n- Always start by asking for the customer name and invoice date.\n- Generate a professional PDF invoice using reportlab.\n- Include line items, subtotal, tax (10%), and total.\n- Save as invoice_<date>.pdf in the workspace.`}
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
              />
              <p className={`mt-1 text-[10px] ${sub}`}>Be specific and action-oriented. Explain the "why" behind each rule, not just the "what".</p>
            </div>
            <div className={`rounded-xl border px-3 py-2.5 text-[11px] leading-6 ${isWorkspaceMode ? 'border-white/8 bg-white/3 text-[#94a3b8]' : 'border-slate-200 bg-slate-50 text-slate-500'}`}>
              <strong className={text}>Tip:</strong> Great skill instructions explain context, not just rules. Instead of "ALWAYS include the date", write "Include the date because invoices without dates are legally ambiguous."
            </div>
          </>
        )}

        {step === 'confirm' && (
          <>
            <div className={`rounded-xl border px-4 py-4 space-y-3 ${isWorkspaceMode ? 'border-white/8 bg-[#161618]' : 'border-slate-200 bg-slate-50'}`}>
              <div>
                <p className={`text-[10px] font-semibold uppercase tracking-[0.14em] ${sub}`}>Name</p>
                <p className={`mt-0.5 text-[13px] font-semibold ${text}`}>{name}</p>
              </div>
              <div>
                <p className={`text-[10px] font-semibold uppercase tracking-[0.14em] ${sub}`}>Description</p>
                <p className={`mt-0.5 text-[12px] leading-5 ${text}`}>{description}</p>
              </div>
              {triggers && (
                <div>
                  <p className={`text-[10px] font-semibold uppercase tracking-[0.14em] ${sub}`}>Triggers</p>
                  <p className={`mt-0.5 text-[12px] ${text}`}>{triggers}</p>
                </div>
              )}
              <div>
                <p className={`text-[10px] font-semibold uppercase tracking-[0.14em] ${sub}`}>Output</p>
                <p className={`mt-0.5 text-[12px] ${text}`}>{OUTPUT_TYPES.find((o) => o.value === outputType)?.label || outputType}</p>
              </div>
              {instructions && (
                <div>
                  <p className={`text-[10px] font-semibold uppercase tracking-[0.14em] ${sub}`}>Instructions preview</p>
                  <pre className={`mt-0.5 max-h-32 overflow-y-auto whitespace-pre-wrap text-[11px] leading-5 ${sub}`}>{instructions.slice(0, 400)}{instructions.length > 400 ? '…' : ''}</pre>
                </div>
              )}
            </div>
            {error && <p className="text-[12px] text-red-400">{error}</p>}
          </>
        )}

        {step === 'done' && (
          <div className="flex flex-col items-center justify-center py-8 text-center gap-3">
            <CheckCircle2 className={`h-10 w-10 ${isWorkspaceMode ? 'text-emerald-400' : 'text-emerald-600'}`} />
            <p className={`text-[14px] font-semibold ${text}`}>Skill Created!</p>
            <p className={`text-[12px] ${sub}`}>
              <strong>{name}</strong> is now available. It will auto-activate when your messages match its description.
            </p>
            <button type="button" onClick={onClose} className={`mt-2 rounded-xl px-4 py-2 text-[12px] font-semibold transition ${accent}`}>
              Close
            </button>
          </div>
        )}
      </div>

      {/* Footer nav */}
      {step !== 'done' && (
        <div className={`flex items-center justify-between border-t px-4 py-3 ${border}`}>
          <button
            type="button"
            onClick={back}
            disabled={stepIndex === 0}
            className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-2 text-[12px] font-medium transition disabled:opacity-30 ${isWorkspaceMode ? 'border-white/10 bg-white/5 text-white hover:bg-white/10' : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'}`}
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back
          </button>
          {step !== 'confirm' ? (
            <button
              type="button"
              onClick={advance}
              disabled={!canAdvance()}
              className={`inline-flex items-center gap-1.5 rounded-xl px-4 py-2 text-[12px] font-semibold transition disabled:opacity-40 ${accent}`}
            >
              Next
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          ) : (
            <button
              type="button"
              onClick={submit}
              disabled={submitting || !canAdvance()}
              className={`inline-flex items-center gap-1.5 rounded-xl px-4 py-2 text-[12px] font-semibold transition disabled:opacity-40 ${accent}`}
            >
              {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Wand2 className="h-3.5 w-3.5" />}
              {submitting ? 'Creating…' : 'Create Skill'}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
