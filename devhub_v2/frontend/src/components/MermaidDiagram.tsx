import { useEffect, useRef, useState } from 'react';

interface Props {
  chart: string;
  id?: string;
}

function normalizeMermaid(chart: string) {
  let cleanChart = (chart || '')
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '  ')
    .trim();

  if (/^erDiagram/i.test(cleanChart)) {
    cleanChart = cleanChart.replace(/^erDiagram\s*;?/i, 'erDiagram\n').replace(/;\s*/g, '\n');
  } else if (/^sequenceDiagram/i.test(cleanChart)) {
    cleanChart = cleanChart.replace(/^sequenceDiagram\s*;?/i, 'sequenceDiagram\n').replace(/;\s*/g, '\n');
  } else if (/^(graph|flowchart)\s/i.test(cleanChart)) {
    cleanChart = cleanChart.replace(/;\s*/g, '\n');
  }

  return cleanChart;
}

export default function MermaidDiagram({ chart, id = 'mermaid' }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!chart || !chart.trim()) {
      setSvg('');
      setError('');
      return;
    }

    let cancelled = false;

    const renderChart = async () => {
      try {
        if (!(window as any).mermaid) {
          await new Promise<void>((resolve, reject) => {
            const existing = document.querySelector('script[data-mermaid-cdn]');
            if (existing) {
              existing.addEventListener('load', () => resolve(), { once: true });
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

        const cleanChart = normalizeMermaid(chart);
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
    return () => {
      cancelled = true;
    };
  }, [chart, id]);

  if (!chart || !chart.trim()) {
    return (
      <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-6 text-center text-xs text-slate-400">
        No diagram data available
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4">
        <p className="mb-1 text-xs font-medium text-red-600">Diagram render error</p>
        <p className="text-[10px] text-red-500">{error}</p>
        <details className="mt-2">
          <summary className="cursor-pointer text-[10px] text-slate-400">Raw diagram code</summary>
          <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-slate-800 p-2 text-[10px] text-green-400">{chart}</pre>
        </details>
      </div>
    );
  }

  if (!svg) {
    return (
      <div className="rounded-lg bg-slate-50 p-8 text-center">
        <div className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-black" />
        <p className="mt-2 text-xs text-slate-400">Rendering diagram...</p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="overflow-auto rounded-lg border border-slate-200 bg-white p-4"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
