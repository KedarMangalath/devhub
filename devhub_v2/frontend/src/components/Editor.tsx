import { useRef, useEffect } from 'react';
import Editor, { useMonaco } from '@monaco-editor/react';
import type { Monaco } from '@monaco-editor/react';

interface CodeEditorProps {
  language: string;
  value: string;
  onChange?: (value: string | undefined) => void;
  readOnly?: boolean;
}

export const CodeEditor = ({ language, value, onChange, readOnly = false }: CodeEditorProps) => {
  const monaco = useMonaco();
  const editorRef = useRef<any>(null);

  useEffect(() => {
    if (monaco) {
      // Define a custom theme that matches the white-dominant DevHub brand
      monaco.editor.defineTheme('devhubTheme', {
        base: 'vs', // light theme base
        inherit: true,
        rules: [
          { token: '', background: 'ffffff' },
          { token: 'comment', foreground: '9ca3af', fontStyle: 'italic' },
          { token: 'keyword', foreground: 'aa3bff' },
          { token: 'string', foreground: '059669' },
          { token: 'number', foreground: 'cd853f' },
          { token: 'identifier', foreground: '111827' },
        ],
        colors: {
          'editor.background': '#ffffff',
          'editor.foreground': '#111827',
          'editor.lineHighlightBackground': '#f3f4f6',
          'editorLineNumber.foreground': '#d1d5db',
          'editorIndentGuide.background': '#e5e7eb',
          'editorSuggestWidget.background': '#ffffff',
          'editorSuggestWidget.border': '#e5e7eb',
          'editorSuggestWidget.selectedBackground': '#f3f4f6',
        }
      });
      monaco.editor.setTheme('devhubTheme');
    }
  }, [monaco]);

  const handleEditorDidMount = (editor: any, _monacoInstance: Monaco) => {
    editorRef.current = editor;
  };

  return (
    <div className="w-full h-full rounded-lg overflow-hidden border border-slate-200">
      <Editor
        height="100%"
        language={language}
        value={value}
        onChange={onChange}
        onMount={handleEditorDidMount}
        theme="devhubTheme"
        options={{
          minimap: { enabled: false },
          fontSize: 14,
          fontFamily: "'Geist Mono', 'Consolas', monospace",
          roundedSelection: true,
          scrollBeyondLastLine: false,
          padding: { top: 16, bottom: 16 },
          readOnly: readOnly,
          cursorBlinking: 'smooth',
          cursorStyle: 'line',
          lineNumbersMinChars: 3,
        }}
      />
    </div>
  );
};
