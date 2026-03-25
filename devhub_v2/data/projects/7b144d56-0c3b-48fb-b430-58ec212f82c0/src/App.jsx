import { useMemo, useState } from 'react';

const BUTTON_ROWS = [
  ['C', 'DEL', '%', '÷'],
  ['7', '8', '9', '×'],
  ['4', '5', '6', '-'],
  ['1', '2', '3', '+'],
  ['+/-', '0', '.', '='],
  ['√', 'x²'],
];

const DISPLAY_OPERATORS = {
  '/': '÷',
  '*': '×',
  '-': '−',
  '+': '+',
};

function sanitizeExpression(value) {
  return value
    .replace(/×/g, '*')
    .replace(/÷/g, '/')
    .replace(/−/g, '-')
    .replace(/[^0-9+\-*/.() ]/g, '');
}

function evaluateExpression(value) {
  const sanitized = sanitizeExpression(value);
  if (!sanitized.trim()) return '0';
  if (!/^[0-9+\-*/.() ]+$/.test(sanitized)) throw new Error('Invalid expression');
  const result = Function(`"use strict"; return (${sanitized})`)();
  if (!Number.isFinite(result)) throw new Error('Invalid result');
  return String(Number(result.toFixed(10)));
}

function applyUnary(value, transform) {
  const result = transform(Number(evaluateExpression(value)));
  if (!Number.isFinite(result)) throw new Error('Invalid result');
  return String(Number(result.toFixed(10)));
}

function prettify(value) {
  return value.replace(/[/*\-+]/g, (symbol) => DISPLAY_OPERATORS[symbol] || symbol);
}

export default function App() {
  const [expression, setExpression] = useState('0');
  const [history, setHistory] = useState([
    'Tap numbers and operators to start calculating.',
    'Use √, x², %, and +/- for quick utility actions.',
  ]);
  const [solved, setSolved] = useState(false);

  const livePreview = useMemo(() => prettify(expression), [expression]);

  const updateHistory = (entry) => {
    setHistory((current) => [entry, ...current].slice(0, 6));
  };

  const onPress = (value) => {
    if (/^[0-9]$/.test(value)) {
      setExpression((current) => (current === '0' || solved ? value : current + value));
      setSolved(false);
      return;
    }

    if (value === '.') {
      setExpression((current) => {
        if (solved) return '0.';
        const parts = current.split(/[+\-*/]/);
        const currentPart = parts[parts.length - 1] || '';
        return currentPart.includes('.') ? current : current + '.';
      });
      setSolved(false);
      return;
    }

    if (value === 'C') {
      setExpression('0');
      setSolved(false);
      updateHistory('Calculator reset.');
      return;
    }

    if (value === 'DEL') {
      setExpression((current) => {
        const next = solved ? '0' : current.slice(0, -1);
        return next || '0';
      });
      setSolved(false);
      return;
    }

    if (value === '+/-') {
      try {
        setExpression((current) => String(Number(evaluateExpression(current)) * -1));
        setSolved(false);
      } catch {
        updateHistory('Could not toggle the current value.');
      }
      return;
    }

    if (value === '%') {
      try {
        setExpression((current) => applyUnary(current, (number) => number / 100));
        setSolved(false);
      } catch {
        updateHistory('Could not convert the value to a percentage.');
      }
      return;
    }

    if (value === '√') {
      try {
        setExpression((current) => applyUnary(current, (number) => Math.sqrt(number)));
        setSolved(true);
        updateHistory('Square root applied.');
      } catch {
        updateHistory('Square root is only available for valid positive values.');
      }
      return;
    }

    if (value === 'x²') {
      try {
        setExpression((current) => applyUnary(current, (number) => number ** 2));
        setSolved(true);
        updateHistory('Squared the current value.');
      } catch {
        updateHistory('Could not square the current value.');
      }
      return;
    }

    if (value === '=') {
      try {
        const result = evaluateExpression(expression);
        updateHistory(`${prettify(expression)} = ${result}`);
        setExpression(result);
        setSolved(true);
      } catch {
        updateHistory('That expression could not be evaluated.');
        setExpression('0');
        setSolved(false);
      }
      return;
    }

    setExpression((current) => {
      const next = solved ? `${current}${value}` : current;
      if (/[+\-*/]$/.test(next)) return next.slice(0, -1) + value;
      return `${next}${value}`;
    });
    setSolved(false);
  };

  return (
    <main className="calculator-shell">
      <section className="calculator-frame">
        <div className="hero-copy">
          <span className="eyebrow">Working Calculator</span>
          <h1>Simple calculator</h1>
          <p>simple calculator - clean minimal ui, with lots of animation</p>
        </div>

        <section className="calculator-panel">
          <div className="display-panel">
            <div className="display-meta">
              <span>Live expression</span>
              <span className="status-pill">{solved ? 'Solved' : 'Editing'}</span>
            </div>
            <div className="expression-preview">{livePreview}</div>
            <div className="display-value">{prettify(expression)}</div>
          </div>

          <div className="button-grid">
            {BUTTON_ROWS.flat().map((button) => (
              <button
                key={button}
                type="button"
                onClick={() => onPress(button)}
                className={`calc-button ${button === '=' ? 'accent' : ''} ${['÷', '×', '-', '+'].includes(button) ? 'operator' : ''} ${['C', 'DEL'].includes(button) ? 'utility' : ''}`}
              >
                {button}
              </button>
            ))}
          </div>
        </section>

        <aside className="history-panel">
          <div>
            <span className="eyebrow">Recent Activity</span>
            <h2>History</h2>
          </div>
          <div className="history-list">
            {history.map((entry, index) => (
              <div key={`${entry}-${index}`} className="history-item">
                {entry}
              </div>
            ))}
          </div>
        </aside>
      </section>
    </main>
  );
}
