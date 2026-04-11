/**
 * Sutra — graph-to-linear-algebra interactive demo.
 *
 * Self-contained vanilla JS widget that visualizes the same tiny
 * "fly-brain-shaped" network three different ways: as a graph, as an
 * adjacency matrix, and as a state vector in 6-dimensional space.
 * A "tick" button runs one matrix-vector multiply step so the user
 * can watch the network propagate using only linear algebra.
 *
 * Typed with JSDoc so the script can be edited as if it were
 * TypeScript without requiring a build step. The mkdocs Material
 * theme loads it as a plain `<script defer>` from the page that
 * contains `<div id="graph-to-vector-widget">`.
 *
 * No frameworks, no bundler, no external dependencies. Pure DOM + SVG.
 *
 * @file
 */

// ============================================================
// Network model
// ============================================================

/**
 * Six-neuron toy network. The first four nodes are "sensory" inputs;
 * the last two are "motor" outputs. The connectivity is hand-picked
 * so that propagation is visually interesting (not all motor neurons
 * fire on every tick).
 *
 * adjacency[i][j] === 1 means neuron i sends signal TO neuron j.
 * (Row = source, column = destination — standard adjacency convention.)
 *
 * @type {number[][]}
 */
const ADJACENCY = [
    // dst:    s0  s1  s2  s3  m0  m1
    /* s0 */ [  0,  0,  0,  0,  1,  0 ],
    /* s1 */ [  0,  0,  0,  0,  1,  1 ],
    /* s2 */ [  0,  0,  0,  0,  0,  1 ],
    /* s3 */ [  0,  0,  0,  0,  1,  1 ],
    /* m0 */ [  0,  0,  0,  0,  0,  0 ],
    /* m1 */ [  0,  0,  0,  0,  0,  0 ],
];

const NEURON_COUNT = 6;

/** @type {{ id: string, role: "sensory" | "motor", x: number, y: number }[]} */
const NEURON_LAYOUT = [
    { id: "s0", role: "sensory", x: 80,  y: 50  },
    { id: "s1", role: "sensory", x: 80,  y: 110 },
    { id: "s2", role: "sensory", x: 80,  y: 170 },
    { id: "s3", role: "sensory", x: 80,  y: 230 },
    { id: "m0", role: "motor",   x: 320, y: 100 },
    { id: "m1", role: "motor",   x: 320, y: 180 },
];

/** Initial firing pattern: just s1 is firing. */
const INITIAL_STATE = [0, 1, 0, 0, 0, 0];

// ============================================================
// State
// ============================================================

/**
 * Mutable widget state. There is exactly one widget per page; reusing
 * the same module-level state object would matter only if we ever embed
 * two of these on the same page (we don't).
 *
 * @typedef {{
 *   view: "graph" | "matrix" | "vector",
 *   currentState: number[],
 *   tickCount: number,
 *   container: HTMLElement,
 * }} WidgetState
 */

// ============================================================
// Linear algebra (the whole point of the demo)
// ============================================================

/**
 * Compute next_state[j] = OR over i of (state[i] AND adjacency[i][j]).
 *
 * This is matrix-vector multiplication in the boolean semiring — an
 * "any source pointed at this destination is firing" rule. Real
 * neurons sum and threshold; we use the boolean version because it's
 * the simplest possible thing that's still recognizably "the same
 * math." The conceptual point survives the simplification: the entire
 * dynamics of the network are one matrix-vector multiply.
 *
 * @param {number[]} state Length-6 vector of 0/1 firing flags.
 * @param {number[][]} matrix 6x6 adjacency matrix.
 * @returns {number[]} Length-6 next state.
 */
function tick(state, matrix) {
    const n = state.length;
    /** @type {number[]} */
    const next = new Array(n).fill(0);
    for (let j = 0; j < n; j++) {
        let acc = 0;
        for (let i = 0; i < n; i++) {
            acc |= (state[i] & matrix[i][j]);
        }
        next[j] = acc;
    }
    return next;
}

// ============================================================
// SVG / DOM rendering
// ============================================================

const SVG_NS = "http://www.w3.org/2000/svg";

/** @param {string} tag @returns {SVGElement} */
function svgEl(tag) {
    return document.createElementNS(SVG_NS, tag);
}

/**
 * Render the graph view: 6 circles connected by lines, filled if firing.
 *
 * @param {WidgetState} ws
 * @returns {SVGSVGElement}
 */
