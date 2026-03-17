import { useEffect, useRef, useState } from 'react';

interface Props {
  chart: string;
  id?: string;
}

/**
 * Renders a Mermaid diagram by loading the Mermaid library from CDN
 * and rendering the provided chart string into SVG.
 */
export default function MermaidDiagram({ chart, id = 'mermaid' }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string>('');
  const [error, setError] = useState<string>('');

  useEffect(() => {
    if (!chart || !chart.trim()) {
      setSvg('');
      return;
    }

    let cancelled = false;

    const renderChart = async () => {
      try {
        // Dynamically import mermaid from CDN if not already loaded
        if (!(window as any).mermaid) {
          await new Promise<void>((resolve, reject) => {
            // Check if script is already being loaded
            const existing = document.querySelector('script[data-mermaid-cdn]');
            if (existing) {
              existing.addEventListener('load', () => resolve());
              if ((window as any).mermaid) resolve();
              return;
            }
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js';
            script.setAttribute('data-mermaid-cdn', 'true');
            script.onload = () => resolve();
            script.onerror = () => reject(new Error('Failed to load Mermaid library'));
            document.head.appendChild(script);
          });
        }

        const mermaid = (window as any).mermaid;
        mermaid.initialize({
          startOnLoad: false,
          theme: 'neutral',
          securityLevel: 'loose',
          flowchart: { useMaxWidth: true, htmlLabels: true, curve: 'basis' },
          er: { useMaxWidth: true },
        });

        // Clean chart text — fix escaped newlines from JSON
        let cleanChart = chart
          .replace(/\\n/g, '\n')
          .replace(/\\t/g, '  ')
          .trim();

        const uniqueId = `mermaid-${id}-${Date.now()}`;
        const { svg: renderedSvg } = await mermaid.render(uniqueId, cleanChart);

        if (!cancelled) {
          setSvg(renderedSvg);
          setError('');
        }
      } catch (err: any) {
        if (!cancelled) {
          setError(err?.message || 'Diagram render failed');
          setSvg('');
        }
      }
    };

    renderChart();
    return () => { cancelled = true; };
  }, [chart, id]);

  if (!chart || !chart.trim()) {
    return (
      <div className="bg-slate-50 border border-dashed border-slate-200 rounded-lg p-6 text-center text-xs text-slate-400">
        No diagram data available
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-xs text-red-600 font-medium mb-1">Diagram render error</p>
        <p className="text-[10px] text-red-500">{error}</p>
        <details className="mt-2">
          <summary className="text-[10px] text-slate-400 cursor-pointer">Raw diagram code</summary>
          <pre className="mt-1 text-[10px] bg-slate-800 text-green-400 p-2 rounded overflow-auto max-h-40 whitespace-pre-wrap">{chart}</pre>
        </details>
      </div>
    );
  }

  if (!svg) {
    return (
      <div className="bg-slate-50 rounded-lg p-8 text-center">
        <div className="inline-block w-5 h-5 border-2 border-slate-300 border-t-black rounded-full animate-spin" />
        <p className="text-xs text-slate-400 mt-2">Rendering diagram…</p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="bg-white rounded-lg border border-slate-200 p-4 overflow-auto"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
