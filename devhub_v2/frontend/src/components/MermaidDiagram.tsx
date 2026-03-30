import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

interface Props {
  chart: string;
  id?: string;
}

interface DiagramSize {
  width: number;
  height: number;
}

interface SequenceMessage {
  from: string;
  to: string;
  label: string;
  dashed: boolean;
}

interface SequenceBlock {
  type: string;
  label: string;
  start: number;
  end: number;
}

interface SequenceDiagramModel {
  participants: string[];
  messages: SequenceMessage[];
  blocks: SequenceBlock[];
}

interface GraphNodeModel {
  id: string;
  label: string;
  shape: 'rect' | 'round' | 'database' | 'circle' | 'subroutine' | 'decision';
  order: number;
}

interface GraphEdgeModel {
  from: string;
  to: string;
  label: string;
}

interface GraphDiagramModel {
  direction: 'TD' | 'LR';
  nodes: GraphNodeModel[];
  edges: GraphEdgeModel[];
  layers: string[][];
}

interface GraphLayoutNode extends GraphNodeModel {
  x: number;
  y: number;
  width: number;
  height: number;
  lines: string[];
}

interface GraphDiagramLayout {
  size: DiagramSize;
  nodes: GraphLayoutNode[];
}

interface GraphConnectionPoints {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  labelX: number;
  labelY: number;
  path: string;
}

const SEQUENCE_ARROW_TOKENS = ['<<->>', '<<->', '-->>', '->>', '<<--', '-->', '->', '--x', 'x--'];

let mermaidLoadPromise: Promise<any> | null = null;
let mermaidRenderQueue: Promise<unknown> = Promise.resolve();
let mermaidInstance: any = null;
let mermaidConfigured = false;

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function enqueueMermaidRender<T>(job: () => Promise<T>) {
  const nextJob = mermaidRenderQueue.then(job, job);
  mermaidRenderQueue = nextJob.then(() => undefined, () => undefined);
  return nextJob;
}

async function loadMermaid() {
  if (mermaidInstance) {
    return mermaidInstance;
  }

  if (!mermaidLoadPromise) {
    // Use Mermaid's bundled browser ESM build instead of the package-root core
    // entry. The core entry pulls bare "dompurify" in a way that can surface
    // the factory function instead of the bound browser sanitizer under Vite,
    // which breaks flowchart rendering while sequence/ER diagrams still work.
    mermaidLoadPromise = import('mermaid/dist/mermaid.esm.mjs')
      .then((module) => {
        mermaidInstance = module?.default ?? module;
        if (!mermaidInstance) {
          throw new Error('Failed to load Mermaid library');
        }
        return mermaidInstance;
      })
      .catch((error) => {
        mermaidLoadPromise = null;
        throw error;
      });
  }

  return mermaidLoadPromise;
}

function initializeMermaid(mermaid: any) {
  if (mermaidConfigured) {
    return;
  }

  mermaid.parseError = () => undefined;
  mermaid.initialize({
    startOnLoad: false,
    theme: 'neutral',
    securityLevel: 'loose',
    // Mermaid's HTML-label flowchart renderer is brittle in our runtime and
    // can fail with DOMPurify sanitizer errors. Plain SVG labels are more
    // stable and still render the blueprint graphs correctly.
    flowchart: { useMaxWidth: true, htmlLabels: false, curve: 'basis' },
    er: { useMaxWidth: true },
  });
  mermaidConfigured = true;
}

async function renderMermaidViaDom(mermaid: any, chart: string, id: string) {
  const host = document.createElement('div');
  host.style.position = 'fixed';
  host.style.left = '-10000px';
  host.style.top = '-10000px';
  host.style.width = '1px';
  host.style.height = '1px';
  host.style.overflow = 'hidden';

  const node = document.createElement('div');
  node.className = 'mermaid';
  node.id = `mermaid-dom-${id}-${Date.now()}`;
  node.textContent = chart;
  host.appendChild(node);
  document.body.appendChild(host);

  try {
    await mermaid.run({ nodes: [node], suppressErrors: true });
    return node.innerHTML || '';
  } finally {
    host.remove();
  }
}

