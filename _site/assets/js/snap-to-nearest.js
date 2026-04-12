/**
 * Sutra — interactive snap-to-nearest widget.
 *
 * A 2D codebook of named atoms is rendered as labeled points. The
 * user drags the "query" point; the widget draws a line to the
 * nearest codebook entry and reports the cosine similarity. A
 * noise slider perturbs the query around a chosen target to show
 * the failure mode — when the query drifts past the Voronoi
 * boundary, the snap returns the wrong atom.
 *
 * Vanilla JS + SVG, no framework. Mounts into
 * <div id="snap-widget">.
 *
 * @file
 */

(function () {
  const HOST = document.getElementById('snap-widget');
  if (!HOST) return;

  const W = 420, H = 320;
  const CODEBOOK = [
    { name: 'cat',   x: 100, y: 90  },
    { name: 'dog',   x: 160, y: 140 },
    { name: 'mouse', x: 250, y: 100 },
    { name: 'bird',  x: 330, y: 180 },
    { name: 'fish',  x: 100, y: 240 },
    { name: 'lion',  x: 300, y: 260 },
  ];

  const state = { qx: 200, qy: 200, target: 'cat', noise: 0 };

  function nearest(x, y) {
    let best = null, bestD = Infinity;
    for (const c of CODEBOOK) {
      const d = (c.x - x) ** 2 + (c.y - y) ** 2;
      if (d < bestD) { bestD = d; best = c; }
    }
    return { atom: best, dist: Math.sqrt(bestD) };
  }

  function cosine(ax, ay, bx, by) {
    const na = Math.sqrt(ax * ax + ay * ay);
    const nb = Math.sqrt(bx * bx + by * by);
    return (ax * bx + ay * by) / (na * nb + 1e-9);
  }

  function applyNoiseFromTarget() {
    const target = CODEBOOK.find(c => c.name === state.target);
    const r = state.noise;
    const theta = hashAngle(state.target, r);
    state.qx = target.x + Math.cos(theta) * r * 80;
    state.qy = target.y + Math.sin(theta) * r * 80;
  }

  function hashAngle(s, r) {
    let h = 0;
    for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
    return ((h ^ Math.floor(r * 1000)) % 6283) / 1000;
  }

  function render() {
    const { atom, dist } = nearest(state.qx, state.qy);
    const target = CODEBOOK.find(c => c.name === state.target);
    const sim = cosine(state.qx - W / 2, state.qy - H / 2, atom.x - W / 2, atom.y - H / 2);
    const correct = atom.name === state.target;

    const points = CODEBOOK.map(c => `
      <circle cx="${c.x}" cy="${c.y}" r="6" fill="${c.name === state.target ? '#ff9800' : '#7c4dff'}" />
      <text x="${c.x + 10}" y="${c.y + 4}" font-size="12" fill="currentColor">${c.name}</text>
    `).join('');

    const voronoiHint = CODEBOOK.map(c =>
      `<circle cx="${c.x}" cy="${c.y}" r="3" fill="none" stroke="currentColor" stroke-opacity="0.1" stroke-dasharray="2,2" />`
    ).join('');

    HOST.innerHTML = `
      <div style="padding:1em;border:1px solid var(--md-default-fg-color--lightest);border-radius:6px;">
        <div style="margin-bottom:.8em;">
          <label>target filler: <select id="snap-target">${CODEBOOK.map(c => `<option ${c.name === state.target ? 'selected' : ''}>${c.name}</option>`).join('')}</select></label>
          &nbsp;&nbsp;
          <label>noise: <input type="range" id="snap-noise" min="0" max="1" step="0.02" value="${state.noise}" style="vertical-align:middle"> <span>${state.noise.toFixed(2)}</span></label>
        </div>
        <svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" style="border:1px solid var(--md-default-fg-color--lightest);border-radius:4px;cursor:crosshair;display:block;">
          ${voronoiHint}
          <line x1="${state.qx}" y1="${state.qy}" x2="${atom.x}" y2="${atom.y}" stroke="${correct ? '#4caf50' : '#ff5252'}" stroke-width="2" stroke-dasharray="4,3" />
          ${points}
          <circle id="snap-query" cx="${state.qx}" cy="${state.qy}" r="8" fill="#ffeb3b" stroke="#000" stroke-width="1.5" style="cursor:grab;" />
          <text x="${state.qx + 10}" y="${state.qy - 10}" font-size="12" fill="currentColor">query</text>
        </svg>
        <div style="margin-top:.6em;padding:.5em;background:var(--md-code-bg-color);border-radius:4px;font-family:var(--md-code-font)">
          target = <strong>${state.target}</strong>,
          snap(query) → <strong>${atom.name}</strong>
          (distance ${dist.toFixed(1)}, cosine ${sim.toFixed(3)})
          ${correct ? '<span style="color:#4caf50;"> ✓ recovered target</span>' : '<span style="color:#ff5252;"> ✗ snapped to wrong atom</span>'}
        </div>
        <div style="margin-top:.5em;font-size:.9em;color:var(--md-default-fg-color--light);">
          Drag the yellow query point, or turn up the noise slider to see the query drift away from its target.
          Snap returns the correct atom as long as the query stays on the target's side of the Voronoi boundary with its neighbors.
          When noise pushes the query past that boundary, snap fails — and you need a larger codebook spacing or a cleaner upstream computation.
        </div>
      </div>
    `;

    const svg = HOST.querySelector('svg');
    const q = HOST.querySelector('#snap-query');
    let dragging = false;

    function setFromEvent(ev) {
      const rect = svg.getBoundingClientRect();
      const scaleX = W / rect.width, scaleY = H / rect.height;
      const cx = (ev.touches ? ev.touches[0].clientX : ev.clientX) - rect.left;
      const cy = (ev.touches ? ev.touches[0].clientY : ev.clientY) - rect.top;
      state.qx = Math.max(10, Math.min(W - 10, cx * scaleX));
      state.qy = Math.max(10, Math.min(H - 10, cy * scaleY));
      render();
    }
    q.addEventListener('mousedown', () => { dragging = true; });
    window.addEventListener('mouseup', () => { dragging = false; });
    window.addEventListener('mousemove', (ev) => { if (dragging) setFromEvent(ev); });
    svg.addEventListener('click', setFromEvent);

    document.getElementById('snap-target').onchange = e => {
      state.target = e.target.value;
      applyNoiseFromTarget();
      render();
    };
    document.getElementById('snap-noise').oninput = e => {
      state.noise = +e.target.value;
      applyNoiseFromTarget();
      render();
    };
  }

  render();
})();
