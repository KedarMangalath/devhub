import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

export type DevhubTheme = 'light' | 'dark';
export type DevhubDensity = 'comfortable' | 'compact';
export type DevhubMotion = 'normal' | 'reduced';

export type DevhubSettings = {
  theme: DevhubTheme;
  density: DevhubDensity;
  motion: DevhubMotion;
  editorFontSize: number;
};

type DevhubSettingsContextValue = {
  settings: DevhubSettings;
  setSettings: (next: Partial<DevhubSettings>) => void;
  resetSettings: () => void;
};

const STORAGE_KEY = 'devhub.settings.v1';

const DEFAULT_SETTINGS: DevhubSettings = {
  theme: 'light',
  density: 'comfortable',
  motion: 'normal',
  editorFontSize: 13,
};

const DevhubSettingsContext = createContext<DevhubSettingsContextValue | null>(null);

function normalizeSettings(value: unknown): DevhubSettings {
  const raw = value && typeof value === 'object' ? value as Partial<DevhubSettings> : {};
  return {
    theme: raw.theme === 'dark' ? 'dark' : 'light',
    density: raw.density === 'compact' ? 'compact' : 'comfortable',
    motion: raw.motion === 'reduced' ? 'reduced' : 'normal',
    editorFontSize: Math.min(20, Math.max(11, Number(raw.editorFontSize) || DEFAULT_SETTINGS.editorFontSize)),
  };
}

function readStoredSettings(): DevhubSettings {
  if (typeof window === 'undefined') return DEFAULT_SETTINGS;
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return stored ? normalizeSettings(JSON.parse(stored)) : DEFAULT_SETTINGS;
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function DevhubSettingsProvider({ children }: { children: ReactNode }) {
  const [settings, updateSettings] = useState<DevhubSettings>(() => readStoredSettings());

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = settings.theme;
    root.dataset.density = settings.density;
    root.dataset.motion = settings.motion;
    root.classList.toggle('dark', settings.theme === 'dark');
    root.style.setProperty('--devhub-editor-font-size', `${settings.editorFontSize}px`);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  }, [settings]);

  const value = useMemo<DevhubSettingsContextValue>(() => ({
    settings,
    setSettings: (next) => updateSettings((current) => normalizeSettings({ ...current, ...next })),
    resetSettings: () => updateSettings(DEFAULT_SETTINGS),
  }), [settings]);

  return (
    <DevhubSettingsContext.Provider value={value}>
      {children}
    </DevhubSettingsContext.Provider>
  );
}

export function useDevhubSettings() {
  const value = useContext(DevhubSettingsContext);
  if (!value) {
    throw new Error('useDevhubSettings must be used inside DevhubSettingsProvider');
  }
  return value;
}
