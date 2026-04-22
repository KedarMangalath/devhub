import React, { useEffect, useRef } from 'react';
import { Terminal as Xterm } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';
import { useDevhubSettings } from '../theme';

interface TerminalProps {
  onInput?: (data: string) => void;
  outputStream?: string; // We'll pipe output here in a real app, or via imperative handle
}

export const Terminal = React.forwardRef<{ write: (data: string) => void }, TerminalProps>(
  ({ onInput, outputStream }, ref) => {
    const { settings } = useDevhubSettings();
    const terminalRef = useRef<HTMLDivElement>(null);
    const xtermRef = useRef<Xterm | null>(null);
    const terminalTheme = settings.theme === 'dark'
      ? { background: '#000000', foreground: '#f5f5f5', cursor: '#d9a4b2' }
      : { background: '#ffffff', foreground: '#0f172a', cursor: '#70434f' };

    useEffect(() => {
      if (!terminalRef.current) return;

      const xterm = new Xterm({
        cursorBlink: true,
        fontSize: settings.editorFontSize,
        fontFamily: 'Consolas, "Courier New", monospace',
        theme: terminalTheme,
      });

      const fitAddon = new FitAddon();
      xterm.loadAddon(fitAddon);
      xterm.open(terminalRef.current);
      fitAddon.fit();

      xterm.onData((data) => {
        if (onInput) onInput(data);
      });

      xtermRef.current = xterm;

      const handleResize = () => fitAddon.fit();
      window.addEventListener('resize', handleResize);

      // Initial greeting
      xterm.writeln('\x1b[1;35mDevHub v2 Terminal\x1b[0m');
      xterm.writeln('Connected to sandboxed environment.');
      xterm.write('\r\n$ ');

      return () => {
        window.removeEventListener('resize', handleResize);
        xterm.dispose();
      };
    }, []);

    useEffect(() => {
      if (!xtermRef.current) return;
      xtermRef.current.options.theme = terminalTheme;
      xtermRef.current.options.fontSize = settings.editorFontSize;
    }, [settings.editorFontSize, settings.theme]);

    React.useImperativeHandle(ref, () => ({
      write: (data: string) => {
        xtermRef.current?.write(data);
      }
    }));

    // If we receive stream updates via props (though refs are usually better for streams)
    useEffect(() => {
      if (outputStream && xtermRef.current) {
        xtermRef.current.write(outputStream);
      }
    }, [outputStream]);

    return (
      <div 
        ref={terminalRef} 
        className="devhub-terminal w-full h-full rounded-lg overflow-hidden bg-[#08060d] p-2"
      />
    );
  }
);

Terminal.displayName = 'Terminal';
