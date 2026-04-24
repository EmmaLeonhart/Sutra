/**
 * Sutra — fuzzy-logic explorer.
 *
 * Tabs along the top pick one connective; a single card below shows
 * its live value as the sliders move. Each tab shows three lines:
 * the connective's name, its math symbol, and the common programming
 * idiom for it.
 *
 * @file
 */

(function () {
  const HOST = document.getElementById('fuzzy-logic-widget');
  if (!HOST) return;

  const andPoly = (a, b) =>
    (a + b + a * b - a * a - b * b + a * a * b * b) / 2;
  const orPoly = (a, b) =>
    (a + b - a * b + a * a + b * b - a * a * b * b) / 2;

  const CONNECTIVES = [
    {
      id: 'and',
      name: 'AND',
      symbol: '∧',           // ∧
      idiom: '&&',
      polynomial: '(a + b + ab − a² − b² + a²b²) / 2',
      fn: andPoly,
    },
    {
      id: 'or',
      name: 'OR',
      symbol: '∨',           // ∨
      idiom: '||',
      polynomial: '(a + b − ab + a² + b² − a²b²) / 2',
      fn: orPoly,
    },
    {
      id: 'nand',
      name: 'NAND',
      symbol: '⊼',           // ⊼
      idiom: '!(a && b)',
      polynomial: '(−a − b − ab + a² + b² − a²b²) / 2',
      fn: (a, b) => -andPoly(a, b),
    },
    {
      id: 'nor',
      name: 'NOR',
      symbol: '⊽',           // ⊽
      idiom: '!(a || b)',
      polynomial: '(−a − b + ab − a² − b² + a²b²) / 2',
      fn: (a, b) => -orPoly(a, b),
    },
    {
      id: 'xor',
      name: 'XOR',
      symbol: '⊕',           // ⊕
      idiom: '^',
      polynomial: '−a · b',
      fn: (a, b) => -a * b,
    },
    {
      id: 'xnor',
      name: 'XNOR',
      symbol: '↔',           // ↔  (also the biconditional / IFF)
      idiom: '== (on bools)',
      polynomial: 'a · b',
      fn: (a, b) => a * b,
    },
  ];

  const CSS = `
#fuzzy-logic-widget { font-family: Inter, system-ui, sans-serif; margin: 1rem 0; }
#fuzzy-logic-widget .flw-controls {
  background: var(--md-default-bg-color);
  border: 1px solid var(--md-default-fg-color--lightest);
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1rem;
}
#fuzzy-logic-widget .flw-row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 0.75rem;
  align-items: center;
  margin-bottom: 0.5rem;
}
#fuzzy-logic-widget .flw-row label { font-weight: 600; min-width: 1.5rem; }
#fuzzy-logic-widget .flw-row input[type=range] { width: 100%; }
#fuzzy-logic-widget .flw-val {
  font-family: 'JetBrains Mono', 'SF Mono', monospace;
  min-width: 5ch;
  text-align: right;
}
#fuzzy-logic-widget .flw-snap {
  display: flex;
  gap: 0.25rem;
  justify-content: flex-end;
}
#fuzzy-logic-widget .flw-snap button {
  padding: 0.2rem 0.5rem;
  border: 1px solid var(--md-default-fg-color--lighter);
  background: var(--md-default-bg-color);
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8em;
}
#fuzzy-logic-widget .flw-snap button:hover { background: var(--md-accent-fg-color--transparent); }

#fuzzy-logic-widget .flw-tabs {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
  gap: 0.4rem;
  margin-bottom: 0.75rem;
}
#fuzzy-logic-widget .flw-tab {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.1rem;
  padding: 0.5rem 0.5rem;
  border: 1px solid var(--md-default-fg-color--lighter);
  background: var(--md-default-bg-color);
  border-radius: 6px;
  cursor: pointer;
  text-align: center;
  transition: background 80ms, border-color 80ms;
}
#fuzzy-logic-widget .flw-tab:hover { background: var(--md-accent-fg-color--transparent); }
#fuzzy-logic-widget .flw-tab.active {
  background: var(--md-primary-fg-color);
  color: var(--md-primary-bg-color);
  border-color: var(--md-primary-fg-color);
}
#fuzzy-logic-widget .flw-tab-name {
  font-weight: 700;
  font-size: 0.95em;
  letter-spacing: 0.05em;
}
#fuzzy-logic-widget .flw-tab-symbol {
  font-size: 1.2em;
  line-height: 1;
  opacity: 0.85;
}
#fuzzy-logic-widget .flw-tab-idiom {
  font-family: 'JetBrains Mono', 'SF Mono', monospace;
  font-size: 0.75em;
  opacity: 0.65;
  margin-top: 0.1rem;
}
#fuzzy-logic-widget .flw-tab.active .flw-tab-symbol,
#fuzzy-logic-widget .flw-tab.active .flw-tab-idiom { opacity: 1; }

#fuzzy-logic-widget .flw-card {
  border: 1px solid var(--md-default-fg-color--lightest);
  border-radius: 8px;
  padding: 1rem;
  background: var(--md-default-bg-color);
}
#fuzzy-logic-widget .flw-card-header {
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
  margin-bottom: 0.3rem;
}
#fuzzy-logic-widget .flw-card-name {
  font-weight: 700;
  font-size: 1.1rem;
  letter-spacing: 0.05em;
  color: var(--md-primary-fg-color);
}
#fuzzy-logic-widget .flw-card-symbol {
  font-size: 1.3rem;
  color: var(--md-default-fg-color--light);
}
#fuzzy-logic-widget .flw-card-idiom {
  font-family: 'JetBrains Mono', 'SF Mono', monospace;
  font-size: 0.85em;
  color: var(--md-default-fg-color--light);
  margin-left: auto;
}
#fuzzy-logic-widget .flw-poly {
  font-family: 'JetBrains Mono', 'SF Mono', monospace;
  font-size: 0.85em;
  color: var(--md-default-fg-color--light);
  margin-bottom: 0.6rem;
}
#fuzzy-logic-widget .flw-result {
  font-family: 'JetBrains Mono', 'SF Mono', monospace;
  font-size: 1.1rem;
  margin-bottom: 0.5rem;
}
#fuzzy-logic-widget .flw-bar {
  position: relative;
  height: 14px;
  background: linear-gradient(to right,
    #d32f2f 0%, #d32f2f 15%,
    #757575 40%, #757575 60%,
    #388e3c 85%, #388e3c 100%);
  border-radius: 4px;
}
#fuzzy-logic-widget .flw-marker {
  position: absolute;
  top: -3px;
  width: 3px;
  height: 20px;
  background: var(--md-default-fg-color);
  border-radius: 2px;
  transform: translateX(-50%);
  transition: left 80ms linear;
}
#fuzzy-logic-widget .flw-axis {
  display: flex;
  justify-content: space-between;
  font-size: 0.7em;
  color: var(--md-default-fg-color--light);
  margin-top: 2px;
}
`;
  const style = document.createElement('style');
  style.textContent = CSS;
  HOST.appendChild(style);

  HOST.innerHTML += `
    <div class="flw-controls">
      <div class="flw-row">
        <label for="flw-a">a</label>
        <input id="flw-a" type="range" min="-1" max="1" step="0.01" value="1">
        <span class="flw-val" id="flw-a-val">+1.00</span>
      </div>
      <div class="flw-row">
        <span></span>
        <div class="flw-snap">
          <button data-target="flw-a" data-value="-1">false</button>
          <button data-target="flw-a" data-value="0">unknown</button>
          <button data-target="flw-a" data-value="1">true</button>
        </div>
        <span></span>
      </div>
      <div class="flw-row">
        <label for="flw-b">b</label>
        <input id="flw-b" type="range" min="-1" max="1" step="0.01" value="-1">
        <span class="flw-val" id="flw-b-val">-1.00</span>
      </div>
      <div class="flw-row">
        <span></span>
        <div class="flw-snap">
          <button data-target="flw-b" data-value="-1">false</button>
          <button data-target="flw-b" data-value="0">unknown</button>
          <button data-target="flw-b" data-value="1">true</button>
        </div>
        <span></span>
      </div>
    </div>
    <div class="flw-tabs" id="flw-tabs"></div>
    <div class="flw-card">
      <div class="flw-card-header">
        <span class="flw-card-name" id="flw-name"></span>
        <span class="flw-card-symbol" id="flw-symbol"></span>
        <span class="flw-card-idiom" id="flw-idiom"></span>
      </div>
      <div class="flw-poly" id="flw-poly"></div>
      <div class="flw-result" id="flw-result"></div>
      <div class="flw-bar"><div class="flw-marker" id="flw-marker"></div></div>
      <div class="flw-axis"><span>false</span><span>unknown</span><span>true</span></div>
    </div>
  `;

  const tabsEl = HOST.querySelector('#flw-tabs');
  for (const c of CONNECTIVES) {
    const b = document.createElement('button');
    b.className = 'flw-tab';
    b.dataset.id = c.id;
    b.innerHTML = `
      <span class="flw-tab-name">${c.name}</span>
      <span class="flw-tab-symbol">${c.symbol}</span>
      <span class="flw-tab-idiom">${escapeHtml(c.idiom)}</span>
    `;
    tabsEl.appendChild(b);
  }

  const aSlider = HOST.querySelector('#flw-a');
  const bSlider = HOST.querySelector('#flw-b');
  const aVal = HOST.querySelector('#flw-a-val');
  const bVal = HOST.querySelector('#flw-b-val');
  const nameEl = HOST.querySelector('#flw-name');
  const symbolEl = HOST.querySelector('#flw-symbol');
  const idiomEl = HOST.querySelector('#flw-idiom');
  const polyEl = HOST.querySelector('#flw-poly');
  const resultEl = HOST.querySelector('#flw-result');
  const markerEl = HOST.querySelector('#flw-marker');

  let activeId = 'and';

  function fmt(v) { return (v >= 0 ? '+' : '') + v.toFixed(3); }
  function escapeHtml(s) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function render() {
    const a = parseFloat(aSlider.value);
    const b = parseFloat(bSlider.value);
    aVal.textContent = fmt(a);
    bVal.textContent = fmt(b);
    const c = CONNECTIVES.find(c => c.id === activeId);
    nameEl.textContent = c.name;
    symbolEl.textContent = c.symbol;
    idiomEl.textContent = c.idiom;
    polyEl.textContent = c.polynomial;
    const val = c.fn(a, b);
    resultEl.textContent = fmt(val);
    const clamped = Math.max(-1, Math.min(1, val));
    markerEl.style.left = `${((clamped + 1) / 2) * 100}%`;
    for (const tab of HOST.querySelectorAll('.flw-tab')) {
      tab.classList.toggle('active', tab.dataset.id === activeId);
    }
  }

  aSlider.addEventListener('input', render);
  bSlider.addEventListener('input', render);
  for (const btn of HOST.querySelectorAll('.flw-snap button')) {
    btn.addEventListener('click', () => {
      HOST.querySelector('#' + btn.dataset.target).value = parseFloat(btn.dataset.value);
      render();
    });
  }
  for (const tab of HOST.querySelectorAll('.flw-tab')) {
    tab.addEventListener('click', () => { activeId = tab.dataset.id; render(); });
  }

  render();
})();
