"""Measurement-claim sweep — the corpus-wide version of the state-locus and
signal-separation measurement checks.

CLAUDE.md § "Subtler substrate breaches" names three failure modes that the
"every op runs on the substrate" dispatch check does NOT catch. The 2026-06-02
retrospective flagged this class (C5, "dispatch cleanliness mistaken for
sufficiency") as the breach that cost the most weeks and has the WEAKEST
automation. One of the three — the dimension audit — is now a sweep
(`dimension_audit_sweep.py`). This sweep covers the other two:

  #2 STATE-LOCUS. A `.su` labelled "RNN"/"recurrent" must carry its state as a
     vector surviving across ticks ON THE SUBSTRATE — not `make_real(scalar) ->
     host -> real()` per tick (that is a host counter wearing an RNN label).
     `count.su`'s walk-10-steps-no-host-feedback test is the template.

  #3 SIGNAL-SEPARATION. A `.su` that classifies must ship a MEASURED
     `gap = min(positive_class) - max(negative_class)` table — otherwise
     "the substrate decides X" is an unverified claim. `test_font_bound.py`'s
     lit/unlit gap and `measure_select_gap.py`'s operator gap are the templates.

Per todo.md § FV these two "need a per-`.su` CLAIM annotation before they can be
swept" (unlike the dimension one, where codebook-use is intrinsic). The
annotation surface is a comment in the `.su`:

    // @fv-claim: rnn test=demos/gui/test_gui_counter.py
    // @fv-claim: classifier test=demos/font/test_font_bound.py

For each claim this sweep enforces the claim->measurement LINKAGE:
  - the linked measurement file must EXIST;
  - rnn  => static state-locus check on the `.su`: it must carry a `recurring`
    vector through `recur(...)` AND contain NO host accessor (`real`/`imag`/
    `truth`/`component`) — the per-tick host-extraction breach signature;
  - classifier => the linked measurement file must compute a measured gap
    (a `gap` over `min(...)`/`max(...)`).
It also reports any UNANNOTATED state-bearing (`recur`+`recurring`) `.su` as an
advisory "carries substrate state, no measurement linkage" list.

**Advisory, not a hard gate by default** (matching `dimension_audit_sweep.py`):
exits 0 and just reports. `--strict` exits non-zero when an ANNOTATED claim fails
to verify (missing test, host-accessor breach, or no measured gap) — a real
broken claim, never the advisory unannotated list. Whether to wire `--strict`
into CI as a blocking gate is Emma's call (the gate-semantics decision todo §FV
reserves for her).

It is a STATIC analysis (read source + grep the linked file, no compile / no
torch), so it is fast and dependency-light.

Run from the repo root (or anywhere):

    python experiments/measurement_claim_sweep.py [--strict]
"""
from __future__ import annotations

import glob
import os
import re
import sys

# // @fv-claim: <kind> [test=<path>]
_CLAIM_RE = re.compile(
    r"//\s*@fv-claim:\s*(rnn|classifier)\b(?:\s+test=(\S+))?", re.IGNORECASE
)
# Host-readout accessors being removed from the language (CLAUDE.md § NO
# introspection). `\breal\b` does NOT match inside `make_real(` — the `_` is a
# word char, so there is no word boundary before "real" there.
_ACCESSOR_RE = re.compile(r"\b(?:real|imag|truth|component)\s*\(")
_RECUR_RE = re.compile(r"\brecur\s*\(")
_RECURRING_RE = re.compile(r"\brecurring\b")
_GAP_RE = re.compile(r"\bgap\b")
_MINMAX_RE = re.compile(r"\bmin\s*\(|\bmax\s*\(")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def check_rnn_claim(su_src: str, test_path: str | None, repo: str) -> list[str]:
    """State-locus check (#2). Returns a list of problems (empty == verified)."""
    problems: list[str] = []
    if not test_path:
        problems.append("rnn claim missing `test=<path>` linkage")
    elif not os.path.exists(os.path.join(repo, test_path)):
        problems.append(f"linked rnn test not found: {test_path}")
    if not (_RECUR_RE.search(su_src) and _RECURRING_RE.search(su_src)):
        problems.append(
            "rnn claim but no `recurring` vector through `recur(...)` — "
            "state-locus breach: the recurrence is not a substrate vector"
        )
    if _ACCESSOR_RE.search(su_src):
        problems.append(
            "rnn claim but a host accessor (real/imag/truth/component) appears — "
            "the per-tick host-extraction breach (state round-trips through a scalar)"
        )
    return problems


