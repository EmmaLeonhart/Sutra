/**
 * Sutra — interactive fuzzy-logic explorer.
 *
 * Two sliders for the inputs (a, b) in [-1, +1], snap buttons for
 * the canonical three-valued points (false, unknown, true), and a
 * live card per connective showing:
 *   - Surface composition from the three primitives {!, &&, ||}
 *   - The simplified polynomial form
 *   - The current computed value
 *   - A horizontal bar on the truth axis showing where the value
 *     sits between false (-1), unknown (0), and true (+1)
 *
 * When both a and b are near canonical points the truth-table
 * summary highlights the grid cell we're looking at, so you can
 * confirm the polynomial is producing the right three-valued
 * result.
 *
 * Vanilla JS, no framework, no bundler. Mounts into
 * <div id="fuzzy-logic-widget">.
 *
 * @file
 */

(function () {
  const HOST = document.getElementById('fuzzy-logic-widget');
  if (!HOST) return;

  // --------------------------------------------------------------
  // Connectives — one definition per gate
  // --------------------------------------------------------------

  // NOT(a) applied to just `a`; used inside derived forms.
  const not = (a) => -a;
  const andPoly = (a, b) =>
    (a + b + a * b - a * a - b * b + a * a * b * b) / 2;
  const orPoly = (a, b) =>
    (a + b - a * b + a * a + b * b - a * a * b * b) / 2;

  const CONNECTIVES = [
    {
      id: 'not',
      name: 'NOT',
      surface: '!a',
      composition: 'primitive',
      polynomial: '-a',
      // Unary; b unused.
      fn: (a) => not(a),
      unary: true,
    },
    {
      id: 'and',
      name: 'AND',
      surface: 'a && b',
      composition: 'primitive',
      polynomial: '(a + b + ab − a² − b² + a²b²) / 2',
      fn: (a, b) => andPoly(a, b),
    },
    {
      id: 'or',
      name: 'OR',
      surface: 'a || b',
      composition: 'primitive',
      polynomial: '(a + b − ab + a² + b² − a²b²) / 2',
      fn: (a, b) => orPoly(a, b),
    },
    {
      id: 'nand',
      name: 'NAND',
      surface: '!(a && b)',
      composition: 'negated AND polynomial',
      polynomial: '(−a − b − ab + a² + b² − a²b²) / 2',
      fn: (a, b) => -andPoly(a, b),
    },
    {
      id: 'nor',
      name: 'NOR',
      surface: '!(a || b)',
      composition: 'negated OR polynomial',
      polynomial: '(−a − b + ab − a² − b² + a²b²) / 2',
      fn: (a, b) => -orPoly(a, b),
    },
    {
      id: 'xor',
      name: 'XOR',
      surface: '(a && !b) || (!a && b)',
      composition: 'collapses to a single product',
      polynomial: '−a · b',
      fn: (a, b) => -a * b,
    },
    {
      id: 'iff',
      name: 'IFF',
      surface: '(a → b) && (b → a)',
      composition: 'collapses to a single product',
      polynomial: 'a · b',
      fn: (a, b) => a * b,
    },
    {
      id: 'implies',
      name: '→',
      surface: '!a || b',
      composition: '!a || b (material implication)',
      polynomial: '(−a + b + ab + a² + b² − a²b²) / 2',
      fn: (a, b) => orPoly(not(a), b),
    },
  ];

  // --------------------------------------------------------------
  // Styling — scoped to this widget via an ID prefix
  // --------------------------------------------------------------

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
  min-width: 4.5rem;
}
#fuzzy-logic-widget .flw-row input[type=range] {
  width: 100%;
}
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
  padding: 0.25rem 0.5rem;
  border: 1px solid var(--md-default-fg-color--lighter);
  background: var(--md-default-bg-color);
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85em;
}
#fuzzy-logic-widget .flw-snap button:hover { background: var(--md-accent-fg-color--transparent); }
#fuzzy-logic-widget .flw-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(270px, 1fr));
  gap: 0.75rem;
}
#fuzzy-logic-widget .flw-card {
  border: 1px solid var(--md-default-fg-color--lightest);
  border-radius: 8px;
  padding: 0.75rem 0.9rem;
  background: var(--md-default-bg-color);
}
#fuzzy-logic-widget .flw-card h4 {
  margin: 0 0 0.25rem 0;
  font-size: 1.05rem;
  color: var(--md-primary-fg-color);
}
#fuzzy-logic-widget .flw-surface {
  font-family: 'JetBrains Mono', 'SF Mono', monospace;
  font-size: 0.9em;
  color: var(--md-default-fg-color--light);
  margin-bottom: 0.15rem;
}
#fuzzy-logic-widget .flw-poly {
  font-family: 'JetBrains Mono', 'SF Mono', monospace;
  font-size: 0.8em;
  color: var(--md-default-fg-color--light);
  margin-bottom: 0.5rem;
  word-break: break-word;
}
#fuzzy-logic-widget .flw-result {
  font-family: 'JetBrains Mono', 'SF Mono', monospace;
  font-size: 1rem;
  margin-bottom: 0.35rem;
}
#fuzzy-logic-widget .flw-bar {
  position: relative;
  height: 14px;
  background: linear-gradient(to right,
    #d32f2f 0%, #d32f2f 20%,
    #757575 40%, #757575 60%,
    #388e3c 80%, #388e3c 100%);
  border-radius: 4px;
  margin-top: 0.3rem;
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
#fuzzy-logic-widget .flw-label {
  display: inline-block;
  padding: 0 0.3rem;
  border-radius: 3px;
  font-size: 0.7em;
  font-weight: 600;
  margin-left: 0.4rem;
  color: white;
}
#fuzzy-logic-widget .flw-label.t { background: #388e3c; }
#fuzzy-logic-widget .flw-label.f { background: #d32f2f; }
#fuzzy-logic-widget .flw-label.u { background: #757575; }
`;
  const style = document.createElement('style');
  style.textContent = CSS;
  HOST.appendChild(style);

  // --------------------------------------------------------------
  // DOM
  // --------------------------------------------------------------

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
          <button data-target="flw-a" data-value="-1">false (-1)</button>
          <button data-target="flw-a" data-value="0">unknown (0)</button>
          <button data-target="flw-a" data-value="1">true (+1)</button>
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
          <button data-target="flw-b" data-value="-1">false (-1)</button>
          <button data-target="flw-b" data-value="0">unknown (0)</button>
          <button data-target="flw-b" data-value="1">true (+1)</button>
        </div>
        <span></span>
      </div>
    </div>
    <div class="flw-cards" id="flw-cards"></div>
  `;

  const cardsEl = HOST.querySelector('#flw-cards');
  for (const c of CONNECTIVES) {
    const card = document.createElement('div');
    card.className = 'flw-card';
    card.id = `flw-card-${c.id}`;
    card.innerHTML = `
      <h4>${c.name} <span class="flw-label u" id="flw-label-${c.id}">—</span></h4>
      <div class="flw-surface">${escapeHtml(c.surface)}</div>
      <div class="flw-poly">poly: ${escapeHtml(c.polynomial)}</div>
      <div class="flw-result" id="flw-result-${c.id}">0.000</div>
      <div class="flw-bar"><div class="flw-marker" id="flw-marker-${c.id}" style="left: 50%;"></div></div>
      <div class="flw-axis"><span>false</span><span>unknown</span><span>true</span></div>
    `;
    cardsEl.appendChild(card);
  }

  // --------------------------------------------------------------
  // Wiring
  // --------------------------------------------------------------

  const aSlider = HOST.querySelector('#flw-a');
  const bSlider = HOST.querySelector('#flw-b');
  const aVal = HOST.querySelector('#flw-a-val');
  const bVal = HOST.querySelector('#flw-b-val');

  function labelFor(v) {
    if (v > 0.5) return { cls: 't', text: 'true' };
    if (v < -0.5) return { cls: 'f', text: 'false' };
    return { cls: 'u', text: 'unk' };
  }

  function fmt(v) {
    const s = v >= 0 ? '+' : '';
    return s + v.toFixed(3);
  }

  function render() {
    const a = parseFloat(aSlider.value);
    const b = parseFloat(bSlider.value);
    aVal.textContent = fmt(a);
    bVal.textContent = fmt(b);
    for (const c of CONNECTIVES) {
      const val = c.unary ? c.fn(a) : c.fn(a, b);
      const clamped = Math.max(-1, Math.min(1, val));
      const leftPct = ((clamped + 1) / 2) * 100;
      HOST.querySelector(`#flw-result-${c.id}`).textContent = fmt(val);
      HOST.querySelector(`#flw-marker-${c.id}`).style.left = `${leftPct}%`;
      const lab = labelFor(val);
      const labEl = HOST.querySelector(`#flw-label-${c.id}`);
      labEl.className = `flw-label ${lab.cls}`;
      labEl.textContent = lab.text;
    }
  }

  aSlider.addEventListener('input', render);
  bSlider.addEventListener('input', render);

  for (const btn of HOST.querySelectorAll('.flw-snap button')) {
    btn.addEventListener('click', () => {
      const target = btn.dataset.target;
      const v = parseFloat(btn.dataset.value);
      HOST.querySelector('#' + target).value = v;
      render();
    });
  }

  function escapeHtml(s) {
    return s
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  render();
})();
