import { useRef, useEffect } from 'react';
import Editor, { useMonaco } from '@monaco-editor/react';
import type { Monaco } from '@monaco-editor/react';
import { useDevhubSettings } from '../theme';

interface CodeEditorProps {
  language: string;
  value: string;
  onChange?: (value: string | undefined) => void;
  readOnly?: boolean;
}

const WORKSPACE_EDITOR_DARK_THEME = 'devhubWorkspaceDark';
const WORKSPACE_EDITOR_LIGHT_THEME = 'devhubWorkspaceLight';

const defineWorkspaceEditorTheme = (monacoInstance: Monaco) => {
  monacoInstance.editor.defineTheme(WORKSPACE_EDITOR_DARK_THEME, {
    base: 'vs-dark',
    inherit: true,
    rules: [
      { token: '', background: '101012', foreground: 'e8e4e6' },
      { token: 'comment', foreground: '8a7a80', fontStyle: 'italic' },
      { token: 'keyword', foreground: 'd6a1b1' },
      { token: 'string', foreground: 'c7b08a' },
      { token: 'number', foreground: 'd8a06c' },
      { token: 'identifier', foreground: 'e8e4e6' },
      { token: 'type', foreground: 'bda2ff' },
    ],
    colors: {
      'editor.background': '#101012',
      'editor.foreground': '#e8e4e6',
      'editor.lineHighlightBackground': '#1a1618',
      'editorLineNumber.foreground': '#62545a',
      'editorLineNumber.activeForeground': '#d6a1b1',
      'editorIndentGuide.background1': '#2a2327',
      'editorSuggestWidget.background': '#161214',
      'editorSuggestWidget.border': '#2c2227',
      'editorSuggestWidget.selectedBackground': '#2b1d22',
      'editorCursor.foreground': '#d6a1b1',
      'editor.selectionBackground': '#4a2d37',
      'editor.inactiveSelectionBackground': '#2b1d22',
    },
  });
  monacoInstance.editor.defineTheme(WORKSPACE_EDITOR_LIGHT_THEME, {
    base: 'vs',
    inherit: true,
    rules: [
      { token: '', background: 'ffffff', foreground: '0f172a' },
      { token: 'comment', foreground: '64748b', fontStyle: 'italic' },
      { token: 'keyword', foreground: '70434f' },
      { token: 'string', foreground: '8a5a1f' },
      { token: 'number', foreground: 'a85532' },
      { token: 'identifier', foreground: '0f172a' },
      { token: 'type', foreground: '365fa8' },
    ],
    colors: {
      'editor.background': '#ffffff',
      'editor.foreground': '#0f172a',
      'editor.lineHighlightBackground': '#f8fafc',
      'editorLineNumber.foreground': '#94a3b8',
      'editorLineNumber.activeForeground': '#70434f',
      'editorIndentGuide.background1': '#e5e7eb',
      'editorSuggestWidget.background': '#ffffff',
      'editorSuggestWidget.border': '#e5e7eb',
      'editorSuggestWidget.selectedBackground': '#f3f5f8',
      'editorCursor.foreground': '#70434f',
      'editor.selectionBackground': '#dbeafe',
      'editor.inactiveSelectionBackground': '#eef2ff',
    },
  });
};

export const CodeEditor = ({ language, value, onChange, readOnly = false }: CodeEditorProps) => {
  const { settings } = useDevhubSettings();
  const monaco = useMonaco();
  const editorRef = useRef<any>(null);
  const editorTheme = settings.theme === 'dark' ? WORKSPACE_EDITOR_DARK_THEME : WORKSPACE_EDITOR_LIGHT_THEME;

  useEffect(() => {
    if (monaco) {
      defineWorkspaceEditorTheme(monaco);
      monaco.editor.setTheme(editorTheme);
      window.requestAnimationFrame(() => editorRef.current?.layout());
    }
  }, [monaco, editorTheme]);

  const handleEditorWillMount = (monacoInstance: Monaco) => {
    defineWorkspaceEditorTheme(monacoInstance);
  };

  const handleEditorDidMount = (editor: any, monacoInstance: Monaco) => {
    editorRef.current = editor;
    defineWorkspaceEditorTheme(monacoInstance);
    monacoInstance.editor.setTheme(editorTheme);
    window.requestAnimationFrame(() => editor.layout());
  };

  return (
    <div className="devhub-monaco-editor h-full w-full overflow-hidden bg-[#101012]">
      <Editor
        height="100%"
        language={language}
        value={value}
        onChange={onChange}
        beforeMount={handleEditorWillMount}
        onMount={handleEditorDidMount}
        theme={editorTheme}
        options={{
          minimap: { enabled: false },
          fontSize: settings.editorFontSize,
          fontFamily: "'JetBrains Mono', 'Geist Mono', 'Consolas', monospace",
          roundedSelection: true,
          scrollBeyondLastLine: false,
          padding: { top: 18, bottom: 18 },
          readOnly: readOnly,
          cursorBlinking: 'smooth',
          cursorStyle: 'line',
          lineNumbersMinChars: 3,
        }}
      />
    </div>
  );
};
