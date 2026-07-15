# uncertain/ — quarantined, UNVERIFIED examples

These six files were **deliberately quarantined here by Emma on 2026-04-15**
("examples: quarantine unverified language-feature demos to uncertain/"). They are
tutorial-style demos of language features that were never verified against the compiler
and are **not** run by `examples/_smoke_test.py`.

Do not copy patterns from these files. Known problems:

- `01-objects-and-methods.su` calls `Cosine(self, them)` — **`Cosine` does not exist**
  in the language (it appears only inside a comment in `stdlib/similarity.su`). The
  real operation is `similarity(a, b)`. The call validates only because PascalCase
  names get the open-world method convention.
- The `/* */` comment style here doesn't match the rest of the example set.

For verified, idiomatic examples, use the files in `examples/` proper — everything the
smoke test runs (see the table in the root `README.md`) compiles and executes end-to-end
on every CI run.

(This README only marks status. The files themselves are left as quarantined — repairing
or deleting them is a deliberate decision, not drive-by cleanup.)
