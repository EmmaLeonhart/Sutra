# `apps/terminal` — the symbol-stable terminal surface

**Stage 2 of the headline demo** (`planning/22-meta-demo-replication.md`):
a terminal whose output is *computed*, not *generated*. Meta's NCCLIGen (a
DiT video model trained on ~1,100 h of terminal recordings) *hallucinates*
plausible terminal frames that drift symbol-by-symbol; their own paper
lists symbolic stability as unsolved. This terminal admits a real utility
through the kernel and prints **the exact bytes the substrate produced** —
exact by construction, zero drift however long the session runs. Same
surface, opposite engineering, and the wedge goes in exactly where their
paper concedes weakness.

## Run it

```
python apps/terminal/terminal.py     # interactive REPL (Ctrl-D to quit)
python apps/terminal/demo.py         # fixed transcript, exact every line
```

Example session:

```
echo hello world          ->  hello world
calc 2 + 3 * 4 =          ->  14
calc 4729 * 8831 =        ->  41761799
help                      ->  yterm commands: calc, echo, help
```

## Commands

| Command | What it does |
|---|---|
| `echo <text>` | Carries `text` through `echo.su` on the substrate and prints the **substrate's decoded string** (rotation-bind → kernel route under capability check → `echo.su` re-bind → unbind + decode). Not a host re-echo of the input. |
| `calc <expr>` | Evaluates `<expr>` on the calc substrate (`switch.su`; operator selected on the substrate; float64). Exact or refused. |
| `help` | Lists the available commands. |

Unknown commands return a shell-style `yterm: command not found: <name>`.

## What runs where (the architecture, planning/01)

- **The terminal is host orchestration.** Reading a line, splitting the
  command name from its arguments, and deciding which admitted utility to
  route to is the **Connectome Manager's job** — "deciding what is
  connected to what" — which is the CPU-side orchestrator's work, not
  substrate computation.

  This is a deliberate distinction from the calculator. In `calc`, *which
  arithmetic operation* runs is data-driven computation on the operands,
  so it happens **on the substrate** via `switch.su`. In the terminal,
  *which program a typed command names* is admission/routing — **host-side
  by design**. The two dispatches look alike but sit on opposite sides of
  the host/substrate line.

- **The computation runs on the substrate, and the output shown is the
  substrate's** — decoded verbatim, never a host re-computation.

## Substrate-purity note (no overclaim)

This terminal does **not** close the calculator's known step-c gap
(`planning/23`): `calc` still returns a host `Fraction` behind a
host-oracle refuse-gate. The terminal composes calc as-is; it neither
adds nor removes that gap. The `echo` path is content-pure — the displayed
string is the substrate's decode.

## The measurable claim

`Terminal.run_script(lines)` runs an N-step interaction trace and returns
one output per line. `tests/test_terminal.py::test_scripted_trace_zero_drift`
asserts a fixed transcript matches at **every** step — the headline-demo
measurement (planning/22 § "Making it measurable") at small N: 100% exact,
flat as N grows, where a generative baseline decays with horizon.

## Status / what's next

- **Built (2026-05-24):** the command reader + `echo`/`calc`/`help`,
  19 passing tests, a demo transcript.
- **Next:** more utilities (`cat`, `ls`, `wc`) as they land natively in
  Sutra (gated on Sutra string/IO/FS vocabulary — `todo.md` § 2); a
  keyboard/interactive front-end belongs to the browser/GUI layer
  (build-sequence milestone 3). The Python command reader is the host
  stand-in for the eventual Rust-orchestrator / browser terminal.