def check_classifier_claim(test_path: str | None, repo: str) -> list[str]:
    """Signal-separation check (#3). Returns a list of problems (empty == verified)."""
    if not test_path:
        return ["classifier claim missing `test=<path>` linkage"]
    full = os.path.join(repo, test_path)
    if not os.path.exists(full):
        return [f"linked classifier measurement not found: {test_path}"]
    src = _read(full)
    if not (_GAP_RE.search(src) and _MINMAX_RE.search(src)):
        return [
            f"classifier claim's measurement {test_path} computes no measured "
            "gap (need a `gap = min(positive) - max(negative)` table)"
        ]
    return []


def scan(repo: str):
    """Returns (verified, broken, unannotated_programs, unannotated_fixtures)."""
    patterns = [
        os.path.join(repo, "sdk", "sutra-compiler", "tests", "corpus", "valid", "*.su"),
        os.path.join(repo, "examples", "**", "*.su"),
        os.path.join(repo, "demos", "**", "*.su"),
        os.path.join(repo, "experiments", "**", "*.su"),
    ]
    files: list[str] = []
    for p in patterns:
        files.extend(glob.glob(p, recursive=True))
    files = sorted(set(files))

    verified: list[str] = []          # (rel, kind) — annotated claim that checks out
    broken: list[tuple[str, list[str]]] = []   # (rel, problems)
    unannotated_programs: list[str] = []
    unannotated_fixtures: list[str] = []

    for path in files:
        rel = os.path.relpath(path, repo).replace(os.sep, "/")
        try:
            src = _read(path)
        except OSError:
            continue
        claims = _CLAIM_RE.findall(src)
        if claims:
            for kind, test_path in claims:
                kind = kind.lower()
                test_path = test_path or None
                if kind == "rnn":
                    problems = check_rnn_claim(src, test_path, repo)
                else:
                    problems = check_classifier_claim(test_path, repo)
                if problems:
                    broken.append((f"{rel} [{kind}]", problems))
                else:
                    verified.append(f"{rel} [{kind}] -> {test_path}")
            continue
        # No claim. Flag state-bearing programs that carry substrate state but
        # link no measurement — advisory only.
        if _RECUR_RE.search(src) and _RECURRING_RE.search(src):
            if "tests/corpus" in rel:
                unannotated_fixtures.append(rel)
            else:
                unannotated_programs.append(rel)

    return verified, broken, unannotated_programs, unannotated_fixtures


def main() -> int:
    strict = "--strict" in sys.argv[1:]
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)

    verified, broken, prog_free, fix_free = scan(repo)

    if verified:
        print("Verified measurement claims (annotation -> measurement linkage holds):")
        for v in verified:
            print(f"  ok  {v}")
    if broken:
        print("\nBROKEN measurement claims (annotated but the claim does not verify):")
        for rel, problems in broken:
            print(f"  FAIL {rel}")
            for p in problems:
                print(f"        - {p}")
    if prog_free:
        print("\nAdvisory — state-bearing programs with NO measurement claim "
              "(carry a `recurring` vector through `recur`; if any asserts RNN "
              "status, add `// @fv-claim: rnn test=...` + a walk-N state-locus test):")
        for rel in prog_free:
            print(f"  ?   {rel}")

    print(
        f"\nMeasurement-claim audit — {len(verified)} verified, {len(broken)} broken, "
        f"{len(prog_free)} unannotated state-bearing program(s) [advisory], "
        f"{len(fix_free)} state-bearing corpus fixture(s) [expected]."
    )
    if broken and strict:
        print("--strict: failing because annotated measurement claims did not verify.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