function normalizeMermaid(chart: string) {
  let cleanChart = (chart || '')
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '  ')
    .trim();

  const unescapeHtml = (value: string) =>
    (value || '')
      .replace(/&lt;/gi, '<')
      .replace(/&gt;/gi, '>')
      .replace(/&amp;/gi, '&')
      .replace(/&quot;/gi, '"')
      .replace(/&#39;/gi, "'");

  const escapeSequenceLabelText = (value: string) =>
    unescapeHtml(value || '')
      .replace(/\\n/g, ' newline ')
      .replace(/\r/g, '')
      .replace(/\n/g, ' newline ')
      .replace(/<([^>]+)>/g, ' $1 ')
      .replace(/\[([^\]]+)\]/g, ' $1 ')
      .replace(/[{}()]/g, ' ')
      .replace(/&/g, ' and ')
      .replace(/["'`]/g, '')
      .replace(/[^A-Za-z0-9 _-]+/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();

  const escapeGraphLabelText = (value: string) =>
    unescapeHtml(value || '')
      .replace(/\\n/g, ' ')
      .replace(/\r/g, ' ')
      .replace(/\n/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .replace(/\\/g, '\\\\')
      .replace(/"/g, '\\"');

  const rewriteGraphLabel = (match: string, _id: string, _label: string, groups?: { id?: string; label?: string }, template?: string) => {
    const nodeId = (groups?.id || '').trim();
    const rawLabel = (groups?.label || '').trim();
    if (!nodeId || !rawLabel || (/^".*"$/.test(rawLabel))) {
      return match;
    }
    const safeLabel = escapeGraphLabelText(rawLabel);
    return String(template || '')
      .replace('{id}', nodeId)
      .replace('{label}', safeLabel);
  };

  const normalizeGraphLine = (line: string) => {
    const rewrites: Array<{ pattern: RegExp; template: string }> = [
      { pattern: /(?<id>\b[A-Za-z][A-Za-z0-9_]*\b)\[\((?<label>[^"\n][^)\n]*?)\)\]/g, template: '{id}[("{label}")]' },
      { pattern: /(?<id>\b[A-Za-z][A-Za-z0-9_]*\b)\[\[(?<label>[^"\n][^\]\n]*?)\]\]/g, template: '{id}[["{label}"]]' },
      { pattern: /(?<id>\b[A-Za-z][A-Za-z0-9_]*\b)\(\((?<label>[^"\n][^)\n]*?)\)\)/g, template: '{id}(("{label}"))' },
      { pattern: /(?<id>\b[A-Za-z][A-Za-z0-9_]*\b)\(\[(?<label>[^"\n][^\]\n]*?)\]\)/g, template: '{id}(["{label}"])' },
      { pattern: /(?<id>\b[A-Za-z][A-Za-z0-9_]*\b)\[(?<label>[^"\[(\n][^\]\n]*?)\]/g, template: '{id}["{label}"]' },
      { pattern: /(?<id>\b[A-Za-z][A-Za-z0-9_]*\b)\((?<label>[^"\[(\n][^)\n]*?)\)/g, template: '{id}("{label}")' },
      { pattern: /(?<id>\b[A-Za-z][A-Za-z0-9_]*\b)\{(?<label>[^"\n][^}\n]*?)\}/g, template: '{id}{{"{label}"}}' },
    ];

    let normalized = line || '';
    for (const rewrite of rewrites) {
      normalized = normalized.replace(
        rewrite.pattern,
        (match, id, label, _offset, _input, groups) => rewriteGraphLabel(match, id, label, groups, rewrite.template),
      );
    }
    return normalized;
  };

  const startsSequenceStatement = (line: string) => {
    const stripped = (line || '').trim();
    if (!stripped) return false;
    if (/^sequenceDiagram$/i.test(stripped)) return true;
    if (/^(participant|actor|note|activate|deactivate|autonumber|title|link|box|end|alt|else|opt|loop|par|and|critical|break|rect)\b/i.test(stripped)) {
      return true;
    }
    return /^[A-Za-z0-9_.()[\]`"'/-]+\s*(?:-->>|->>|-->|->|<<--|<<->>|<<->|--x|x--)/.test(stripped);
  };

  if (/^erDiagram/i.test(cleanChart)) {
    cleanChart = cleanChart.replace(/^erDiagram\s*;?/i, 'erDiagram\n').replace(/;\s*/g, '\n');
  } else if (/^sequenceDiagram/i.test(cleanChart)) {
    cleanChart = cleanChart.replace(/^sequenceDiagram\s*;?/i, 'sequenceDiagram\n').replace(/;\s*/g, '\n');
    const rawLines = cleanChart
      .split('\n')
      .map((line) => line.trimEnd())
      .filter((line) => line.trim());
    const mergedLines: string[] = [];
    for (const line of rawLines) {
      const stripped = line.trim();
      if (!mergedLines.length || startsSequenceStatement(stripped)) {
        mergedLines.push(stripped);
      } else {
        mergedLines[mergedLines.length - 1] = `${mergedLines[mergedLines.length - 1]}\\n${stripped}`;
      }
    }
    cleanChart = mergedLines
      .map((line) => {
        if (/^sequenceDiagram$/i.test(line.trim())) return 'sequenceDiagram';
        if (line.includes(':') && /(?:-->>|->>|-->|->|<<--|<<->>|<<->|--x|x--)/.test(line)) {
          const colonIndex = line.indexOf(':');
          const prefix = line.slice(0, colonIndex);
          const label = line.slice(colonIndex + 1).trim();
          return `${prefix}: ${escapeSequenceLabelText(label)}`;
        }
        return line;
      })
      .join('\n');
  } else if (/^(graph|flowchart)\s/i.test(cleanChart)) {
    cleanChart = cleanChart
      .replace(/;\s*/g, '\n')
      .split('\n')
      .map((line) => line.trimEnd())
      .filter((line) => line.trim())
      .map((line) => normalizeGraphLine(line))
      .join('\n');
  }

  return cleanChart;
}

function hasMermaidErrorMarkup(svg: string) {
  const normalized = (svg || '').toLowerCase();
  return (
    normalized.includes('syntax error in text') ||
    normalized.includes('mermaid version') ||
    normalized.includes('error-icon') ||
    normalized.includes('parse error')
  );
}

function extractSvgDimensions(svg: string): DiagramSize | null {
  const viewBoxMatch = svg.match(/viewBox=["'][^"']*?(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)["']/i);
  if (viewBoxMatch) {
    return {
      width: Number(viewBoxMatch[3]),
      height: Number(viewBoxMatch[4]),
    };
  }

  const widthMatch = svg.match(/width=["'](\d+(?:\.\d+)?)["']/i);
  const heightMatch = svg.match(/height=["'](\d+(?:\.\d+)?)["']/i);
  if (widthMatch && heightMatch) {
    return {
      width: Number(widthMatch[1]),
      height: Number(heightMatch[1]),
    };
  }
  return null;
}

function wrapDiagramText(text: string, maxChars = 28) {
  const clean = (text || '').trim();
  if (!clean) return [];

  const words = clean.split(/\s+/);
  const lines: string[] = [];
  let current = '';

  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length <= maxChars || !current) {
      current = candidate;
      continue;
    }
    lines.push(current);
    current = word;
  }

  if (current) lines.push(current);
  return lines.slice(0, 2);
}

function splitSequenceStatement(line: string) {
  const colonIndex = line.indexOf(':');
  const statement = colonIndex >= 0 ? line.slice(0, colonIndex).trim() : line.trim();
  const label = colonIndex >= 0 ? line.slice(colonIndex + 1).trim() : '';

  let bestMatch: { index: number; token: string } | null = null;
  for (const token of SEQUENCE_ARROW_TOKENS) {
    const index = statement.indexOf(token);
    if (index <= 0) continue;
    if (!bestMatch || index < bestMatch.index || (index === bestMatch.index && token.length > bestMatch.token.length)) {
      bestMatch = { index, token };
    }
  }

  if (!bestMatch) return null;

  const from = statement.slice(0, bestMatch.index).trim();
  const to = statement.slice(bestMatch.index + bestMatch.token.length).trim();
  if (!from || !to) return null;

  return {
    from,
    to,
    arrow: bestMatch.token,
    label,
  };
}

function parseSequenceDiagram(chart: string): SequenceDiagramModel | null {
  const lines = (chart || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);

  if (!lines.length || lines[0] !== 'sequenceDiagram') {
    return null;
  }

  const participants: string[] = [];
  const messages: SequenceMessage[] = [];
  const blocks: SequenceBlock[] = [];
  const blockStack: Array<{ type: string; label: string; start: number }> = [];

  const ensureParticipant = (name: string) => {
    const clean = name.trim();
    if (clean && !participants.includes(clean)) {
      participants.push(clean);
    }
  };

  for (const line of lines.slice(1)) {
    const participantMatch = line.match(/^participant\s+([A-Za-z0-9_.-]+)(?:\s+as\s+.+)?$/i);
    if (participantMatch) {
      ensureParticipant(participantMatch[1]);
      continue;
    }

    const blockMatch = line.match(/^(loop|opt|alt|par|critical|break|rect)\b\s*(.*)$/i);
    if (blockMatch) {
      blockStack.push({
        type: blockMatch[1].toLowerCase(),
        label: (blockMatch[2] || '').trim(),
        start: messages.length,
      });
      continue;
    }

    if (/^end\b/i.test(line)) {
      const current = blockStack.pop();
      if (current && messages.length > current.start) {
        blocks.push({
          type: current.type,
          label: current.label,
          start: current.start,
          end: messages.length - 1,
        });
      }
      continue;
    }

    const parts = splitSequenceStatement(line);
    if (!parts) continue;

    ensureParticipant(parts.from);
    ensureParticipant(parts.to);
    messages.push({
      from: parts.from,
      to: parts.to,
      label: parts.label,
      dashed: parts.arrow.includes('--'),
    });
  }

  if (!participants.length || !messages.length) {
    return null;
  }

  while (blockStack.length) {
    const current = blockStack.pop();
    if (current && messages.length > current.start) {
      blocks.push({
        type: current.type,
        label: current.label,
        start: current.start,
        end: messages.length - 1,
      });
    }
  }

  return { participants, messages, blocks };
}

function getSequenceDiagramSize(model: SequenceDiagramModel): DiagramSize {
  const columnWidth = 144;
  const sidePadding = 18;
  const rowHeight = 40;
  const headerHeight = 74;
  const footerHeight = 16;
  return {
    width: Math.max(560, sidePadding * 2 + model.participants.length * columnWidth),
    height: headerHeight + model.messages.length * rowHeight + footerHeight,
  };
}

function renderArrowHead(x: number, y: number, direction: 'left' | 'right') {
  if (direction === 'left') {
    return <path d={`M ${x} ${y} L ${x + 10} ${y - 5} L ${x + 10} ${y + 5} Z`} fill="#0f172a" />;
  }
  return <path d={`M ${x} ${y} L ${x - 10} ${y - 5} L ${x - 10} ${y + 5} Z`} fill="#0f172a" />;
}

function SequenceDiagramCanvas({ model }: { model: SequenceDiagramModel }) {
  const columnWidth = 144;
  const sidePadding = 18;
  const rowHeight = 40;
  const headerY = 34;
  const lifelineTop = 62;
  const size = getSequenceDiagramSize(model);
  const participantCenter = (index: number) => sidePadding + index * columnWidth + columnWidth / 2;

  return (
    <svg width={size.width} height={size.height} viewBox={`0 0 ${size.width} ${size.height}`}>
      <defs>
        <filter id="diagram-shadow" x="-10%" y="-10%" width="120%" height="120%">
          <feDropShadow dx="0" dy="10" stdDeviation="14" floodColor="#0f172a" floodOpacity="0.08" />
        </filter>
      </defs>

      <rect x="0" y="0" width={size.width} height={size.height} fill="#ffffff" />

      {model.blocks.map((block, index) => {
        const y = lifelineTop + block.start * rowHeight - 12;
        const blockHeight = (block.end - block.start + 1) * rowHeight + 8;
        return (
          <g key={`block-${index}`}>
            <rect
              x={sidePadding - 6}
              y={y}
              width={size.width - sidePadding * 2 + 12}
              height={blockHeight}
              rx="12"
              fill="#f8fafc"
              stroke="#cbd5e1"
              strokeDasharray="4 4"
            />
            <text x={sidePadding} y={y + 12} fontSize="9" fontWeight="700" fill="#475569">
              {block.type.toUpperCase()}{block.label ? `: ${block.label}` : ''}
            </text>
          </g>
        );
      })}

      {model.participants.map((participant, index) => {
        const centerX = participantCenter(index);
        return (
          <g key={participant}>
            <rect
              x={centerX - 38}
              y={headerY - 10}
              width="76"
              height="18"
              rx="7"
              fill="#ffffff"
              stroke="#cbd5e1"
              filter="url(#diagram-shadow)"
            />
            <text
              x={centerX}
              y={headerY}
              textAnchor="middle"
              dominantBaseline="middle"
              fontSize="9"
              fontWeight="700"
              fill="#0f172a"
            >
              {participant}
            </text>
            <line
              x1={centerX}
              y1={lifelineTop}
              x2={centerX}
              y2={size.height - 10}
              stroke="#d7deea"
              strokeDasharray="4 4"
            />
          </g>
        );
      })}

      {model.messages.map((message, index) => {
        const fromIndex = model.participants.indexOf(message.from);
        const toIndex = model.participants.indexOf(message.to);
        const y = lifelineTop + index * rowHeight + 10;
        const fromX = participantCenter(fromIndex);
        const toX = participantCenter(toIndex);
        const isSelf = fromIndex === toIndex;
        const textLines = wrapDiagramText(message.label, 20);
        const strokeDasharray = message.dashed ? '4 3' : undefined;

        if (isSelf) {
          const loopWidth = 24;
          return (
            <g key={`message-${index}`}>
              <path
                d={`M ${fromX} ${y} h ${loopWidth} v 14 h -${loopWidth}`}
                fill="none"
                stroke="#0f172a"
                strokeWidth="1.2"
                strokeDasharray={strokeDasharray}
              />
              {renderArrowHead(fromX, y + 14, 'left')}
              <text x={fromX + loopWidth / 2} y={y - 7} textAnchor="middle" fontSize="8.5" fill="#334155">
                {textLines.map((line, lineIndex) => (
                  <tspan key={lineIndex} x={fromX + loopWidth / 2} dy={lineIndex === 0 ? 0 : 10}>
                    {line}
                  </tspan>
                ))}
              </text>
            </g>
          );
        }

        const direction = fromX < toX ? 'right' : 'left';
        const startX = fromX < toX ? fromX + 6 : fromX - 6;
        const endX = fromX < toX ? toX - 6 : toX + 6;

        return (
          <g key={`message-${index}`}>
            <line
              x1={startX}
              y1={y}
              x2={endX}
              y2={y}
              stroke="#0f172a"
              strokeWidth="1.2"
              strokeDasharray={strokeDasharray}
            />
            {renderArrowHead(endX, y, direction)}
            <text
              x={(fromX + toX) / 2}
              y={y - 7}
              textAnchor="middle"
              fontSize="8.5"
              fill="#334155"
            >
              {textLines.map((line, lineIndex) => (
                <tspan key={lineIndex} x={(fromX + toX) / 2} dy={lineIndex === 0 ? 0 : 10}>
                  {line}
                </tspan>
              ))}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function decodeGraphLabel(value: string) {
  return (value || '').replace(/\\"/g, '"').replace(/\\\\/g, '\\').trim();
}

function parseGraphNodeToken(token: string): GraphNodeModel | null {
  const source = (token || '').trim();
  if (!source) return null;

  const matchers: Array<{ regex: RegExp; shape: GraphNodeModel['shape'] }> = [
    { regex: /^(?<id>[A-Za-z][A-Za-z0-9_]*)\[\("(?<label>.*)"\)\]$/, shape: 'database' },
    { regex: /^(?<id>[A-Za-z][A-Za-z0-9_]*)\[\["(?<label>.*)"\]\]$/, shape: 'subroutine' },
    { regex: /^(?<id>[A-Za-z][A-Za-z0-9_]*)\(\("(?<label>.*)"\)\)$/, shape: 'circle' },
    { regex: /^(?<id>[A-Za-z][A-Za-z0-9_]*)\("(?<label>.*)"\)$/, shape: 'round' },
    { regex: /^(?<id>[A-Za-z][A-Za-z0-9_]*)\{\{"(?<label>.*)"\}\}$/, shape: 'decision' },
    { regex: /^(?<id>[A-Za-z][A-Za-z0-9_]*)\["(?<label>.*)"\]$/, shape: 'rect' },
    { regex: /^(?<id>[A-Za-z][A-Za-z0-9_]*)$/, shape: 'rect' },
  ];

  for (const matcher of matchers) {
    const result = source.match(matcher.regex);
    if (!result?.groups?.id) continue;
    return {
      id: result.groups.id,
      label: decodeGraphLabel(result.groups.label || result.groups.id),
      shape: matcher.shape,
      order: 0,
    };
  }

  return null;
}

function parseGraphDiagram(chart: string): GraphDiagramModel | null {
  const lines = (chart || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);

  const header = lines[0]?.match(/^(graph|flowchart)\s+(TD|LR|BT|RL)\b/i);
  if (!header) return null;

  const direction = /^(LR|RL)$/i.test(header[2]) ? 'LR' : 'TD';
  const nodeMap = new Map<string, GraphNodeModel>();
  const edges: GraphEdgeModel[] = [];
  let order = 0;

  const ensureNode = (token: string) => {
    const parsed = parseGraphNodeToken(token);
    if (!parsed) return null;
    const existing = nodeMap.get(parsed.id);
    if (existing) {
      if (existing.label === existing.id && parsed.label && parsed.label !== parsed.id) {
        existing.label = parsed.label;
      }
      if (existing.shape === 'rect' && parsed.shape !== 'rect') {
        existing.shape = parsed.shape;
      }
      return existing;
    }
    parsed.order = order++;
    nodeMap.set(parsed.id, parsed);
    return parsed;
  };

  for (const line of lines.slice(1)) {
    if (!line || line.startsWith('%%')) continue;

    let leftRaw = '';
    let rightRaw = '';
    let edgeLabel = '';

    const labeledArrowIndex = line.indexOf('-->|');
    if (labeledArrowIndex >= 0) {
      leftRaw = line.slice(0, labeledArrowIndex).trim();
      const rest = line.slice(labeledArrowIndex + 4);
      const labelTerminator = rest.indexOf('|');
      if (labelTerminator >= 0) {
        edgeLabel = rest.slice(0, labelTerminator).trim();
        rightRaw = rest.slice(labelTerminator + 1).trim();
      }
    } else {
      const arrowIndex = line.indexOf('-->');
      if (arrowIndex >= 0) {
        leftRaw = line.slice(0, arrowIndex).trim();
        rightRaw = line.slice(arrowIndex + 3).trim();
      }
    }

    if (leftRaw && rightRaw) {
      const fromNode = ensureNode(leftRaw);
      const toNode = ensureNode(rightRaw);
      if (fromNode && toNode) {
        edges.push({
          from: fromNode.id,
          to: toNode.id,
          label: decodeGraphLabel(edgeLabel),
        });
      }
      continue;
    }

    ensureNode(line);
  }

  if (!nodeMap.size) return null;

  const ids = Array.from(nodeMap.keys());
  const adjacency = new Map<string, string[]>();
  const indegree = new Map<string, number>();
  const layer = new Map<string, number>();

  for (const id of ids) {
    adjacency.set(id, []);
    indegree.set(id, 0);
    layer.set(id, 0);
  }

  for (const edge of edges) {
    adjacency.get(edge.from)?.push(edge.to);
    indegree.set(edge.to, (indegree.get(edge.to) || 0) + 1);
  }

  const queue = ids.filter((id) => (indegree.get(id) || 0) === 0);
  let cursor = 0;
  while (cursor < queue.length) {
    const id = queue[cursor++];
    const nextLayer = (layer.get(id) || 0) + 1;
    for (const neighbor of adjacency.get(id) || []) {
      layer.set(neighbor, Math.max(layer.get(neighbor) || 0, nextLayer));
      indegree.set(neighbor, (indegree.get(neighbor) || 0) - 1);
      if ((indegree.get(neighbor) || 0) === 0) {
        queue.push(neighbor);
      }
    }
  }

  const unresolved = ids.filter((id) => !queue.includes(id) && (adjacency.get(id)?.length || 0 || (edges.some((edge) => edge.to === id || edge.from === id))));
  for (const id of unresolved) {
    let fallbackLayer = 0;
    for (const edge of edges) {
      if (edge.to === id) {
        fallbackLayer = Math.max(fallbackLayer, (layer.get(edge.from) || 0) + 1);
      }
    }
    layer.set(id, fallbackLayer);
  }

  const grouped = new Map<number, string[]>();
  for (const node of Array.from(nodeMap.values()).sort((a, b) => a.order - b.order)) {
    const level = layer.get(node.id) || 0;
    if (!grouped.has(level)) grouped.set(level, []);
    grouped.get(level)?.push(node.id);
  }

  const layers = Array.from(grouped.entries())
    .sort((a, b) => a[0] - b[0])
    .map((entry) => entry[1]);

  return {
    direction,
    nodes: Array.from(nodeMap.values()).sort((a, b) => a.order - b.order),
    edges,
    layers,
  };
}

function getGraphDiagramLayout(model: GraphDiagramModel): GraphDiagramLayout {
  const nodeGapPrimary = model.direction === 'LR' ? 180 : 36;
  const nodeGapSecondary = model.direction === 'LR' ? 42 : 182;
  const paddingX = model.direction === 'LR' ? 56 : 52;
  const paddingY = model.direction === 'LR' ? 52 : 64;
  const nodeEntries = model.nodes.map((node) => {
    const lines = wrapDiagramText(node.label || node.id, 22);
    const width = Math.max(150, Math.min(220, Math.max(...lines.map((line) => line.length), 10) * 6.6 + 36));
    const height = 46 + Math.max(0, lines.length - 1) * 16;
    return { ...node, lines, width, height, x: 0, y: 0 };
  });
  const byId = new Map(nodeEntries.map((node) => [node.id, node]));

  if (model.direction === 'TD') {
    const layerWidths = model.layers.map((layer) => {
      return layer.reduce((sum, id, index) => {
        const node = byId.get(id);
        if (!node) return sum;
        return sum + node.width + (index > 0 ? nodeGapPrimary : 0);
      }, 0);
    });
    const totalWidth = Math.max(560, Math.max(...layerWidths, 0) + paddingX * 2);

    let currentY = paddingY;
    for (const layer of model.layers) {
      const nodes = layer.map((id) => byId.get(id)).filter(Boolean) as GraphLayoutNode[];
      const layerWidth = nodes.reduce((sum, node, index) => sum + node.width + (index > 0 ? nodeGapPrimary : 0), 0);
      let currentX = (totalWidth - layerWidth) / 2;
      let maxHeight = 0;
      for (const node of nodes) {
        node.x = currentX;
        node.y = currentY;
        currentX += node.width + nodeGapPrimary;
        maxHeight = Math.max(maxHeight, node.height);
      }
      currentY += maxHeight + nodeGapSecondary;
    }

    return {
      size: {
        width: totalWidth,
        height: Math.max(320, currentY - nodeGapSecondary + paddingY),
      },
      nodes: nodeEntries,
    };
  }

  const layerHeights = model.layers.map((layer) => {
    return layer.reduce((sum, id, index) => {
      const node = byId.get(id);
      if (!node) return sum;
      return sum + node.height + (index > 0 ? nodeGapPrimary : 0);
    }, 0);
  });
  const totalHeight = Math.max(320, Math.max(...layerHeights, 0) + paddingY * 2);

  let currentX = paddingX;
  for (const layer of model.layers) {
    const nodes = layer.map((id) => byId.get(id)).filter(Boolean) as GraphLayoutNode[];
    const layerHeight = nodes.reduce((sum, node, index) => sum + node.height + (index > 0 ? nodeGapPrimary : 0), 0);
    let currentY = (totalHeight - layerHeight) / 2;
    let maxWidth = 0;
    for (const node of nodes) {
      node.x = currentX;
      node.y = currentY;
      currentY += node.height + nodeGapPrimary;
      maxWidth = Math.max(maxWidth, node.width);
    }
    currentX += maxWidth + nodeGapSecondary;
  }

  return {
    size: {
      width: Math.max(560, currentX - nodeGapSecondary + paddingX),
      height: totalHeight,
    },
    nodes: nodeEntries,
  };
}

function GraphDiagramCanvas({ model, layout }: { model: GraphDiagramModel; layout: GraphDiagramLayout }) {
  const nodeMap = new Map(layout.nodes.map((node) => [node.id, node]));
  const outgoingEdgeMap = new Map<string, GraphEdgeModel[]>();
  const incomingEdgeMap = new Map<string, GraphEdgeModel[]>();

  for (const edge of model.edges) {
    const outgoing = outgoingEdgeMap.get(edge.from) || [];
    outgoing.push(edge);
    outgoingEdgeMap.set(edge.from, outgoing);

    const incoming = incomingEdgeMap.get(edge.to) || [];
    incoming.push(edge);
    incomingEdgeMap.set(edge.to, incoming);
  }

  const cubicPoint = (
    start: { x: number; y: number },
    control1: { x: number; y: number },
    control2: { x: number; y: number },
    end: { x: number; y: number },
    t: number,
  ) => {
    const mt = 1 - t;
    const mt2 = mt * mt;
    const t2 = t * t;
    const x =
      mt2 * mt * start.x +
      3 * mt2 * t * control1.x +
      3 * mt * t2 * control2.x +
      t2 * t * end.x;
    const y =
      mt2 * mt * start.y +
      3 * mt2 * t * control1.y +
      3 * mt * t2 * control2.y +
      t2 * t * end.y;
    return { x, y };
  };

  const edgePoints = (edge: GraphEdgeModel): GraphConnectionPoints | null => {
    const fromNode = nodeMap.get(edge.from);
    const toNode = nodeMap.get(edge.to);
    if (!fromNode || !toNode) return null;

    const outgoing = outgoingEdgeMap.get(edge.from) || [];
    const incoming = incomingEdgeMap.get(edge.to) || [];
    const outgoingIndex = Math.max(0, outgoing.findIndex((candidate) => candidate === edge));
    const incomingIndex = Math.max(0, incoming.findIndex((candidate) => candidate === edge));
    const outgoingSlot = (outgoingIndex + 1) / (outgoing.length + 1);
    const incomingSlot = (incomingIndex + 1) / (incoming.length + 1);

    if (model.direction === 'LR') {
      const start = {
        x: fromNode.x + fromNode.width,
        y: fromNode.y + fromNode.height * outgoingSlot,
      };
      const end = {
        x: toNode.x,
        y: toNode.y + toNode.height * incomingSlot,
      };
      const bend = Math.max(46, Math.abs(end.x - start.x) * 0.36);
      const control1 = { x: start.x + bend, y: start.y };
      const control2 = { x: end.x - bend, y: end.y };
      const mid = cubicPoint(start, control1, control2, end, 0.5);
      return {
        x1: start.x,
        y1: start.y,
        x2: end.x,
        y2: end.y,
        labelX: mid.x,
        labelY: mid.y - 12,
        path: `M ${start.x} ${start.y} C ${control1.x} ${control1.y}, ${control2.x} ${control2.y}, ${end.x} ${end.y}`,
      };
    }

    const start = {
      x: fromNode.x + fromNode.width * outgoingSlot,
      y: fromNode.y + fromNode.height,
    };
    const end = {
      x: toNode.x + toNode.width * incomingSlot,
      y: toNode.y,
    };
    const bend = Math.max(44, Math.abs(end.y - start.y) * 0.34);
    const control1 = { x: start.x, y: start.y + bend };
    const control2 = { x: end.x, y: end.y - bend };
    const mid = cubicPoint(start, control1, control2, end, 0.5);
    return {
      x1: start.x,
      y1: start.y,
      x2: end.x,
      y2: end.y,
      labelX: mid.x,
      labelY: mid.y - 12,
      path: `M ${start.x} ${start.y} C ${control1.x} ${control1.y}, ${control2.x} ${control2.y}, ${end.x} ${end.y}`,
    };
  };

  return (
    <svg width={layout.size.width} height={layout.size.height} viewBox={`0 0 ${layout.size.width} ${layout.size.height}`}>
      <defs>
        <filter id="graph-node-shadow" x="-10%" y="-10%" width="120%" height="120%">
          <feDropShadow dx="0" dy="8" stdDeviation="10" floodColor="#0f172a" floodOpacity="0.08" />
        </filter>
        <marker id="graph-arrowhead" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#0f172a" />
        </marker>
      </defs>

      <rect x="0" y="0" width={layout.size.width} height={layout.size.height} fill="#ffffff" />

      {model.edges.map((edge, index) => {
        const points = edgePoints(edge);
        if (!points) return null;
        const labelLines = edge.label ? wrapDiagramText(edge.label, 18) : [];
        const labelWidth = labelLines.length ? Math.max(...labelLines.map((line) => line.length), 6) * 5.8 + 14 : 0;
        const labelHeight = labelLines.length ? labelLines.length * 12 + 6 : 0;
        return (
          <g key={`graph-edge-${index}`}>
            <path
              d={points.path}
              fill="none"
              stroke="#475569"
              strokeWidth="1.6"
              markerEnd="url(#graph-arrowhead)"
            />
            {labelLines.length > 0 && (
              <>
                <rect
                  x={points.labelX - labelWidth / 2}
                  y={points.labelY - labelHeight + 2}
                  width={labelWidth}
                  height={labelHeight}
                  rx="10"
                  fill="#ffffff"
                  stroke="#e2e8f0"
                />
                <text x={points.labelX} y={points.labelY - labelHeight / 2 + 10} textAnchor="middle" fontSize="9" fill="#334155">
                  {labelLines.map((line, lineIndex) => (
                    <tspan key={lineIndex} x={points.labelX} dy={lineIndex === 0 ? 0 : 10}>
                      {line}
                    </tspan>
                  ))}
                </text>
              </>
            )}
          </g>
        );
      })}

      {layout.nodes.map((node) => {
        const commonProps = {
          fill: '#ffffff',
          stroke: '#cbd5e1',
          filter: 'url(#graph-node-shadow)',
        } as const;

        return (
          <g key={node.id}>
            {node.shape === 'round' ? (
              <rect x={node.x} y={node.y} width={node.width} height={node.height} rx="24" {...commonProps} />
            ) : node.shape === 'database' ? (
              <>
                <rect x={node.x} y={node.y + 8} width={node.width} height={Math.max(node.height - 16, 26)} rx="16" {...commonProps} />
                <ellipse cx={node.x + node.width / 2} cy={node.y + 8} rx={node.width / 2} ry="8" fill="#ffffff" stroke="#cbd5e1" />
                <ellipse cx={node.x + node.width / 2} cy={node.y + node.height - 8} rx={node.width / 2} ry="8" fill="#f8fafc" stroke="#cbd5e1" />
              </>
            ) : node.shape === 'circle' ? (
              <ellipse cx={node.x + node.width / 2} cy={node.y + node.height / 2} rx={node.width / 2} ry={node.height / 2} {...commonProps} />
            ) : node.shape === 'decision' ? (
              <path d={`M ${node.x + node.width / 2} ${node.y} L ${node.x + node.width} ${node.y + node.height / 2} L ${node.x + node.width / 2} ${node.y + node.height} L ${node.x} ${node.y + node.height / 2} Z`} {...commonProps} />
            ) : (
              <rect x={node.x} y={node.y} width={node.width} height={node.height} rx="18" {...commonProps} />
            )}

            <text x={node.x + node.width / 2} y={node.y + node.height / 2 - (node.lines.length - 1) * 7} textAnchor="middle" fontSize="11" fontWeight="600" fill="#0f172a">
              {node.lines.map((line, lineIndex) => (
                <tspan key={lineIndex} x={node.x + node.width / 2} dy={lineIndex === 0 ? 0 : 14}>
                  {line}
                </tspan>
              ))}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function ZoomableDiagramFrame({ intrinsicSize, children }: { intrinsicSize: DiagramSize; children: ReactNode }) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const lastZoomRef = useRef(1);
  const wheelAnchorRef = useRef<{
    contentX: number;
    contentY: number;
    viewportX: number;
    viewportY: number;
  } | null>(null);
  const panRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    scrollLeft: number;
    scrollTop: number;
  } | null>(null);
  const [fitScale, setFitScale] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [manualZoom, setManualZoom] = useState(false);
  const [isPanning, setIsPanning] = useState(false);
  const [frameSize, setFrameSize] = useState(() => ({
    width: intrinsicSize.width,
    height: Math.max(320, Math.min(620, intrinsicSize.width / (16 / 9))),
  }));
  const horizontalPadding = 24;
  const topPadding = 48;
  const bottomPadding = 12;

  useEffect(() => {
    setManualZoom(false);
  }, [intrinsicSize.width, intrinsicSize.height]);

  useEffect(() => {
    const updateFitScale = () => {
      const viewportWidth = viewportRef.current?.clientWidth ?? intrinsicSize.width;
      const maxFrameHeight = typeof window !== 'undefined' ? Math.min(window.innerHeight * 0.68, 620) : 620;
      const nextFrameHeight = clamp(viewportWidth / (16 / 9), 320, maxFrameHeight);
      const availableWidth = Math.max(viewportWidth - horizontalPadding, 160);
      const availableHeight = Math.max(nextFrameHeight - topPadding - bottomPadding, 180);
      const widthFit = availableWidth / intrinsicSize.width;
      const heightFit = availableHeight / intrinsicSize.height;
      const nextFit = clamp(Math.min(widthFit, heightFit, 1), 0.25, 1);
      setFrameSize({ width: viewportWidth, height: nextFrameHeight });
      setFitScale(nextFit);
      setZoom((current) => (manualZoom ? current : nextFit));
    };

    updateFitScale();

    if (!viewportRef.current || typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', updateFitScale);
      return () => window.removeEventListener('resize', updateFitScale);
    }

    const observer = new ResizeObserver(() => updateFitScale());
    observer.observe(viewportRef.current);
    return () => observer.disconnect();
  }, [intrinsicSize.width, intrinsicSize.height, manualZoom]);

  const availableWidth = Math.max(frameSize.width - horizontalPadding, 160);
  const availableHeight = Math.max(frameSize.height - topPadding - bottomPadding, 180);
  const scaledWidth = intrinsicSize.width * zoom;
  const scaledHeight = intrinsicSize.height * zoom;
  const stageWidth = Math.max(availableWidth, scaledWidth);
  const stageHeight = Math.max(availableHeight, scaledHeight);
  const offsetX = scaledWidth < availableWidth ? (availableWidth - scaledWidth) / 2 : 0;
  const offsetY = scaledHeight < availableHeight ? (availableHeight - scaledHeight) / 2 : 0;

  const setPresetZoom = (value: number, manual = true) => {
    wheelAnchorRef.current = null;
    setManualZoom(manual);
    setZoom(clamp(value, 0.3, 2.4));
  };

  const zoomLabel = `${Math.round(zoom * 100)}%`;
  const canPan = scaledWidth > availableWidth + 1 || scaledHeight > availableHeight + 1;

  useEffect(() => {
    if (!canPan) {
      panRef.current = null;
      setIsPanning(false);
    }
  }, [canPan]);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    if (!manualZoom || !canPan) {
      viewport.scrollTo({ left: 0, top: 0 });
      wheelAnchorRef.current = null;
      lastZoomRef.current = zoom;
      return;
    }

    const wheelAnchor = wheelAnchorRef.current;
    if (wheelAnchor) {
      viewport.scrollTo({
        left: Math.max(0, offsetX + wheelAnchor.contentX * zoom - wheelAnchor.viewportX),
        top: Math.max(0, offsetY + wheelAnchor.contentY * zoom - wheelAnchor.viewportY),
      });
      wheelAnchorRef.current = null;
      lastZoomRef.current = zoom;
      return;
    }

    if (Math.abs(lastZoomRef.current - zoom) > 0.001) {
      viewport.scrollTo({
        left: Math.max(0, (stageWidth - availableWidth) / 2),
        top: Math.max(0, (stageHeight - availableHeight) / 2),
      });
    }
    lastZoomRef.current = zoom;
  }, [manualZoom, canPan, fitScale, intrinsicSize.width, intrinsicSize.height, zoom, stageWidth, stageHeight, availableWidth, availableHeight]);

  const stopPanning = (pointerId?: number) => {
    const viewport = viewportRef.current;
    const activePan = panRef.current;
    if (!activePan) return;
    if (pointerId != null && activePan.pointerId !== pointerId) return;
    if (viewport?.hasPointerCapture(activePan.pointerId)) {
      viewport.releasePointerCapture(activePan.pointerId);
    }
    panRef.current = null;
    setIsPanning(false);
  };

  const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!canPan) return;
    if (event.pointerType === 'mouse' && event.button !== 0) return;

    const viewport = viewportRef.current;
    if (!viewport) return;

    panRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      scrollLeft: viewport.scrollLeft,
      scrollTop: viewport.scrollTop,
    };
    viewport.setPointerCapture(event.pointerId);
    setIsPanning(true);
    event.preventDefault();
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const viewport = viewportRef.current;
    const activePan = panRef.current;
    if (!viewport || !activePan || activePan.pointerId !== event.pointerId) return;

    const deltaX = event.clientX - activePan.startX;
      const deltaY = event.clientY - activePan.startY;
      viewport.scrollLeft = activePan.scrollLeft - deltaX;
      viewport.scrollTop = activePan.scrollTop - deltaY;
      event.preventDefault();
  };

  const handleWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    if (!event.ctrlKey && !event.metaKey) return;

    const viewport = viewportRef.current;
    if (!viewport) return;

    event.preventDefault();

    const rect = viewport.getBoundingClientRect();
    const viewportX = event.clientX - rect.left;
    const viewportY = event.clientY - rect.top;
    const stageX = viewport.scrollLeft + viewportX;
    const stageY = viewport.scrollTop + viewportY;

    const contentX = clamp((stageX - offsetX) / zoom, 0, intrinsicSize.width);
    const contentY = clamp((stageY - offsetY) / zoom, 0, intrinsicSize.height);
    const wheelScale = Math.exp(-event.deltaY * 0.0025);
    const nextZoom = clamp(zoom * wheelScale, 0.3, 2.4);

    if (Math.abs(nextZoom - zoom) < 0.001) return;

    wheelAnchorRef.current = {
      contentX,
      contentY,
      viewportX,
      viewportY,
    };
    setManualZoom(true);
    setZoom(nextZoom);
  };

  return (
    <div
      className="relative overflow-hidden rounded-[20px] border border-black/5 bg-[linear-gradient(180deg,#ffffff_0%,#f8fafc_100%)] shadow-[0_16px_40px_rgba(15,23,42,0.05)]"
      style={{ height: frameSize.height }}
    >
      <div className="absolute inset-x-0 top-0 h-12 bg-[linear-gradient(180deg,rgba(248,250,252,0.96),rgba(248,250,252,0))]" />
      <div className="absolute right-3 top-3 z-10 flex items-center gap-1 rounded-full border border-black/5 bg-white/95 px-2 py-1 text-[10px] font-medium text-slate-500 shadow-[0_10px_24px_rgba(15,23,42,0.08)] backdrop-blur">
        <button
          type="button"
          onClick={() => setPresetZoom(zoom - 0.15)}
          className="flex h-6 w-6 items-center justify-center rounded-full text-sm leading-none text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
          aria-label="Zoom out"
        >
          -
        </button>
        <button
          type="button"
          onClick={() => setPresetZoom(fitScale, false)}
          className="rounded-full px-2 py-1 text-[9px] uppercase tracking-[0.16em] text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
        >
          Fit
        </button>
        <button
          type="button"
          onClick={() => setPresetZoom(1)}
          className="rounded-full px-2 py-1 text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
        >
          {zoomLabel}
        </button>
        <button
          type="button"
          onClick={() => setPresetZoom(zoom + 0.15)}
          className="flex h-6 w-6 items-center justify-center rounded-full text-sm leading-none text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
          aria-label="Zoom in"
        >
          +
        </button>
      </div>

      <div
        ref={viewportRef}
        className={`diagram-pan-shell h-full overflow-auto px-3 pb-3 pt-12 ${canPan ? 'select-none' : ''}`}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={(event) => stopPanning(event.pointerId)}
        onPointerCancel={(event) => stopPanning(event.pointerId)}
        onWheel={handleWheel}
        style={{ cursor: canPan ? (isPanning ? 'grabbing' : 'grab') : 'default' }}
      >
        <div style={{ position: 'relative', width: stageWidth, height: stageHeight }}>
          <div
            style={{
              position: 'absolute',
              left: offsetX,
              top: offsetY,
              width: intrinsicSize.width * zoom,
              height: intrinsicSize.height * zoom,
            }}
          >
            <div
              style={{
                width: intrinsicSize.width,
                height: intrinsicSize.height,
                transform: `scale(${zoom})`,
                transformOrigin: 'top left',
              }}
            >
              {children}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function MermaidDiagram({ chart, id = 'mermaid' }: Props) {
  const [svg, setSvg] = useState('');
  const [error, setError] = useState('');
  const [debugChart, setDebugChart] = useState('');
  const [sequenceFallback, setSequenceFallback] = useState<SequenceDiagramModel | null>(null);
  const [graphFallback, setGraphFallback] = useState<GraphDiagramModel | null>(null);

  useEffect(() => {
    if (!chart || !chart.trim()) {
      setSvg('');
      setError('');
      setDebugChart('');
      setSequenceFallback(null);
      setGraphFallback(null);
      return;
    }

    let cancelled = false;

    const renderChart = async () => {
      try {
        const mermaid = await loadMermaid();
        initializeMermaid(mermaid);

        const cleanChart = normalizeMermaid(chart);
        const isErDiagram = /^erDiagram\b/i.test(cleanChart);
        if (!cancelled) {
          setDebugChart(cleanChart);
          setSequenceFallback(null);
          setGraphFallback(null);
        }

        const renderedSvg = await enqueueMermaidRender(async () => {
          let primaryError: unknown = null;

          if (isErDiagram) {
            const uniqueId = `mermaid-${id}-${Date.now()}`;
            const { svg: nextSvg } = await mermaid.render(uniqueId, cleanChart);
            return nextSvg;
          }

          try {
            const uniqueId = `mermaid-${id}-${Date.now()}`;
            const { svg: nextSvg } = await mermaid.render(uniqueId, cleanChart);
            if (nextSvg && !hasMermaidErrorMarkup(nextSvg)) {
              return nextSvg;
            }
          } catch (err) {
            primaryError = err;
            // Fall through to the DOM-based Mermaid rendering, which mirrors mermaid.live more closely.
          }

          const fallbackSvg = await renderMermaidViaDom(mermaid, cleanChart, id);
          if (!fallbackSvg) {
            const fallbackMessage =
              (primaryError as any)?.message ||
              (primaryError as any)?.str ||
              'Diagram syntax error';
            throw new Error(fallbackMessage);
          }
          return fallbackSvg;
        });

        if (!renderedSvg || (!isErDiagram && hasMermaidErrorMarkup(renderedSvg)) || !/<svg[\s>]/i.test(renderedSvg)) {
          throw new Error('Diagram syntax error');
        }

        if (!cancelled) {
          setSvg(renderedSvg);
          setError('');
          setSequenceFallback(null);
          setGraphFallback(null);
        }
      } catch (err: any) {
        if (!cancelled) {
          const normalizedChart = debugChart || normalizeMermaid(chart);
          const sequenceModel = /^sequenceDiagram\b/i.test(normalizedChart) ? parseSequenceDiagram(normalizedChart) : null;
          if (sequenceModel) {
            setSvg('');
            setError('');
            setSequenceFallback(sequenceModel);
            setGraphFallback(null);
            return;
          }
          const graphModel = /^(graph|flowchart)\b/i.test(normalizedChart) ? parseGraphDiagram(normalizedChart) : null;
          if (graphModel) {
            setSvg('');
            setError('');
            setSequenceFallback(null);
            setGraphFallback(graphModel);
            return;
          }
          setError(err?.message || 'Diagram render failed');
          setSvg('');
          setSequenceFallback(null);
          setGraphFallback(null);
        }
      }
    };

    void renderChart();
    return () => {
      cancelled = true;
    };
  }, [chart, id]);

  const svgSize = useMemo(() => (svg ? extractSvgDimensions(svg) : null), [svg]);
  const fallbackSize = useMemo(() => (sequenceFallback ? getSequenceDiagramSize(sequenceFallback) : null), [sequenceFallback]);
  const graphLayout = useMemo(() => (graphFallback ? getGraphDiagramLayout(graphFallback) : null), [graphFallback]);

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
          <summary className="cursor-pointer text-[10px] text-slate-400">Normalized diagram code</summary>
          <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-slate-800 p-2 text-[10px] text-green-400">{debugChart || normalizeMermaid(chart)}</pre>
        </details>
      </div>
    );
  }

  if (sequenceFallback && fallbackSize) {
    return (
      <ZoomableDiagramFrame intrinsicSize={fallbackSize}>
        <SequenceDiagramCanvas model={sequenceFallback} />
      </ZoomableDiagramFrame>
    );
  }

  if (graphFallback && graphLayout) {
    return (
      <ZoomableDiagramFrame intrinsicSize={graphLayout.size}>
        <GraphDiagramCanvas model={graphFallback} layout={graphLayout} />
      </ZoomableDiagramFrame>
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
    <ZoomableDiagramFrame intrinsicSize={svgSize || { width: 1200, height: 680 }}>
      <div
        className="[&>svg]:block [&>svg]:h-full [&>svg]:w-full [&>svg]:max-w-none"
        dangerouslySetInnerHTML={{ __html: svg }}
      />
    </ZoomableDiagramFrame>
  );
}
