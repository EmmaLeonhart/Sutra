# Planning

This directory holds the design notes for Yantra. The files are
deliberately written so each one stands on its own and can be read
without the others, but the numbering is the reading order if you
want the whole picture.

The notes are **planning, not specification.** They reflect the
current best thinking, not committed APIs. Things will change as
the implementation pressure-tests the assumptions.

## Reading order

1. [00-vision.md](00-vision.md) — what Yantra is, what it isn't,
   the thesis, who would buy it.
2. [01-architecture.md](01-architecture.md) — the layer cake, the
   three guiding inversions, what's in scope and what isn't.
3. [02-axon-model.md](02-axon-model.md) — the data model and
   inter-process protocol; why rotation binding; capabilities as
   roles.
4. [03-process-lifecycle.md](03-process-lifecycle.md) — Active /
   Cold states, fixed allocations, admission instead of throttling.
5. [04-kernel-and-init.md](04-kernel-and-init.md) — boot order,
   what the kernel does and doesn't do, the systemd-shaped piece.
6. [05-filesystem-bridge.md](05-filesystem-bridge.md) — keeping the
   FS conventional and legible; verbatim vs semantic reads.
7. [06-gui-stack.md](06-gui-stack.md) — everything-is-a-browser;
   HTML5 + WebGL + AOT-compiled JS/TS; what we don't support.
8. [07-transpilers.md](07-transpilers.md) — JS/TS, C, WASM
   transpilation strategy and the constraints they impose.
9. [08-security-and-isolation.md](08-security-and-isolation.md) —
   capability model, synthetic-dimension partitioning, attack
   surface story for airgapped customers.
10. [09-verification.md](09-verification.md) — what's verifiable,
    what isn't, DO-178C-shaped argument, AI-side quarantine.
11. [10-ai-native-interface.md](10-ai-native-interface.md) —
    perception/cognition/action in one tensor space, alignment
    pacemaker, "the thing beyond an agent."
12. [11-debugging-and-observability.md](11-debugging-and-observability.md)
    — axon trace viewer, sparse-autoencoder introspection, AI-
    assisted debugging, deception detection.
13. [12-target-markets.md](12-target-markets.md) — defense,
    aerospace, industrial; why critical-systems markets care; the
    ChromeOS comparison.
14. [13-hardware-roadmap.md](13-hardware-roadmap.md) — three
    hardware eras, why analog substrate matters even if it doesn't
    land soon.
15. [14-roadmap-and-milestones.md](14-roadmap-and-milestones.md) —
    foundations → Sutra Real-Time Shell → real boot → reference
    appliance → AI-native applications.
16. [15-open-questions.md](15-open-questions.md) — the running list
    of design decisions still unmade.
17. [16-related-work.md](16-related-work.md) — Meta Neural
    Computers, NTM/DNC, Percepta, ChromeOS, VSA, niche-OS history.

## Conventions

- Each file ends with an "Open questions" section that flows into
  [15-open-questions.md](15-open-questions.md). Edit both when a
  decision moves.
- File numbering is for ordering, not status. Adding `17-...` is
  fine; renumbering is not.
- These are not committed specs — speak in terms of "current
  thinking" and "lean: ..." rather than "must" and "shall." When
  something is decided, it can move into the corresponding
  documentation under `docs/` (which doesn't exist yet — when it
  does, that's where decisions land).
