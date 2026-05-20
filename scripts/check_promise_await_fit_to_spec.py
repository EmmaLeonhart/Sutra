"""check_promise_await_fit_to_spec.py — watchdog for Audit REAL LEAK #3.

Hourly cron driver (CronCreate in-session, durable). Verifies the
promise/await implementation matches the spec across two surfaces:

1. Regression test 4/4 green: tests/test_await_substrate_pure.py.
2. The host-bounded-poll leak signatures do NOT reappear inside
   codegen_pytorch.py's await_value emission window. The signatures
   to ban are `for _ in range(100)` and `if self.isPending` (the
   exact pre-fix shape that Audit.md cites). If they reappear,
   something has rewired the substrate-pure reduction back into a
   host poll loop and the safety claim is broken.

Spec authorities:
- planning/sutra-spec/promises.md (Stage 2 lowering)
- planning/sutra-spec/axon-io.md (norm(slot) > eps arrival check)
- Audit.md REAL LEAK #3 (status: FIXED 2026-05-17)

On regression: exits non-zero and prints a clear repro message.
The cron driver (claude session) will then read the message, reopen
queue.md item, commit, push.

Run directly: `python scripts/check_promise_await_fit_to_spec.py`.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CODEGEN = REPO_ROOT / "sdk" / "sutra-compiler" / "sutra_compiler" / "codegen_pytorch.py"
TEST_FILE = "tests/test_await_substrate_pure.py"
COMPILER_DIR = REPO_ROOT / "sdk" / "sutra-compiler"

# The two host-poll-loop signatures the 2026-05-17 fix removed.
# Both must remain absent from await_value's emission.
LEAK_SIGS = (
    "for _ in range(100)",
    "if self.isPending",
)


def find_await_value_block(src: str) -> str:
    """Slice from `def await_value(self, p):` to the next top-level
    method definition. The block is what we lint for leak signatures.
    """
    match = re.search(r'self\._emit\("def await_value\(self, p\):"\)', src)
    if not match:
        return ""
    start = match.start()
    # End at the next `# ----` section header or `self._emit("def `
    # at the same indent, whichever comes first.
    remainder = src[start + 1:]
    next_def = re.search(r'self\._emit\("def [a-zA-Z_]', remainder)
    end = start + 1 + (next_def.start() if next_def else len(remainder))
    return src[start:end]


def check_codegen() -> list[str]:
    """Return a list of regression messages. Empty list = clean."""
    if not CODEGEN.exists():
        return [f"FATAL: codegen file not found at {CODEGEN}"]
    src = CODEGEN.read_text(encoding="utf-8")
    block = find_await_value_block(src)
    if not block:
        return ["FATAL: could not locate await_value emission block"]
    messages: list[str] = []
    for sig in LEAK_SIGS:
        # The signature appears inside an `_emit("...")` string in
        # the codegen — meaning the EMITTED runtime has it. The
        # block's own docstring may discuss the signature in prose
        # (e.g., "the prior body was a host Python ...") but never
        # inside `_emit("`. So we look for `_emit("` immediately
        # followed by a string that contains the signature.
        emitted = re.findall(r'self\._emit\("([^"]*)"\)', block)
        for line in emitted:
            if sig in line:
                messages.append(
                    f"REGRESSION: leak signature `{sig}` re-emitted inside "
                    f"await_value: `{line[:80]}...`"
                )
    return messages


def run_regression_tests() -> tuple[bool, str]:
    """Run tests/test_await_substrate_pure.py. Returns (passed, output)."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", TEST_FILE, "-v", "--tb=short"],
            cwd=str(COMPILER_DIR),
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired as e:
        return False, f"TIMEOUT after 120s: {e}"
    except Exception as e:  # pragma: no cover
        return False, f"EXCEPTION: {e!r}"


def main() -> int:
    print("=" * 70)
    print("check_promise_await_fit_to_spec — watchdog for Audit REAL LEAK #3")
    print("=" * 70)
    print()
    print("Spec authorities:")
    print("  - planning/sutra-spec/promises.md (Stage 2 lowering)")
    print("  - planning/sutra-spec/axon-io.md  (norm(slot) > eps arrival)")
    print("  - Audit.md REAL LEAK #3           (status: FIXED 2026-05-17)")
    print()

    codegen_issues = check_codegen()
    if codegen_issues:
        print("[1/2] codegen lint  FAIL")
        for msg in codegen_issues:
            print(f"      {msg}")
    else:
        print("[1/2] codegen lint  PASS (no leak signature in await_value emission)")

    print("[2/2] regression tests  running...")
    tests_ok, output = run_regression_tests()
    if tests_ok:
        print("[2/2] regression tests  PASS (4/4 expected)")
    else:
        print("[2/2] regression tests  FAIL")
        print(output[-2000:])

    print()
    if codegen_issues or not tests_ok:
        print("RESULT: REGRESSION — promise/await drifted from spec.")
        print("Reopen queue.md REAL LEAK #3, commit, push.")
        return 1
    print("RESULT: FIT-TO-SPEC — no action needed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
