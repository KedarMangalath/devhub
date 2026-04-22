import { useState } from 'react';
import { Check, Minus, Moon, Plus, RotateCcw, Settings2, Sun, X } from 'lucide-react';
import { useDevhubSettings, type DevhubTheme } from '../theme';

type Props = {
  variant?: 'pill' | 'icon';
  label?: string;
};

const themeOptions: Array<{ value: DevhubTheme; label: string; icon: typeof Sun; note: string }> = [
  { value: 'light', label: 'Light', icon: Sun, note: 'White app, white workspace, light editor.' },
  { value: 'dark', label: 'Dark', icon: Moon, note: 'Black app, black workspace, dark editor.' },
];

export default function AppSettingsButton({ variant = 'pill', label = 'Settings' }: Props) {
  const [open, setOpen] = useState(false);
  const { settings, setSettings, resetSettings } = useDevhubSettings();

  const buttonClass = variant === 'icon'
    ? 'inline-flex h-8 w-8 items-center justify-center rounded-xl border border-black/5 bg-white/80 text-slate-600 shadow-[0_10px_24px_rgba(15,23,42,0.06)] transition hover:-translate-y-0.5 hover:bg-white'
    : 'inline-flex items-center justify-center gap-2 rounded-full border border-slate-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 shadow-[0_14px_28px_rgba(15,23,42,0.08)] transition hover:-translate-y-0.5';

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={buttonClass}
        title="DevHub settings"
      >
        <Settings2 className="h-4 w-4" />
        {variant === 'pill' && <span>{label}</span>}
      </button>

      {open && (
        <div className="devhub-settings-overlay fixed inset-0 z-[140] flex items-center justify-center px-4 py-4">
          <div className="absolute inset-0 bg-black/30 backdrop-blur-md" onClick={() => setOpen(false)} />
          <div className="devhub-settings-modal relative max-h-[calc(var(--app-vh)-2rem)] w-full max-w-3xl overflow-y-auto rounded-[28px] border p-0 shadow-[0_32px_90px_rgba(0,0,0,0.22)]">
            <div className="flex items-start justify-between gap-4 border-b px-6 py-6 lg:px-8">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.32em] opacity-60">DevHub Settings</p>
                <h2 className="mt-3 text-2xl font-semibold tracking-tight lg:text-3xl">Appearance and workspace</h2>
                <p className="mt-3 max-w-2xl text-sm leading-7 opacity-70">
                  These preferences apply across the dashboard, project pages, workspace, chat, preview chrome, code viewer, and terminal.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded-2xl border p-2 opacity-70 transition hover:opacity-100"
                aria-label="Close settings"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="grid gap-5 px-6 py-6 lg:px-8">
              <section className="devhub-settings-section rounded-2xl border p-4">
                <div className="flex flex-col gap-1">
                  <h3 className="text-sm font-semibold">Color Mode</h3>
                  <p className="text-xs leading-5 opacity-65">Pick a strict black or white theme. The workspace follows the same mode.</p>
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  {themeOptions.map((option) => {
                    const Icon = option.icon;
                    const active = settings.theme === option.value;
                    return (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => setSettings({ theme: option.value })}
                        className={`devhub-theme-option flex items-start gap-3 rounded-2xl border p-4 text-left transition ${active ? 'is-active' : ''}`}
                      >
                        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border">
                          <Icon className="h-4 w-4" />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="flex items-center gap-2 text-sm font-semibold">
                            {option.label}
                            {active && <Check className="h-4 w-4" />}
                          </span>
                          <span className="mt-1 block text-xs leading-5 opacity-65">{option.note}</span>
                        </span>
                      </button>
                    );
                  })}
                </div>
              </section>

              <section className="devhub-settings-section grid gap-4 rounded-2xl border p-4 md:grid-cols-[minmax(0,1fr)_14rem] md:items-center">
                <div>
                  <h3 className="text-sm font-semibold">Workspace Font Size</h3>
                  <p className="mt-1 text-xs leading-5 opacity-65">Controls the code editor and terminal font size.</p>
                </div>
                <div className="flex items-center justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setSettings({ editorFontSize: settings.editorFontSize - 1 })}
                    className="flex h-9 w-9 items-center justify-center rounded-xl border"
                    aria-label="Decrease editor font size"
                  >
                    <Minus className="h-4 w-4" />
                  </button>
                  <span className="min-w-14 rounded-xl border px-3 py-2 text-center text-sm font-semibold">{settings.editorFontSize}px</span>
                  <button
                    type="button"
                    onClick={() => setSettings({ editorFontSize: settings.editorFontSize + 1 })}
                    className="flex h-9 w-9 items-center justify-center rounded-xl border"
                    aria-label="Increase editor font size"
                  >
                    <Plus className="h-4 w-4" />
                  </button>
                </div>
              </section>

              <section className="devhub-settings-section grid gap-3 rounded-2xl border p-4 md:grid-cols-2">
                <button
                  type="button"
                  onClick={() => setSettings({ density: settings.density === 'comfortable' ? 'compact' : 'comfortable' })}
                  className="devhub-toggle-row rounded-2xl border p-4 text-left transition"
                >
                  <span className="text-sm font-semibold">Density</span>
                  <span className="mt-1 block text-xs leading-5 opacity-65">
                    {settings.density === 'compact' ? 'Compact spacing is on.' : 'Comfortable spacing is on.'}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => setSettings({ motion: settings.motion === 'normal' ? 'reduced' : 'normal' })}
                  className="devhub-toggle-row rounded-2xl border p-4 text-left transition"
                >
                  <span className="text-sm font-semibold">Motion</span>
                  <span className="mt-1 block text-xs leading-5 opacity-65">
                    {settings.motion === 'reduced' ? 'Reduced motion is on.' : 'Normal motion is on.'}
                  </span>
                </button>
              </section>
            </div>

            <div className="flex items-center justify-between gap-3 border-t px-6 py-4 lg:px-8">
              <button
                type="button"
                onClick={resetSettings}
                className="inline-flex items-center gap-2 rounded-2xl border px-4 py-2 text-sm font-semibold"
              >
                <RotateCcw className="h-4 w-4" />
                Reset
              </button>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded-2xl px-5 py-2.5 text-sm font-semibold"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