function renderGraph(ws) {
    /** @type {SVGSVGElement} */
    const svg = /** @type {SVGSVGElement} */ (svgEl("svg"));
    svg.setAttribute("viewBox", "0 0 400 280");
    svg.setAttribute("class", "g2v-svg");
    svg.style.width = "100%";
    svg.style.maxWidth = "520px";
    svg.style.height = "auto";

    // Edges first so they sit behind the nodes.
    for (let i = 0; i < NEURON_COUNT; i++) {
        for (let j = 0; j < NEURON_COUNT; j++) {
            if (ADJACENCY[i][j] !== 1) continue;
            const a = NEURON_LAYOUT[i];
            const b = NEURON_LAYOUT[j];
            const line = svgEl("line");
            line.setAttribute("x1", String(a.x));
            line.setAttribute("y1", String(a.y));
            line.setAttribute("x2", String(b.x));
            line.setAttribute("y2", String(b.y));
            // An edge "fires" visually if its source is currently firing.
            const active = ws.currentState[i] === 1;
            line.setAttribute("stroke", active ? "#7c4dff" : "#999");
            line.setAttribute("stroke-width", active ? "3" : "1.5");
            line.setAttribute("stroke-opacity", active ? "0.95" : "0.5");
            svg.appendChild(line);
        }
    }

    // Nodes.
    for (let i = 0; i < NEURON_COUNT; i++) {
        const n = NEURON_LAYOUT[i];
        const firing = ws.currentState[i] === 1;
        const circle = svgEl("circle");
        circle.setAttribute("cx", String(n.x));
        circle.setAttribute("cy", String(n.y));
        circle.setAttribute("r", "22");
        circle.setAttribute("fill", firing ? "#7c4dff" : "#fff");
        circle.setAttribute("stroke", "#444");
        circle.setAttribute("stroke-width", "2");
        svg.appendChild(circle);

        const label = svgEl("text");
        label.setAttribute("x", String(n.x));
        label.setAttribute("y", String(n.y + 5));
        label.setAttribute("text-anchor", "middle");
        label.setAttribute("font-family", "JetBrains Mono, monospace");
        label.setAttribute("font-size", "14");
        label.setAttribute("fill", firing ? "#fff" : "#444");
        label.textContent = n.id;
        svg.appendChild(label);
    }

    // Column labels.
    const sensory = svgEl("text");
    sensory.setAttribute("x", "80");
    sensory.setAttribute("y", "20");
    sensory.setAttribute("text-anchor", "middle");
    sensory.setAttribute("font-family", "Inter, sans-serif");
    sensory.setAttribute("font-size", "13");
    sensory.setAttribute("fill", "#666");
    sensory.textContent = "sensory";
    svg.appendChild(sensory);

    const motor = svgEl("text");
    motor.setAttribute("x", "320");
    motor.setAttribute("y", "20");
    motor.setAttribute("text-anchor", "middle");
    motor.setAttribute("font-family", "Inter, sans-serif");
    motor.setAttribute("font-size", "13");
    motor.setAttribute("fill", "#666");
    motor.textContent = "motor";
    svg.appendChild(motor);

    return svg;
}

/**
 * Render the matrix view: 6x6 grid of 0/1 cells.
 *
 * @param {WidgetState} _ws unused (matrix is constant)
 * @returns {HTMLDivElement}
 */
function renderMatrix(_ws) {
    const wrap = document.createElement("div");
    wrap.className = "g2v-matrix";
    wrap.style.fontFamily = "JetBrains Mono, monospace";
    wrap.style.fontSize = "14px";
    wrap.style.display = "inline-block";
    wrap.style.padding = "12px";
    wrap.style.borderRadius = "4px";
    wrap.style.background = "rgba(124, 77, 255, 0.08)";

    const header = document.createElement("div");
    header.style.color = "#666";
    header.style.marginBottom = "8px";
    header.textContent = "adjacency[i][j]:";
    wrap.appendChild(header);

    const grid = document.createElement("div");
    grid.style.display = "grid";
    grid.style.gridTemplateColumns = `repeat(${NEURON_COUNT + 1}, 32px)`;
    grid.style.gap = "2px";

    // Top-left empty corner.
    grid.appendChild(document.createElement("div"));
    // Column headers.
    for (let j = 0; j < NEURON_COUNT; j++) {
        const h = document.createElement("div");
        h.textContent = NEURON_LAYOUT[j].id;
        h.style.color = "#999";
        h.style.textAlign = "center";
        grid.appendChild(h);
    }
    // Rows.
    for (let i = 0; i < NEURON_COUNT; i++) {
        const r = document.createElement("div");
        r.textContent = NEURON_LAYOUT[i].id;
        r.style.color = "#999";
        r.style.textAlign = "right";
        r.style.paddingRight = "4px";
        grid.appendChild(r);
        for (let j = 0; j < NEURON_COUNT; j++) {
            const cell = document.createElement("div");
            cell.textContent = String(ADJACENCY[i][j]);
            cell.style.textAlign = "center";
            cell.style.padding = "4px 0";
            cell.style.background = ADJACENCY[i][j] === 1
                ? "rgba(124, 77, 255, 0.5)"
                : "rgba(0, 0, 0, 0.04)";
            cell.style.color = ADJACENCY[i][j] === 1 ? "#fff" : "#888";
            cell.style.borderRadius = "2px";
            grid.appendChild(cell);
        }
    }
    wrap.appendChild(grid);
    return wrap;
}

