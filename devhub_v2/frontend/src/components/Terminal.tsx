import React, { useEffect, useRef } from 'react';
import { Terminal as Xterm } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';
import { useDevhubSettings } from '../theme';

interface TerminalProps {
  onInput?: (data: string) => void;
  outputStream?: string; // We'll pipe output here in a real app, or via imperative handle
}

export const Terminal = React.forwardRef<{ write: (data: string) => void; reset: (data?: string) => void; focus: () => void }, TerminalProps>(
  ({ onInput, outputStream }, ref) => {
    const { settings } = useDevhubSettings();
    const terminalRef = useRef<HTMLDivElement>(null);
    const xtermRef = useRef<Xterm | null>(null);
    const syncedOutputRef = useRef('');
    const localEchoBufferRef = useRef('');
    // Terminal is always dark — it's an IDE console, never light regardless of app theme
    const terminalTheme = { background: '#0a0a0c', foreground: '#e2e8f0', cursor: '#d9a4b2', selectionBackground: 'rgba(217,164,178,0.2)' };

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
        if (xtermRef.current) {
          if (data === '\r') {
            xtermRef.current.write('\r\n');
            localEchoBufferRef.current = '';
          } else if (data === '\u007f') {
            if (localEchoBufferRef.current.length > 0) {
              const nextBuffer = localEchoBufferRef.current.slice(0, -1);
              localEchoBufferRef.current = nextBuffer;
              xtermRef.current.write('\b \b');
            }
          } else if (data === '\u0003') {
            xtermRef.current.write('^C\r\n');
            localEchoBufferRef.current = '';
          } else if (/^[\x20-\x7E\t]+$/.test(data)) {
            xtermRef.current.write(data);
            localEchoBufferRef.current += data;
          }
        }
        if (onInput) onInput(data);
      });

      xtermRef.current = xterm;
      syncedOutputRef.current = '';

      const handleResize = () => { try { fitAddon.fit(); } catch {} };
      window.addEventListener('resize', handleResize);

      const ro = new ResizeObserver(handleResize);
      ro.observe(terminalRef.current);

      xterm.focus();

      return () => {
        window.removeEventListener('resize', handleResize);
        ro.disconnect();
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
        if (!xtermRef.current || !data) return;
        xtermRef.current.write(data);
        syncedOutputRef.current += data;
      },
      reset: (data = '') => {
        if (!xtermRef.current) return;
        xtermRef.current.reset();
        syncedOutputRef.current = '';
        localEchoBufferRef.current = '';
        if (data) {
          xtermRef.current.write(data);
          syncedOutputRef.current = data;
        }
      },
      focus: () => {
        xtermRef.current?.focus();
      },
    }));

    useEffect(() => {
      if (typeof outputStream !== 'string' || !xtermRef.current) return;
      if (outputStream.startsWith(syncedOutputRef.current)) {
        const delta = outputStream.slice(syncedOutputRef.current.length);
        if (delta) xtermRef.current.write(delta);
      } else {
        xtermRef.current.reset();
        localEchoBufferRef.current = '';
        if (outputStream) xtermRef.current.write(outputStream);
      }
      syncedOutputRef.current = outputStream;
    }, [outputStream]);

    return (
      <div 
        ref={terminalRef} 
        onClick={() => xtermRef.current?.focus()}
        className="devhub-terminal w-full h-full rounded-lg overflow-hidden bg-[#08060d] p-2"
      />
    );
  }
);

Terminal.displayName = 'Terminal';
