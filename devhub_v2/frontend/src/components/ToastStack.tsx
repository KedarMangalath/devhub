import { AlertCircle, CheckCircle2, X } from 'lucide-react';

type ToastItem = {
  id: string;
  type: 'success' | 'error';
  text: string;
};

type ToastStackProps = {
  items: ToastItem[];
  onDismiss: (id: string) => void;
};

export default function ToastStack({ items, onDismiss }: ToastStackProps) {
  if (!items.length) return null;

  return (
    <div className="pointer-events-none fixed right-5 top-5 z-[90] flex w-[min(360px,calc(100vw-2rem))] flex-col gap-2" aria-live="polite" aria-atomic="true">
      {items.map((item) => {
        const success = item.type === 'success';
        return (
          <div
            key={item.id}
            className={`pointer-events-auto flex items-start gap-3 rounded-2xl border px-4 py-3 shadow-[0_18px_40px_rgba(15,23,42,0.12)] backdrop-blur-xl transition-all duration-200 ${
              success
                ? 'border-emerald-100/80 bg-white/92 text-slate-800'
                : 'border-rose-100/90 bg-white/94 text-slate-800'
            }`}
          >
            <div className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl ${success ? 'bg-emerald-50 text-emerald-600' : 'bg-rose-50 text-rose-600'}`}>
              {success ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                {success ? 'Success' : 'Error'}
              </p>
              <p className="mt-1 text-sm leading-6 text-slate-700">{item.text}</p>
            </div>
            <button
              type="button"
              onClick={() => onDismiss(item.id)}
              className="rounded-lg p-1.5 text-slate-300 transition hover:bg-slate-100 hover:text-slate-500"
              aria-label="Dismiss notification"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