/**
 * Render the state vector as a horizontal row of 6 cells, plus the
 * matrix * vector formula expanded so the user can see what tick()
 * is computing.
 *
 * @param {WidgetState} ws
 * @returns {HTMLDivElement}
 */
function renderVector(ws) {
    const wrap = document.createElement("div");
    wrap.style.fontFamily = "JetBrains Mono, monospace";
    wrap.style.fontSize = "14px";

    const label = document.createElement("div");
    label.style.color = "#666";
    label.style.marginBottom = "8px";
    label.textContent = `state vector (tick ${ws.tickCount}):`;
    wrap.appendChild(label);

    const row = document.createElement("div");
    row.style.display = "grid";
    row.style.gridTemplateColumns = `repeat(${NEURON_COUNT}, 56px)`;
    row.style.gap = "4px";
    for (let i = 0; i < NEURON_COUNT; i++) {
        const cell = document.createElement("div");
        cell.textContent = String(ws.currentState[i]);
        cell.style.textAlign = "center";
        cell.style.padding = "16px 0";
        cell.style.borderRadius = "4px";
        cell.style.background = ws.currentState[i] === 1
            ? "#7c4dff"
            : "rgba(0, 0, 0, 0.04)";
        cell.style.color = ws.currentState[i] === 1 ? "#fff" : "#888";
        cell.style.fontWeight = "600";
        row.appendChild(cell);
    }
    wrap.appendChild(row);

    const ids = document.createElement("div");
    ids.style.display = "grid";
    ids.style.gridTemplateColumns = `repeat(${NEURON_COUNT}, 56px)`;
    ids.style.gap = "4px";
    ids.style.marginTop = "4px";
    for (let i = 0; i < NEURON_COUNT; i++) {
        const id = document.createElement("div");
        id.textContent = NEURON_LAYOUT[i].id;
        id.style.textAlign = "center";
        id.style.color = "#999";
        id.style.fontSize = "11px";
        ids.appendChild(id);
    }
    wrap.appendChild(ids);

    const formula = document.createElement("div");
    formula.style.marginTop = "16px";
    formula.style.color = "#666";
    formula.style.lineHeight = "1.5";
    formula.innerHTML =
        "next_state = adjacency · state<br/>" +
        "&nbsp;&nbsp;<span style='color:#7c4dff'>(this is a single matrix-vector multiply)</span>";
    wrap.appendChild(formula);

    return wrap;
}

// ============================================================
// Widget mounting + event wiring
// ============================================================

/**
 * Re-render the active view inside the widget. Called on mount and on
 * every state change (tick / reset / view switch).
 *
 * @param {WidgetState} ws
 */
function rerender(ws) {
    /** @type {HTMLElement | null} */
    const stage = ws.container.querySelector(".g2v-stage");
    if (!stage) return;
    stage.innerHTML = "";
    let view;
    if (ws.view === "graph") view = renderGraph(ws);
    else if (ws.view === "matrix") view = renderMatrix(ws);
    else view = renderVector(ws);
    stage.appendChild(view);

    // Update the explanation paragraph.
    /** @type {HTMLElement | null} */
    const help = ws.container.querySelector(".g2v-help");
    if (help) {
        if (ws.view === "graph") {
            help.innerHTML =
                "<strong>Graph view.</strong> Six neurons, four sensory and two motor. Filled circles are firing this tick. Lines are connections — bold purple lines are edges where the source neuron is firing right now. This is the picture you have in your head when you say <em>connectome</em>.";
        } else if (ws.view === "matrix") {
            help.innerHTML =
                "<strong>Matrix view.</strong> The same connectivity rewritten as a 6×6 grid of 0s and 1s. Cell (i, j) is 1 if neuron i sends a signal to neuron j. <strong>The graph is gone.</strong> There are no edges. There are no nodes. There is just a numerical pattern. This is the same information as the graph view, expressed differently.";
        } else {
            help.innerHTML =
                `<strong>Vector view.</strong> Which neurons are firing right now is a list of 6 numbers — a 6-dimensional vector. The fly brain's state lives at a <em>point in 6D space</em>. Click <strong>Tick</strong> and watch what happens: <code>next_state = adjacency × state</code>. One matrix-vector multiply propagates the network forward by one step. <strong>This is linear algebra. The graph is gone. The brain is now a coordinate.</strong>`;
        }
    }
}

