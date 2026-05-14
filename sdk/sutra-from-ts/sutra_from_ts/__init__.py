"""sutra-from-ts — transpile a typed core of TypeScript (and JavaScript-as-untyped-TS) to Sutra (.su) source.

Working CLI. `python -m sutra_from_ts input.ts` writes `input.su` next
to it. Coverage as of v0.1.0: functions (incl. arrow-as-const), classes
(fields + methods + static + constructors + `new`), interfaces,
discriminated unions, while/for/do-while loops, async/await/`Promise<T>`,
string concat, primitive arrays, enums lowered via `JavaScriptObject`.
17 fixtures pass through end-to-end (`tests/fixtures/`).

See `DESIGN.md` for the lowering rules and `docs/typescript-to-sutra.md`
in the parent Sutra repo for the user-facing TS→Sutra mapping reference.
"""

__version__ = "0.1.0"
