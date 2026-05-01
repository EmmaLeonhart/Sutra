/**
 * Sutra — interactive bind/unbind widget.
 *
 * Demonstrates the bind/unbind/bundle/crosstalk shape: user picks
 * a role and filler, sees the bound vector (dissimilar to both),
 * then sees the recovered filler after unbind. A "bundle depth"
 * slider shows how crosstalk grows with more role-filler pairs
 * bundled together — the empirical motivation for snap-to-nearest
 * (next tutorial).
 *
 * The widget itself uses sign-flip binding (a retired VSA
 * mechanism) for visual simplicity — Sutra's actual runtime uses
 * rotation binding (Q_role @ filler with cached Haar-random
 * orthogonal Q). The bundle / crosstalk / cleanup shape the widget
 * shows is the same shape rotation binding has; the per-step
 * arithmetic is different. See tutorials/02-bind-and-unbind.md for
 * the caveat in the rendered page.
 *
 * Vanilla JS, no framework, no bundler. Mounts into
 * <div id="bind-unbind-widget">.
 *
 * @file
 */

(function () {
  const HOST = document.getElementById('bind-unbind-widget');
  if (!HOST) return;

  const DIM = 32;
  const ATOMS = ['cat', 'dog', 'mouse', 'bird', 'fish', 'lion'];
  const ROLES = ['agent', 'action', 'object', 'location'];

  function seededRand(seed) {
    let s = seed | 0;
    return () => {
      s = (s * 1103515245 + 12345) & 0x7fffffff;
      return s / 0x7fffffff;
    };
  }

  function makeVec(name) {
    const r = seededRand(hashString(name));
    const v = new Float32Array(DIM);
    let n = 0;
    for (let i = 0; i < DIM; i++) {
      v[i] = r() * 2 - 1;
      n += v[i] * v[i];
    }
    n = Math.sqrt(n);
    for (let i = 0; i < DIM; i++) v[i] /= n;
    return v;
  }

  function hashString(s) {
    let h = 2166136261;
    for (let i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = (h * 16777619) >>> 0;
    }
    return h;
  }

  function bind(a, b) {
    const out = new Float32Array(DIM);
    for (let i = 0; i < DIM; i++) out[i] = a[i] * Math.sign(b[i] || 1);
    return out;
  }

  function add(a, b) {
    const out = new Float32Array(DIM);
    for (let i = 0; i < DIM; i++) out[i] = a[i] + b[i];
    return out;
  }

  function cosine(a, b) {
    let dot = 0, na = 0, nb = 0;
    for (let i = 0; i < DIM; i++) { dot += a[i] * b[i]; na += a[i] * a[i]; nb += b[i] * b[i]; }
    return dot / (Math.sqrt(na) * Math.sqrt(nb) + 1e-9);
  }

  function snap(v) {
    let best = null, bestSim = -2;
    for (const name of ATOMS) {
      const sim = cosine(v, makeVec(name));
      if (sim > bestSim) { bestSim = sim; best = name; }
    }
    return { name: best, sim: bestSim };
  }

  function renderVec(vec, label) {
    const max = Math.max(...vec.map(Math.abs));
    const bars = Array.from(vec).map(v => {
      const h = Math.abs(v) / max * 28;
      const color = v >= 0 ? '#7c4dff' : '#ff5252';
      return `<span style="display:inline-block;width:6px;height:30px;vertical-align:middle;position:relative;">
        <span style="display:block;position:absolute;bottom:15px;left:1px;width:4px;height:${v >= 0 ? h : 0}px;background:${color};"></span>
        <span style="display:block;position:absolute;top:15px;left:1px;width:4px;height:${v < 0 ? h : 0}px;background:${color};"></span>
      </span>`;
    }).join('');
    return `<div style="margin:.3em 0"><strong style="display:inline-block;width:9em;">${label}</strong>${bars}</div>`;
  }

  const state = { role: 'agent', filler: 'cat', bundleDepth: 1 };

  function update() {
    const role = makeVec(state.role);
    const filler = makeVec(state.filler);
    const bound = bind(filler, role);

    let bundled = bound;
    const extraPairs = [];
    for (let k = 1; k < state.bundleDepth; k++) {
      const extraRole = ROLES[k % ROLES.length];
      const extraFiller = ATOMS[(k + 2) % ATOMS.length];
      extraPairs.push(`${extraRole}=${extraFiller}`);
      const r = makeVec(extraRole), f = makeVec(extraFiller);
      bundled = add(bundled, bind(f, r));
    }
    const recovered = bind(bundled, role);
    const simToFiller = cosine(recovered, filler);
    const snapped = snap(recovered);

    const extraStr = extraPairs.length ? `, plus ${extraPairs.join(', ')}` : '';
    HOST.innerHTML = `
      <div style="padding:1em;border:1px solid var(--md-default-fg-color--lightest);border-radius:6px;">
        <div style="margin-bottom:.8em;">
          <label>role: <select id="bu-role">${ROLES.map(r => `<option ${r === state.role ? 'selected' : ''}>${r}</option>`).join('')}</select></label>
          &nbsp;&nbsp;
          <label>filler: <select id="bu-filler">${ATOMS.map(a => `<option ${a === state.filler ? 'selected' : ''}>${a}</option>`).join('')}</select></label>
          &nbsp;&nbsp;
          <label>bundle depth: <input type="range" id="bu-depth" min="1" max="4" value="${state.bundleDepth}" style="vertical-align:middle"> <span>${state.bundleDepth}</span></label>
        </div>
        ${renderVec(role, 'role = ' + state.role)}
        ${renderVec(filler, 'filler = ' + state.filler)}
        ${renderVec(bound, 'bind(filler, role)')}
        ${state.bundleDepth > 1 ? renderVec(bundled, 'bundle (depth ' + state.bundleDepth + ')') : ''}
        ${renderVec(recovered, 'unbind(role, bundle)')}
        <div style="margin-top:.8em;padding:.5em;background:var(--md-code-bg-color);border-radius:4px;font-family:var(--md-code-font)">
          cosine(recovered, ${state.filler}) = <strong>${simToFiller.toFixed(3)}</strong><br>
          snap(recovered) → <strong>${snapped.name}</strong> (sim ${snapped.sim.toFixed(3)})
          ${snapped.name === state.filler ? '<span style="color:#4caf50;"> ✓ recovered</span>' : '<span style="color:#ff5252;"> ✗ crosstalk corrupted this</span>'}
        </div>
        <div style="margin-top:.5em;font-size:.9em;color:var(--md-default-fg-color--light);">
          Raising bundle depth adds ${ROLES.length > 1 ? 'more role-filler pairs' : 'pairs'} to the superposition${extraStr ? '. Extra pairs: ' + extraStr.slice(2) : ''}. Watch how crosstalk grows and eventually beats the signal — that's exactly why <code>snap</code> exists.
        </div>
      </div>
    `;

    document.getElementById('bu-role').onchange = e => { state.role = e.target.value; update(); };
    document.getElementById('bu-filler').onchange = e => { state.filler = e.target.value; update(); };
    document.getElementById('bu-depth').oninput = e => { state.bundleDepth = +e.target.value; update(); };
  }

  update();
})();