/** @param {WidgetState} ws */
function setView(ws, view) {
    ws.view = view;
    // Update button highlighted state.
    ws.container.querySelectorAll(".g2v-tab").forEach((b) => {
        const el = /** @type {HTMLButtonElement} */ (b);
        const active = el.dataset.view === view;
        el.style.background = active ? "#7c4dff" : "transparent";
        el.style.color = active ? "#fff" : "inherit";
        el.style.borderColor = active ? "#7c4dff" : "rgba(124, 77, 255, 0.4)";
    });
    rerender(ws);
}

/**
 * Build a labeled button.
 *
 * @param {string} label
 * @param {() => void} onClick
 * @returns {HTMLButtonElement}
 */
function makeButton(label, onClick) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    b.style.padding = "8px 14px";
    b.style.border = "1px solid rgba(124, 77, 255, 0.4)";
    b.style.borderRadius = "4px";
    b.style.background = "transparent";
    b.style.cursor = "pointer";
    b.style.fontFamily = "Inter, sans-serif";
    b.style.fontSize = "14px";
    b.addEventListener("click", onClick);
    return b;
}

/**
 * Mount the widget into the placeholder div on the page.
 */
function mount() {
    /** @type {HTMLElement | null} */
    const container = document.getElementById("graph-to-vector-widget");
    if (!container) return;
    container.innerHTML = "";
    container.style.border = "1px solid rgba(124, 77, 255, 0.3)";
    container.style.borderRadius = "8px";
    container.style.padding = "20px";
    container.style.marginTop = "16px";
    container.style.marginBottom = "16px";
    container.style.background = "rgba(124, 77, 255, 0.03)";

    /** @type {WidgetState} */
    const ws = {
        view: "graph",
        currentState: INITIAL_STATE.slice(),
        tickCount: 0,
        container,
    };

    // Tab row.
    const tabs = document.createElement("div");
    tabs.style.display = "flex";
    tabs.style.gap = "8px";
    tabs.style.marginBottom = "12px";
    tabs.style.flexWrap = "wrap";

    const views = /** @type {const} */ ([
        { id: "graph",  label: "1. Graph view" },
        { id: "matrix", label: "2. Matrix view" },
        { id: "vector", label: "3. Vector view" },
    ]);
    for (const v of views) {
        const b = makeButton(v.label, () => setView(ws, v.id));
        b.classList.add("g2v-tab");
        b.dataset.view = v.id;
        tabs.appendChild(b);
    }
    container.appendChild(tabs);

    // Stage where the active view renders.
    const stage = document.createElement("div");
    stage.className = "g2v-stage";
    stage.style.minHeight = "200px";
    stage.style.padding = "8px 0";
    container.appendChild(stage);

    // Action row.
    const actions = document.createElement("div");
    actions.style.display = "flex";
    actions.style.gap = "8px";
    actions.style.marginTop = "12px";
    actions.style.flexWrap = "wrap";
    actions.appendChild(makeButton("Tick (matrix × vector)", () => {
        ws.currentState = tick(ws.currentState, ADJACENCY);
        ws.tickCount += 1;
        rerender(ws);
    }));
    actions.appendChild(makeButton("Reset", () => {
        ws.currentState = INITIAL_STATE.slice();
        ws.tickCount = 0;
        rerender(ws);
    }));
    container.appendChild(actions);

    // Explanation paragraph.
    const help = document.createElement("p");
    help.className = "g2v-help";
    help.style.marginTop = "16px";
    help.style.color = "#444";
    help.style.lineHeight = "1.55";
    container.appendChild(help);

    // Initial render.
    setView(ws, "graph");
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
} else {
    mount();
}
