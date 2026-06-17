# GUI stack: everything is a browser

## Sequencing — GUI is third

This document describes the *eventual* GUI. The build sequence is:

1. **Connectome manager** (kernel) — the v0.0 nucleus is in
   `kernel/`; the production version is the Rust orchestrator on
   the CPU side that loads programs onto the GPU and offloads them
   to RAM/disk.
2. **Simple Linux-shaped utilities** — file access, edit, list,
   etc. Initial system is **command-line only**, accessed by SSH
   or serial from a host computer. No graphics whatsoever in this
   phase.
3. **Browser** — only after (1) and (2) are working does the GUI
   stack described in this document get built.

Future agents reading this doc should not interpret it as work
that is or should be in flight. The GUI is the third milestone.

## The shape of the bet

The entire Yantra userspace UI is rendered through what is, in
appearance, a browser. From the outside it looks a lot like ChromeOS —
windows are web views, the file manager is HTML, the settings panel is
HTML, the terminal is HTML, the desktop and taskbar are HTML.

Underneath, the appearance is the only thing it shares with ChromeOS.
There is no Chromium. There is no V8. There is no JIT. There is a
Sutra-native browser that:

- Parses HTML5 and CSS the conventional way.
- AOT-compiles the page's JS/TS bundle into Sutra → tensor program at
  load time.
- Renders via WebGL (which on Yantra hardware maps to the same
  matrix-multiply substrate the rest of the OS uses anyway).
- Talks to the kernel through the same axon-based syscalls every other
  process uses.

The pitch internally was: it's the philosophy of "do one thing and do it
well" applied to an OS. The one thing is **render JavaScript-defined
interfaces and run their logic as compiled tensor programs**. Everything
follows from that.

## What the browser supports

Committed:

- HTML5 ✓
- CSS ✓
- AOT-compiled JS/TS → Sutra ✓
- WebGL / Three.js → tensor substrate (Yantra's GPU/analog hardware
  does WebGL's job natively rather than via a discrete GPU pipeline) ✓
- Semantic web stack (RDF, SPARQL, JSON-LD) — first-class, unusual but
  fits Sutra's symbolic flavor ✓
- WebSockets for data ✓

Explicitly **deferred — eventually, but not soon** (decision 2026-05-14):

- **WebAssembly.** WASM is *eventually* in scope but **not now and
  not for a long time** — not v0, not v0.1, not on any near-term
  roadmap. WASM's linear-memory and threading model is alien to
  Sutra's substrate: there is no flat byte heap to map onto the
  connectome, and its edge cases make it a poor fit for the v0 GUI
  stack the way Sutra+rotation-binding works today. v0's GUI stack
  is JS/TS only — HTML5 + CSS + idiomatic TypeScript +
  WebGL/Three.js. Web apps that ship only as WASM bundles either
  re-ship as JS/TS for v0 or wait for the eventual WASM lowering
  path. See `planning/07-transpilers.md` § "WASM → Sutra — deferred
  (eventually, but not soon)" for the decision record.

Explicitly **not** supported:

- `eval()` — primary attack surface for XSS, easy to live without.
- Service workers pushing executable code at runtime.
- `<script>`-from-server JIT execution. JS is AOT-compiled at page load.
  If a server sends new JS in response to a request, the browser refuses
  to execute it.
- Continuous server-emitted JS / SSR with hydration that swaps in new
  code.

These are documented limitations, not bugs. In a defense / aerospace
context most of them are *features*: every API not implemented is an
attack surface that does not exist, and every dynamic-execution feature
not supported makes the platform that much more auditable.

## Why JS/TS

Three reasons it earns the userspace slot:

1. **Almost every UI thing already exists in JS/TS.** Settings panels,
   file browsers, terminals, IDE-like surfaces, monitoring dashboards —
   the UI surface for a defense/industrial system is squarely in the
   stuff JS/TS handles well.
2. **JS is closer to functional than its reputation.** It has Lisp DNA
   (closures, higher-order functions). Modern TS adds enough type
   information to help the transpiler. Reactive frameworks (React,
   Solid, Svelte signals) push idiomatic JS toward the dataflow shape
   Sutra wants.
3. **Existing transpilers work.** A JS → Sutra transpiler already exists
   and produces tensor programs from idiomatic JS. The pseudo-functional
   nature of JS makes the lowering tractable in a way C++ would not be.

TS and JS get the same treatment: TS does not need to be erased before
transpilation. Type info actually helps, so we keep it.

## Pipeline

```
HTML5 + CSS    → DOM/style tree (conventional parse)
JS / TS bundle → AST → Sutra source → tensor program
WebGL calls    → fused tensor ops on the same substrate
Page state     → axon stream, kernel-routed
```

All AOT. The page takes a bit longer to load than on a JIT browser
because the whole bundle compiles before the first paint. After that,
the page is a Sutra program and runs at the same fixed-allocation pace
as everything else on the system.

## Window manager / desktop

The desktop, taskbar, window manager, login screen are all HTML/JS too.
A "window" is a browser web-view that the window manager places on the
screen. The window manager is itself a browser surface.

This is recursive in the same way the rest of the OS is recursive: the
thing that draws the windows is the same kind of thing the windows
contain. There is no native widget toolkit beneath.

## Apps

An "app" is, at minimum:

- A directory with a `manifest.yantra` file declaring its GPU footprint
  and required role capabilities.
- An HTML entry point.
- A JS/TS bundle.
- Optional WebGL assets, fonts, etc.

The browser loads it the way a browser loads a website, except it's
served from local storage and AOT-compiled once at install time. After
install, launching the app is just admitting its compiled tensor program
to the GPU.

## Loop / "flow object" caveat

A real-world note from running JS through the transpiler: tail-recursive
loops compile fine, but the auto-generated "flow objects" (the structs
that capture the variables a loop needs to carry across iterations) tend
to balloon, capturing more than they need. Trimming those is part of the
optimisation pipeline, not something to leave to the language. We will
need a pass that walks the captured set and removes anything not read on
the next iteration.

## Open questions

- **WebGL precision.** WebGL programs assume IEEE-754 floats. Analog
  substrates have different numerical properties. We'll need a
  conformance-testing strategy that flags the cases where WebGL output
  diverges from spec on Yantra hardware.
- **Animations.** GPU-driven animations are easy. But "the app subtly
  moves a label by 1px every frame for 200ms" needs to fit into the
  fixed-allocation model. Is that just part of the page's program, or
  does the window manager need its own animation budget?
- **Browser name.** Calling it "the browser" works internally. A real
  product name comes later, probably aligned with the Sanskrit naming
  convention (Sutra, Yantra, …).
