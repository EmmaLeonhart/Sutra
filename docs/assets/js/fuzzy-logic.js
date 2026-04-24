/**
 * Sutra — fuzzy-logic explorer.
 *
 * Two sliders (a, b) and a single connective card that switches via
 * tabs. One operation visible at a time, so the user focuses on how
 * that polynomial responds to the inputs rather than reading a grid
 * of cards.
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
      name: 'a && b',
      polynomial: '(a + b + ab − a² − b² + a²b²) / 2',
      fn: andPoly,
    },
    {
      id: 'or',
      name: 'a || b',
      polynomial: '(a + b − ab + a² + b² − a²b²) / 2',
      fn: orPoly,
    },
    {
      id: 'nand',
      name: 'nand(a, b)',
      polynomial: '−(AND polynomial)',
      fn: (a, b) => -andPoly(a, b),
    },
    {
      id: 'nor',
      name: 'nor(a, b)',
      polynomial: '−(OR polynomial)',
      fn: (a, b) => -orPoly(a, b),
    },
    {
      id: 'xor',
      name: 'xor(a, b)',
      polynomial: '−a · b',
      fn: (a, b) => -a * b,
    },
    {
      id: 'iff',
      name: 'iff(a, b)',
      polynomial: 'a · b',
      fn: (a, b) => a * b,
    },
    {
      id: 'implies',
      name: 'a → b',
      polynomial: '(−a + b + ab + a² + b² − a²b²) / 2',
      fn: (a, b) => orPoly(-a, b),
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
#fuzzy-logic-widget .flw-row label {
  font-weight: 600;
  min-width: 1.5rem;
}
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
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  margin-bottom: 0.75rem;
}
#fuzzy-logic-widget .flw-tab {
  padding: 0.35rem 0.75rem;
  border: 1px solid var(--md-default-fg-color--lighter);
  background: var(--md-default-bg-color);
  border-radius: 4px;
  cursor: pointer;
  font-family: 'JetBrains Mono', 'SF Mono', monospace;
  font-size: 0.85em;
}
#fuzzy-logic-widget .flw-tab.active {
  background: var(--md-primary-fg-color);
  color: var(--md-primary-bg-color);
  border-color: var(--md-primary-fg-color);
}
#fuzzy-logic-widget .flw-card {
  border: 1px solid var(--md-default-fg-color--lightest);
  border-radius: 8px;
  padding: 1rem;
  background: var(--md-default-bg-color);
}
#fuzzy-logic-widget .flw-card h4 {
  margin: 0 0 0.4rem 0;
  font-size: 1.1rem;
  font-family: 'JetBrains Mono', 'SF Mono', monospace;
  color: var(--md-primary-fg-color);
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
    <div class="flw-card" id="flw-card">
      <h4 id="flw-name"></h4>
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
    b.textContent = c.name;
    tabsEl.appendChild(b);
  }

  const aSlider = HOST.querySelector('#flw-a');
  const bSlider = HOST.querySelector('#flw-b');
  const aVal = HOST.querySelector('#flw-a-val');
  const bVal = HOST.querySelector('#flw-b-val');
  const nameEl = HOST.querySelector('#flw-name');
  const polyEl = HOST.querySelector('#flw-poly');
  const resultEl = HOST.querySelector('#flw-result');
  const markerEl = HOST.querySelector('#flw-marker');

  let activeId = 'and';

  function fmt(v) { return (v >= 0 ? '+' : '') + v.toFixed(3); }

  function render() {
    const a = parseFloat(aSlider.value);
    const b = parseFloat(bSlider.value);
    aVal.textContent = fmt(a);
    bVal.textContent = fmt(b);
    const c = CONNECTIVES.find(c => c.id === activeId);
    nameEl.textContent = c.name;
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
