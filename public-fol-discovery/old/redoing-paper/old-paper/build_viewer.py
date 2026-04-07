"""Build the embedding space viewer HTML with 485 nouns projected onto semantic axes.

Uses pre-computed projections + PCA-reduced vectors for client-side axis changing.
All unicode characters are written directly (no \\u escapes in HTML).
"""
import json

with open('prototype/viewer_data.json') as f:
    viewer_json = f.read()

html = u'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <meta property="og:type" content="website">
  <meta property="og:title" content="Beyond Proximity: Embedding Space Viewer">
  <meta property="og:description" content="Interactive Voronoi map of 485 word embeddings projected onto custom semantic axes defined by man, woman, boy, and girl. Explore how words organize in high-dimensional space.">
  <meta property="og:url" content="https://emmaleonhart.com/">
  <meta property="og:site_name" content="Beyond Proximity">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="Beyond Proximity: Embedding Space Viewer">
  <meta name="twitter:description" content="Interactive map of word embeddings. Explore how words organize in high-dimensional space.">
  <meta name="description" content="Interactive Voronoi map of 485 word embeddings projected onto custom semantic axes. Part of the Beyond Proximity neurosymbolic research project.">
  <title>Beyond Proximity \u2014 Embedding Space Viewer</title>
  <script src="https://d3js.org/d3.v7.min.js"></script>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
      background: #0a0a0f;
      color: #e0e0e0;
      overflow: hidden;
      height: 100vh;
      height: 100dvh;
    }
    #header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 16px;
      background: #111118;
      border-bottom: 1px solid #2a2a35;
      height: 48px;
      z-index: 10;
      gap: 8px;
    }
    #header h1 {
      font-size: 16px;
      font-weight: 600;
      color: #c0c0d0;
      letter-spacing: 0.5px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      min-width: 0;
    }
    #header h1 span { color: #7c8cf8; }
    #header-right {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-shrink: 0;
    }
    #search {
      background: #1a1a25;
      border: 1px solid #3a3a45;
      color: #e0e0e0;
      padding: 6px 12px;
      border-radius: 4px;
      font-size: 13px;
      width: 220px;
      outline: none;
    }
    #search:focus { border-color: #7c8cf8; }
    #search::placeholder { color: #666; }
    #sidebar-toggle {
      display: none;
      background: #1a1a25;
      border: 1px solid #3a3a45;
      color: #e0e0e0;
      padding: 6px 10px;
      border-radius: 4px;
      font-size: 16px;
      cursor: pointer;
      line-height: 1;
    }
    #sidebar-toggle:hover { background: #252535; }
    #main {
      display: flex;
      height: calc(100vh - 48px - 32px);
      height: calc(100dvh - 48px - 32px);
    }
    #sidebar {
      width: 260px;
      min-width: 260px;
      background: #111118;
      border-right: 1px solid #2a2a35;
      padding: 12px;
      overflow-y: auto;
      font-size: 12px;
      z-index: 15;
      transition: transform 0.25s ease;
    }
    #sidebar h3 {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: #888;
      margin: 14px 0 6px 0;
    }
    #sidebar h3:first-child { margin-top: 0; }
    .info-text {
      font-size: 11px;
      color: #999;
      line-height: 1.5;
      margin-bottom: 8px;
    }
    .legend-item {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 3px 0;
    }
    .legend-dot {
      width: 10px;
      height: 10px;
      border-radius: 2px;
      flex-shrink: 0;
    }
    .legend-label { color: #ccc; font-size: 11px; }

    /* Custom Axis Inputs */
    .axis-group { margin-bottom: 10px; }
    .axis-group-label { font-size: 11px; color: #aaa; margin-bottom: 4px; font-weight: 600; }
    .axis-row { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
    .axis-arrow { color: #666; font-size: 12px; flex-shrink: 0; }
    .axis-input {
      background: #1a1a25;
      border: 1px solid #3a3a45;
      color: #e0e0e0;
      padding: 4px 8px;
      border-radius: 3px;
      font-size: 12px;
      width: 100%;
      outline: none;
      font-family: inherit;
    }
    .axis-input:focus { border-color: #7c8cf8; }
    .axis-input::placeholder { color: #555; }
    .axis-input.invalid { border-color: #e74c3c; }
    .axis-input.valid { border-color: #2ecc71; }
    #apply-axes {
      display: block;
      width: 100%;
      padding: 6px 12px;
      margin-top: 8px;
      background: #7c8cf8;
      border: none;
      border-radius: 4px;
      color: #fff;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.2s;
    }
    #apply-axes:hover { background: #6b7be8; }
    #apply-axes:disabled { background: #3a3a55; color: #666; cursor: not-allowed; }
    #axis-status { font-size: 10px; color: #888; margin-top: 4px; min-height: 14px; }
    #reset-axes {
      background: none;
      border: 1px solid #3a3a45;
      color: #999;
      padding: 4px 8px;
      border-radius: 3px;
      font-size: 11px;
      cursor: pointer;
      margin-top: 4px;
      display: block;
      width: 100%;
    }
    #reset-axes:hover { border-color: #7c8cf8; color: #ccc; }

    .pole-item {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 4px 0;
      cursor: pointer;
      transition: opacity 0.2s;
    }
    .pole-item:hover { opacity: 0.8; }
    .pole-dot {
      width: 12px;
      height: 12px;
      border-radius: 50%;
      border: 2px solid;
      flex-shrink: 0;
    }
    .pole-label { color: #e0e0e0; font-weight: 600; font-size: 12px; }
    #detail-panel {
      margin-top: 16px;
      padding-top: 12px;
      border-top: 1px solid #2a2a35;
      display: none;
    }
    #detail-panel h3 { color: #7c8cf8; }
    #detail-label { font-size: 14px; font-weight: 600; color: #e0e0e0; margin: 4px 0; }
    #detail-coords { font-size: 11px; color: #888; margin-bottom: 8px; }
    #neighbors-list { list-style: none; padding: 0; }
    #neighbors-list li {
      padding: 2px 0;
      color: #aaa;
      font-size: 11px;
      display: flex;
      justify-content: space-between;
    }
    #neighbors-list li .dist { color: #666; }
    #paper-link {
      display: block;
      margin-top: 16px;
      padding: 8px 12px;
      background: #1a1a25;
      border: 1px solid #3a3a45;
      border-radius: 4px;
      color: #7c8cf8;
      text-decoration: none;
      font-size: 12px;
      text-align: center;
      transition: background 0.2s;
    }
    #paper-link:hover { background: #252535; }
    #canvas-wrap { flex: 1; position: relative; overflow: hidden; }
    canvas { display: block; cursor: crosshair; touch-action: none; }
    #tooltip {
      position: absolute;
      pointer-events: none;
      background: rgba(15, 15, 25, 0.95);
      border: 1px solid #3a3a45;
      border-radius: 4px;
      padding: 8px 12px;
      font-size: 12px;
      color: #e0e0e0;
      display: none;
      z-index: 20;
      max-width: 280px;
      white-space: nowrap;
    }
    #tooltip .tt-label { font-weight: 600; font-size: 13px; }
    #tooltip .tt-coords { color: #888; font-size: 11px; margin-top: 2px; }
    #tooltip .tt-regime { font-size: 11px; margin-top: 3px; }
    #footer {
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 16px;
      background: #111118;
      border-top: 1px solid #2a2a35;
      font-size: 11px;
      color: #666;
      gap: 8px;
    }
    #footer a { color: #7c8cf8; text-decoration: none; }
    #footer a:hover { text-decoration: underline; }
    #footer-info { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
    #zoom-info { color: #555; white-space: nowrap; flex-shrink: 0; }
    .regime-badge { display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 10px; font-weight: 600; }
    .regime-over { background: rgba(231,76,60,0.4); color: #ff6b5a; }
    .regime-neuro { background: rgba(46,204,113,0.4); color: #5ddb9e; }
    .regime-under { background: rgba(52,152,219,0.4); color: #5dade2; }

    #sidebar-overlay {
      display: none;
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0,0,0,0.5);
      z-index: 14;
    }

    @media (max-width: 768px) {
      #header h1 { font-size: 14px; }
      #search { width: 140px; font-size: 12px; padding: 5px 8px; }
      #sidebar-toggle { display: block; }
      #sidebar {
        position: fixed;
        top: 48px; left: 0; bottom: 32px;
        width: 280px; min-width: auto;
        transform: translateX(-100%);
      }
      #sidebar.open { transform: translateX(0); }
      #sidebar-overlay.open { display: block; }
      #footer { padding: 0 8px; font-size: 10px; }
      #footer-info { display: none; }
    }
    @media (max-width: 480px) {
      #header { padding: 8px 10px; }
      #header h1 { font-size: 13px; }
      #header h1 .subtitle { display: none; }
      #search { width: 110px; font-size: 11px; }
    }
  </style>
</head>
<body>
  <div id="header">
    <h1><span>Beyond Proximity</span><span class="subtitle"> &mdash; Embedding Space Viewer</span></h1>
    <div id="header-right">
      <input type="text" id="search" placeholder="Search words..." autocomplete="off">
      <button id="sidebar-toggle" aria-label="Toggle sidebar">&#9776;</button>
    </div>
  </div>
  <div id="main">
    <div id="sidebar-overlay"></div>
    <div id="sidebar">
      <h3>Custom Axes</h3>
      <div class="info-text">
        Type any words to define semantic axes.
        X-axis goes left&rarr;right. Y-axis is orthogonalized.
      </div>
      <div class="axis-group">
        <div class="axis-group-label">X-Axis</div>
        <div class="axis-row">
          <span class="axis-arrow">&larr;</span>
          <input type="text" class="axis-input" id="x-neg" value="man" placeholder="e.g. man" autocomplete="off">
        </div>
        <div class="axis-row">
          <span class="axis-arrow">&rarr;</span>
          <input type="text" class="axis-input" id="x-pos" value="woman" placeholder="e.g. woman" autocomplete="off">
        </div>
      </div>
      <div class="axis-group">
        <div class="axis-group-label">Y-Axis</div>
        <div class="axis-row">
          <span class="axis-arrow">&darr;</span>
          <input type="text" class="axis-input" id="y-neg" value="man" placeholder="e.g. man" autocomplete="off">
          <span style="color:#555;font-size:10px">+</span>
          <input type="text" class="axis-input" id="y-neg2" value="woman" placeholder="" autocomplete="off">
        </div>
        <div class="axis-row">
          <span class="axis-arrow">&uarr;</span>
          <input type="text" class="axis-input" id="y-pos" value="boy" placeholder="e.g. boy" autocomplete="off">
          <span style="color:#555;font-size:10px">+</span>
          <input type="text" class="axis-input" id="y-pos2" value="girl" placeholder="" autocomplete="off">
        </div>
      </div>
      <button id="apply-axes">Reproject Axes</button>
      <button id="reset-axes">Reset to default</button>
      <div id="axis-status"></div>

      <h3>Current Poles</h3>
      <div id="pole-legend"></div>

      <h3>Density Regimes</h3>
      <div class="info-text">
        Cell size reveals embedding density. Small cells = many nearby words.
      </div>
      <div class="legend-item">
        <div class="legend-dot" style="background: rgba(231,76,60,0.7);"></div>
        <span class="legend-label"><strong>Oversymbolic</strong> &mdash; dense packing</span>
      </div>
      <div class="legend-item">
        <div class="legend-dot" style="background: rgba(46,204,113,0.7);"></div>
        <span class="legend-label"><strong>Neurosymbolic</strong> &mdash; balanced</span>
      </div>
      <div class="legend-item">
        <div class="legend-dot" style="background: rgba(52,152,219,0.7);"></div>
        <span class="legend-label"><strong>Undersymbolic</strong> &mdash; sparse</span>
      </div>

      <div id="detail-panel">
        <h3>Selected</h3>
        <div id="detail-label"></div>
        <div id="detail-coords"></div>
        <h3 style="margin-top:8px">Nearest Neighbors</h3>
        <ul id="neighbors-list"></ul>
      </div>

      <a id="paper-link" href="paper/">Read the Paper &rarr;</a>
    </div>
    <div id="canvas-wrap">
      <canvas id="canvas"></canvas>
      <div id="tooltip">
        <div class="tt-label"></div>
        <div class="tt-coords"></div>
        <div class="tt-regime"></div>
      </div>
    </div>
  </div>
  <div id="footer">
    <span id="footer-info">485 words &middot; Word2Vec (Google News) &middot; Custom axis projection</span>
    <span id="zoom-info">Scroll to zoom &middot; Drag to pan</span>
    <span>Research by <a href="paper/">Emma Leonhart</a></span>
  </div>

  <script>
  // ============================================================
  // DATA
  // ============================================================
  const VIEWER_DATA = ''' + viewer_json + ''';
  const DEFAULT_PROJ = VIEWER_DATA.proj;
  const PCA = VIEWER_DATA.pca;

  // Build label -> index for PCA vectors
  const pcaLabelIndex = {};
  PCA.labels.forEach((l, i) => { pcaLabelIndex[l] = i; });

  // ============================================================
  // AXIS PROJECTION ENGINE (client-side)
  // ============================================================
  // PCA vectors are int8 quantized. Reconstruct: float = quantized * scale / 127
  function getPcaVec(word) {
    const idx = pcaLabelIndex[word];
    if (idx === undefined) return null;
    const q = PCA.vectors[idx];
    const n = q.length;
    const v = new Float64Array(n);
    for (let i = 0; i < n; i++) v[i] = q[i] * PCA.scales[i] / 127;
    return v;
  }

  function vecSub(a, b) { const r = new Float64Array(a.length); for (let i = 0; i < a.length; i++) r[i] = a[i] - b[i]; return r; }
  function vecAdd(a, b) { const r = new Float64Array(a.length); for (let i = 0; i < a.length; i++) r[i] = a[i] + b[i]; return r; }
  function vecScale(a, s) { const r = new Float64Array(a.length); for (let i = 0; i < a.length; i++) r[i] = a[i] * s; return r; }
  function vecDot(a, b) { let s = 0; for (let i = 0; i < a.length; i++) s += a[i] * b[i]; return s; }
  function vecNorm(a) { return Math.sqrt(vecDot(a, a)); }
  function vecNormalize(a) { const n = vecNorm(a); return n > 0 ? vecScale(a, 1/n) : a; }

  function projectOntoAxes(xNeg, xPos, yNegWords, yPosWords) {
    const vXNeg = getPcaVec(xNeg);
    const vXPos = getPcaVec(xPos);
    if (!vXNeg || !vXPos) return null;

    let xAxis = vecNormalize(vecSub(vXPos, vXNeg));

    const yNegVecs = yNegWords.map(getPcaVec).filter(Boolean);
    const yPosVecs = yPosWords.map(getPcaVec).filter(Boolean);
    if (yNegVecs.length === 0 || yPosVecs.length === 0) return null;

    let yNegCenter = yNegVecs.reduce((a, b) => vecAdd(a, b));
    yNegCenter = vecScale(yNegCenter, 1 / yNegVecs.length);
    let yPosCenter = yPosVecs.reduce((a, b) => vecAdd(a, b));
    yPosCenter = vecScale(yPosCenter, 1 / yPosVecs.length);

    const yRaw = vecSub(yPosCenter, yNegCenter);
    const yOrth = vecSub(yRaw, vecScale(xAxis, vecDot(yRaw, xAxis)));
    if (vecNorm(yOrth) < 1e-8) return null;
    const yAxis = vecNormalize(yOrth);

    const allPoles = [vXNeg, vXPos, ...yNegVecs, ...yPosVecs];
    let center = new Float64Array(vXNeg.length);
    for (const v of allPoles) for (let i = 0; i < v.length; i++) center[i] += v[i];
    center = vecScale(center, 1 / allPoles.length);

    const result = [];
    for (let i = 0; i < PCA.labels.length; i++) {
      const v = getPcaVec(PCA.labels[i]);
      const c = vecSub(v, center);
      result.push({
        l: PCA.labels[i],
        x: Math.round(vecDot(c, xAxis) * 10000) / 10000,
        y: Math.round(vecDot(c, yAxis) * 10000) / 10000
      });
    }
    return result;
  }

  // ============================================================
  // STATE
  // ============================================================
  const POLE_COLORS = ['#4a9eff', '#ff6b9d', '#54d5ff', '#ff9de0', '#ffd700', '#7cff8c'];
  let POLES = {};
  let POLE_SET = new Set();
  let xAxisLabel = { neg: 'man', pos: 'woman' };
  let yAxisLabel = { neg: 'adult', pos: 'young' };

  function updatePoles(poleWords) {
    POLES = {};
    poleWords.forEach((w, i) => {
      POLES[w] = { color: POLE_COLORS[i % POLE_COLORS.length] };
    });
    POLE_SET = new Set(Object.keys(POLES));
    updatePoleLegend();
  }

  function updatePoleLegend() {
    const container = document.getElementById('pole-legend');
    container.innerHTML = '';
    for (const [word, cfg] of Object.entries(POLES)) {
      const el = document.createElement('div');
      el.className = 'pole-item';
      el.innerHTML = '<div class="pole-dot" style="background:' + cfg.color + ';border-color:' + cfg.color + ';"></div><div><span class="pole-label">' + word + '</span></div>';
      el.addEventListener('click', () => {
        const idx = labelIndex[word];
        if (idx !== undefined) {
          selectedIdx = idx;
          showDetail(idx);
          panToPoint(idx, 4);
        }
      });
      container.appendChild(el);
    }
  }

  updatePoles(['man', 'woman', 'boy', 'girl']);

  const NOTABLE = new Set([
    'king', 'queen', 'prince', 'princess',
    'father', 'mother', 'son', 'daughter',
    'husband', 'wife', 'brother', 'sister',
    'dog', 'cat', 'car', 'house', 'water', 'fire',
    'love', 'war', 'death', 'life', 'time', 'world'
  ]);

  let points = [];
  let N = 0;
  let labelIndex = {};
  let dataW, dataH, dataCx, dataCy;

  function loadProjection(data) {
    points = data.map(function(d, i) {
      return {
        idx: i,
        label: d.l,
        x: d.x,
        y: d.y,
        isPole: POLE_SET.has(d.l),
        isNotable: NOTABLE.has(d.l)
      };
    });
    N = points.length;
    labelIndex = {};
    points.forEach(function(p, i) { labelIndex[p.label] = i; });

    var xe = d3.extent(points, function(d) { return d.x; });
    var ye = d3.extent(points, function(d) { return d.y; });
    dataW = xe[1] - xe[0];
    dataH = ye[1] - ye[0];
    dataCx = (xe[0] + xe[1]) / 2;
    dataCy = (ye[0] + ye[1]) / 2;
  }

  loadProjection(DEFAULT_PROJ);

  // ============================================================
  // CANVAS
  // ============================================================
  var canvasWrap = document.getElementById('canvas-wrap');
  var canvas = document.getElementById('canvas');
  var ctx = canvas.getContext('2d');
  var W, H;

  function resize() {
    W = canvasWrap.clientWidth;
    H = canvasWrap.clientHeight;
    canvas.width = W * devicePixelRatio;
    canvas.height = H * devicePixelRatio;
    canvas.style.width = W + 'px';
    canvas.style.height = H + 'px';
    ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
  }
  resize();
  window.addEventListener('resize', function() { resize(); draw(); });

  function getScale() {
    var pad = 40;
    var sx = (W - 2 * pad) / dataW;
    var sy = (H - 2 * pad) / dataH;
    return Math.min(sx, sy);
  }

  function dataToScreen(x, y, transform) {
    var s = getScale();
    var sx = W / 2 + (x - dataCx) * s;
    var sy = H / 2 - (y - dataCy) * s;
    return transform.apply([sx, sy]);
  }

  var currentTransform = d3.zoomIdentity;

  function computeVoronoi(transform) {
    var screenPts = points.map(function(p) { return dataToScreen(p.x, p.y, transform); });
    var delaunay = d3.Delaunay.from(screenPts);
    var voronoi = delaunay.voronoi([0, 0, W, H]);
    return { delaunay: delaunay, voronoi: voronoi, screenPts: screenPts };
  }

  function classifyCells(voronoi) {
    var areas = [];
    for (var i = 0; i < N; i++) {
      var cell = voronoi.cellPolygon(i);
      if (cell) {
        var area = 0;
        for (var j = 0; j < cell.length; j++) {
          var j1 = (j + 1) % cell.length;
          area += cell[j][0] * cell[j1][1] - cell[j1][0] * cell[j][1];
        }
        areas.push(Math.abs(area) / 2);
      } else {
        areas.push(Infinity);
      }
    }
    var finite = areas.filter(function(a) { return isFinite(a) && a > 0; }).map(function(a) { return Math.log(a); });
    finite.sort(function(a, b) { return a - b; });
    var t1 = finite[Math.floor(finite.length / 3)];
    var t2 = finite[Math.floor(2 * finite.length / 3)];
    return areas.map(function(a) {
      if (!isFinite(a) || a <= 0) return 'under';
      var la = Math.log(a);
      if (la <= t1) return 'over';
      if (la <= t2) return 'neuro';
      return 'under';
    });
  }

  var hoveredIdx = -1;
  var selectedIdx = -1;
  var searchMatches = null;

  // ============================================================
  // DRAW
  // ============================================================
  function draw() {
    var transform = currentTransform;
    var computed = computeVoronoi(transform);
    var delaunay = computed.delaunay;
    var voronoi = computed.voronoi;
    var screenPts = computed.screenPts;
    var regimes = classifyCells(voronoi);

    ctx.save();
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = '#0a0a0f';
    ctx.fillRect(0, 0, W, H);

    // Regime-colored cells
    for (var i = 0; i < N; i++) {
      var cell = voronoi.cellPolygon(i);
      if (!cell) continue;
      var regime = regimes[i];
      var fill;
      if (regime === 'over') fill = 'rgba(231,76,60,0.25)';
      else if (regime === 'neuro') fill = 'rgba(46,204,113,0.18)';
      else fill = 'rgba(52,152,219,0.12)';
      ctx.beginPath();
      ctx.moveTo(cell[0][0], cell[0][1]);
      for (var j = 1; j < cell.length; j++) ctx.lineTo(cell[j][0], cell[j][1]);
      ctx.closePath();
      ctx.fillStyle = fill;
      ctx.fill();
    }

    // Voronoi edges
    ctx.strokeStyle = 'rgba(80,80,100,0.25)';
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    voronoi.render(ctx);
    ctx.stroke();

    // Points
    var zoom = transform.k;
    var baseR = Math.max(1.5, Math.min(4, 2 * zoom));

    for (var i = 0; i < N; i++) {
      var p = points[i];
      var sx = screenPts[i][0], sy = screenPts[i][1];
      if (sx < -20 || sx > W + 20 || sy < -20 || sy > H + 20) continue;

      var highlight = false;
      var dimmed = false;
      if (searchMatches) {
        if (!searchMatches.has(i)) dimmed = true;
        else highlight = true;
      }
      if (i === hoveredIdx || i === selectedIdx) highlight = true;

      if (p.isPole) {
        var poleColor = POLES[p.label] ? POLES[p.label].color : '#fff';
        ctx.globalAlpha = dimmed ? 0.2 : 1.0;
        ctx.beginPath();
        ctx.arc(sx, sy, baseR * 2.5, 0, Math.PI * 2);
        ctx.fillStyle = poleColor;
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 1.5;
        ctx.stroke();
      } else {
        ctx.globalAlpha = dimmed ? 0.05 : (highlight ? 0.9 : 0.6);
        ctx.beginPath();
        ctx.arc(sx, sy, highlight ? baseR * 1.5 : baseR, 0, Math.PI * 2);
        ctx.fillStyle = highlight ? '#fff' : '#8888bb';
        ctx.fill();
        if (highlight) {
          ctx.strokeStyle = '#fff';
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      }
    }
    ctx.globalAlpha = 1;

    // Pole labels (always visible)
    ctx.textBaseline = 'middle';
    var poleNames = Object.keys(POLES);
    for (var pi = 0; pi < poleNames.length; pi++) {
      var poleName = poleNames[pi];
      var idx = labelIndex[poleName];
      if (idx === undefined) continue;
      var sx = screenPts[idx][0], sy = screenPts[idx][1];
      if (sx < -50 || sx > W + 50 || sy < -50 || sy > H + 50) continue;
      ctx.font = 'bold ' + Math.max(12, 14 * zoom / 2) + 'px "Segoe UI", system-ui, sans-serif';
      ctx.textAlign = 'left';
      ctx.fillStyle = POLES[poleName].color;
      ctx.fillText(poleName, sx + baseR * 3 + 4, sy);
    }

    // Notable labels at moderate zoom
    if (zoom > 1.5) {
      ctx.font = Math.min(11, 9 * zoom / 2) + 'px "Segoe UI", system-ui, sans-serif';
      ctx.textAlign = 'left';
      for (var i = 0; i < N; i++) {
        var p = points[i];
        if (!p.isNotable || p.isPole) continue;
        if (searchMatches && !searchMatches.has(i)) continue;
        var sx = screenPts[i][0], sy = screenPts[i][1];
        if (sx < -50 || sx > W + 50 || sy < -50 || sy > H + 50) continue;
        ctx.fillStyle = 'rgba(200,200,220,0.7)';
        ctx.fillText(p.label, sx + baseR + 3, sy);
      }
    }

    // All labels at high zoom
    if (zoom > 3) {
      ctx.font = Math.min(10, 8 * zoom / 3) + 'px "Segoe UI", system-ui, sans-serif';
      ctx.textAlign = 'left';
      for (var i = 0; i < N; i++) {
        var p = points[i];
        if (p.isPole || p.isNotable) continue;
        if (searchMatches && !searchMatches.has(i)) continue;
        var sx = screenPts[i][0], sy = screenPts[i][1];
        if (sx < -50 || sx > W + 50 || sy < -50 || sy > H + 50) continue;
        ctx.fillStyle = 'rgba(180,180,200,0.6)';
        ctx.fillText(p.label, sx + baseR + 2, sy);
      }
    }

    // Selected cell
    if (selectedIdx >= 0) {
      var cell = voronoi.cellPolygon(selectedIdx);
      if (cell) {
        ctx.beginPath();
        ctx.moveTo(cell[0][0], cell[0][1]);
        for (var j = 1; j < cell.length; j++) ctx.lineTo(cell[j][0], cell[j][1]);
        ctx.closePath();
        ctx.strokeStyle = '#7c8cf8';
        ctx.lineWidth = 2;
        ctx.stroke();
      }
    }

    // Pole connections
    if (poleNames.length >= 2) {
      ctx.setLineDash([6, 4]);
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = 'rgba(180,130,220,0.35)';
      for (var a = 0; a < poleNames.length; a++) {
        for (var b = a + 1; b < poleNames.length; b++) {
          var ia = labelIndex[poleNames[a]];
          var ib = labelIndex[poleNames[b]];
          if (ia !== undefined && ib !== undefined) {
            ctx.beginPath();
            ctx.moveTo(screenPts[ia][0], screenPts[ia][1]);
            ctx.lineTo(screenPts[ib][0], screenPts[ib][1]);
            ctx.stroke();
          }
        }
      }
      ctx.setLineDash([]);
    }

    // Axis labels
    ctx.font = '11px "Segoe UI", system-ui, sans-serif';
    ctx.fillStyle = 'rgba(140,140,170,0.7)';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'bottom';
    ctx.fillText('\\u2190 ' + xAxisLabel.neg, 90, H - 8);
    ctx.fillText(xAxisLabel.pos + ' \\u2192', W - 90, H - 8);
    ctx.save();
    ctx.translate(14, H / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textBaseline = 'top';
    ctx.textAlign = 'center';
    ctx.fillText('\\u2190 ' + yAxisLabel.neg + '          ' + yAxisLabel.pos + ' \\u2192', 0, 0);
    ctx.restore();

    // Store for hit testing
    window._delaunay = delaunay;
    window._screenPts = screenPts;
    window._regimes = regimes;

    ctx.restore();
  }

  // ============================================================
  // ZOOM & NAVIGATION
  // ============================================================
  var zoomBehavior = d3.zoom()
    .scaleExtent([0.3, 80])
    .on('zoom', function(event) {
      currentTransform = event.transform;
      document.getElementById('zoom-info').textContent = 'Zoom: ' + currentTransform.k.toFixed(1) + 'x';
      draw();
    });

  d3.select(canvas).call(zoomBehavior);

  function panToPoint(idx, k) {
    var p = points[idx];
    var s = getScale();
    var sx = W / 2 + (p.x - dataCx) * s;
    var sy = H / 2 - (p.y - dataCy) * s;
    var tx = W / 2 - sx * k;
    var ty = H / 2 - sy * k;
    var t = d3.zoomIdentity.translate(tx, ty).scale(k);
    d3.select(canvas).transition().duration(600).call(zoomBehavior.transform, t);
  }

  function centerOnPoles() {
    var poleIdxs = Object.keys(POLES).map(function(w) { return labelIndex[w]; }).filter(function(i) { return i !== undefined; });
    if (poleIdxs.length >= 2) {
      var cx = d3.mean(poleIdxs, function(i) { return points[i].x; });
      var cy = d3.mean(poleIdxs, function(i) { return points[i].y; });
      var s = getScale();
      var sx = W / 2 + (cx - dataCx) * s;
      var sy = H / 2 - (cy - dataCy) * s;
      var k = 2.0;
      var tx = W / 2 - sx * k;
      var ty = H / 2 - sy * k;
      var t = d3.zoomIdentity.translate(tx, ty).scale(k);
      d3.select(canvas).transition().duration(800).call(zoomBehavior.transform, t);
    }
  }

  setTimeout(centerOnPoles, 100);

  // ============================================================
  // HOVER / CLICK / SEARCH
  // ============================================================
  canvas.addEventListener('mousemove', function(e) {
    var rect = canvas.getBoundingClientRect();
    var mx = e.clientX - rect.left;
    var my = e.clientY - rect.top;
    var tooltip = document.getElementById('tooltip');

    if (!window._delaunay) return;
    var idx = window._delaunay.find(mx, my);
    var sx = window._screenPts[idx][0], sy = window._screenPts[idx][1];
    var dist = Math.hypot(mx - sx, my - sy);

    if (dist < 40) {
      hoveredIdx = idx;
      var p = points[idx];
      var regime = window._regimes[idx];
      tooltip.querySelector('.tt-label').textContent = p.label;
      tooltip.querySelector('.tt-coords').textContent =
        'x: ' + (p.x >= 0 ? '+' : '') + p.x.toFixed(3) + '  y: ' + (p.y >= 0 ? '+' : '') + p.y.toFixed(3);
      var regimeLabels = { over: 'Oversymbolic (dense)', neuro: 'Neurosymbolic (balanced)', under: 'Undersymbolic (sparse)' };
      var regimeClasses = { over: 'regime-over', neuro: 'regime-neuro', under: 'regime-under' };
      tooltip.querySelector('.tt-regime').innerHTML =
        '<span class="regime-badge ' + regimeClasses[regime] + '">' + regimeLabels[regime] + '</span>';
      tooltip.style.display = 'block';
      tooltip.style.left = (mx + 15) + 'px';
      tooltip.style.top = (my - 10) + 'px';
      var tr = tooltip.getBoundingClientRect();
      var wr = canvasWrap.getBoundingClientRect();
      if (tr.right > wr.right) tooltip.style.left = (mx - tr.width - 10) + 'px';
      if (tr.bottom > wr.bottom) tooltip.style.top = (my - tr.height - 10) + 'px';
    } else {
      hoveredIdx = -1;
      tooltip.style.display = 'none';
    }
    draw();
  });

  canvas.addEventListener('mouseleave', function() {
    hoveredIdx = -1;
    document.getElementById('tooltip').style.display = 'none';
    draw();
  });

  canvas.addEventListener('click', function(e) {
    var rect = canvas.getBoundingClientRect();
    var mx = e.clientX - rect.left;
    var my = e.clientY - rect.top;
    if (!window._delaunay) return;
    var idx = window._delaunay.find(mx, my);
    var sx = window._screenPts[idx][0], sy = window._screenPts[idx][1];
    var dist = Math.hypot(mx - sx, my - sy);

    if (dist < 40) {
      selectedIdx = idx;
      showDetail(idx);
    } else {
      selectedIdx = -1;
      document.getElementById('detail-panel').style.display = 'none';
    }
    draw();
  });

  function showDetail(idx) {
    var p = points[idx];
    document.getElementById('detail-panel').style.display = 'block';
    document.getElementById('detail-label').textContent = p.label;
    document.getElementById('detail-coords').textContent =
      'x: ' + (p.x >= 0 ? '+' : '') + p.x.toFixed(3) + '  y: ' + (p.y >= 0 ? '+' : '') + p.y.toFixed(3);

    var dists = points.map(function(q, i) {
      return { i: i, dist: Math.hypot(q.x - p.x, q.y - p.y) };
    });
    dists.sort(function(a, b) { return a.dist - b.dist; });
    var list = document.getElementById('neighbors-list');
    list.innerHTML = '';
    for (var k = 1; k <= 10 && k < dists.length; k++) {
      var nb = dists[k];
      var q = points[nb.i];
      var li = document.createElement('li');
      var isPole = POLE_SET.has(q.label);
      li.innerHTML = '<span style="color:' + (isPole ? POLES[q.label].color : '#aaa') + '">' + q.label + '</span><span class="dist">' + nb.dist.toFixed(3) + '</span>';
      list.appendChild(li);
    }
  }

  // Search
  var searchInput = document.getElementById('search');
  searchInput.addEventListener('input', function() {
    var q = searchInput.value.trim().toLowerCase();
    if (q.length === 0) {
      searchMatches = null;
      draw();
      return;
    }
    searchMatches = new Set();
    points.forEach(function(p, i) {
      if (p.label.toLowerCase().indexOf(q) !== -1) searchMatches.add(i);
    });
    if (searchMatches.size > 0 && searchMatches.size <= 50) {
      var firstIdx = searchMatches.values().next().value;
      panToPoint(firstIdx, Math.max(currentTransform.k, 3));
    }
    draw();
  });

  // ============================================================
  // CUSTOM AXIS INPUT
  // ============================================================
  var axisInputIds = ['x-neg', 'x-pos', 'y-neg', 'y-neg2', 'y-pos', 'y-pos2'];
  var axisInputs = axisInputIds.map(function(id) { return document.getElementById(id); });

  axisInputs.forEach(function(input) {
    input.addEventListener('input', function() {
      var word = input.value.trim().toLowerCase();
      input.classList.remove('valid', 'invalid');
      if (word.length === 0) return;
      if (pcaLabelIndex[word] !== undefined) input.classList.add('valid');
      else input.classList.add('invalid');
    });
  });

  document.getElementById('apply-axes').addEventListener('click', function() {
    var xNeg = document.getElementById('x-neg').value.trim().toLowerCase();
    var xPos = document.getElementById('x-pos').value.trim().toLowerCase();
    var yNeg = document.getElementById('y-neg').value.trim().toLowerCase();
    var yNeg2 = document.getElementById('y-neg2').value.trim().toLowerCase();
    var yPos = document.getElementById('y-pos').value.trim().toLowerCase();
    var yPos2 = document.getElementById('y-pos2').value.trim().toLowerCase();

    var status = document.getElementById('axis-status');
    var yNegWords = [yNeg, yNeg2].filter(function(w) { return w.length > 0; });
    var yPosWords = [yPos, yPos2].filter(function(w) { return w.length > 0; });
    var allWords = [xNeg, xPos].concat(yNegWords).concat(yPosWords);
    var missing = allWords.filter(function(w) { return pcaLabelIndex[w] === undefined; });

    if (missing.length > 0) {
      status.style.color = '#e74c3c';
      status.textContent = 'Not in vocabulary: ' + missing.join(', ');
      return;
    }
    if (xNeg === xPos) {
      status.style.color = '#e74c3c';
      status.textContent = 'X-axis poles must be different words';
      return;
    }

    status.style.color = '#7c8cf8';
    status.textContent = 'Projecting...';

    requestAnimationFrame(function() {
      var result = projectOntoAxes(xNeg, xPos, yNegWords, yPosWords);
      if (!result) {
        status.style.color = '#e74c3c';
        status.textContent = 'Degenerate axes. Try different words.';
        return;
      }

      var uniquePoles = [];
      var seen = {};
      [xNeg, xPos].concat(yNegWords).concat(yPosWords).forEach(function(w) {
        if (!seen[w]) { uniquePoles.push(w); seen[w] = true; }
      });
      updatePoles(uniquePoles);
      xAxisLabel = { neg: xNeg, pos: xPos };
      yAxisLabel = { neg: yNegWords.join('+'), pos: yPosWords.join('+') };

      loadProjection(result);
      selectedIdx = -1;
      document.getElementById('detail-panel').style.display = 'none';

      status.style.color = '#2ecc71';
      status.textContent = 'Reprojected onto ' + xNeg + '/' + xPos + ' axes';

      currentTransform = d3.zoomIdentity;
      resize();
      draw();
      setTimeout(centerOnPoles, 50);
    });
  });

  document.getElementById('reset-axes').addEventListener('click', function() {
    document.getElementById('x-neg').value = 'man';
    document.getElementById('x-pos').value = 'woman';
    document.getElementById('y-neg').value = 'man';
    document.getElementById('y-neg2').value = 'woman';
    document.getElementById('y-pos').value = 'boy';
    document.getElementById('y-pos2').value = 'girl';
    axisInputs.forEach(function(input) { input.classList.remove('valid', 'invalid'); });

    updatePoles(['man', 'woman', 'boy', 'girl']);
    xAxisLabel = { neg: 'man', pos: 'woman' };
    yAxisLabel = { neg: 'adult', pos: 'young' };

    loadProjection(DEFAULT_PROJ);
    selectedIdx = -1;
    document.getElementById('detail-panel').style.display = 'none';
    document.getElementById('axis-status').textContent = '';

    currentTransform = d3.zoomIdentity;
    resize();
    draw();
    setTimeout(centerOnPoles, 50);
  });

  axisInputs.forEach(function(input) {
    input.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') document.getElementById('apply-axes').click();
    });
  });

  // ============================================================
  // MOBILE SIDEBAR
  // ============================================================
  var sidebar = document.getElementById('sidebar');
  var sidebarOverlay = document.getElementById('sidebar-overlay');
  document.getElementById('sidebar-toggle').addEventListener('click', function() {
    sidebar.classList.toggle('open');
    sidebarOverlay.classList.toggle('open');
  });
  sidebarOverlay.addEventListener('click', function() {
    sidebar.classList.remove('open');
    sidebarOverlay.classList.remove('open');
  });

  // Initial draw
  draw();
  </script>
</body>
</html>'''

with open('pages/index.html', 'w', encoding='utf-8') as f:
    f.write(html)

import os
size = os.path.getsize('pages/index.html')
print(f"Written {size} bytes ({size/1024:.0f} KB) to pages/index.html")
