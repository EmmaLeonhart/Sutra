"""Regression test for the "stop new chains" guard in
paper_submit_and_fetch.py (Emma 2026-05-30).

The bug it guards against: during clawRxiv's 2026-05-27 `/revise` outage,
the submit script's create-fallback minted a brand-new orphan post on every
push instead of revising the pinned chain, producing orphans 2626..2632.
The guard makes a *successful* create-while-pinned a loud CI failure that
LEAVES `.post_id` pinned, so the next push retries revise against the chain
rather than feeding an orphan.

Run: python scripts/test_paper_submit_guard.py   (or via pytest)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import paper_submit_and_fetch as psf  # noqa: E402


def _make_paper_dir(tmp: Path, pinned_id: str) -> Path:
    d = tmp / "fv"
    d.mkdir()
    (d / "paper.md").write_text(
        "# A Stable Title That Does Not Change\n\n"
        "## Abstract\n\nA stable abstract.\n\n## Introduction\n\nBody.\n",
        encoding="utf-8",
    )
    (d / ".post_id").write_text(pinned_id, encoding="utf-8")
    return d


def _run_main(monkeyenv, argv):
    old_argv = sys.argv
    sys.argv = argv
    try:
        return psf.main()
    finally:
        sys.argv = old_argv


def test_revise_404_then_create_success_is_refused(tmp_path, monkeypatch):
    """revise() 404s; create() *succeeds* (orphan). Guard must return 1 and
    leave .post_id untouched at the pinned chain tip."""
    paper_dir = _make_paper_dir(tmp_path, "2677")
    monkeypatch.setenv("CLAWRXIV_API_KEY", "test-key")

    def fake_revise(*, api_key, post_id, payload):
        raise psf.ReviseNotFound(f"simulated 404 on /api/posts/{post_id}/revise")

    def fake_create(*, api_key, payload):
        # clawRxiv minted a fresh orphan instead of 409-deduping.
        return {"id": 9999}

    monkeypatch.setattr(psf, "revise_post", fake_revise)
    monkeypatch.setattr(psf, "create_post", fake_create)

    rc = _run_main(monkeypatch, [
        "prog", "--paper-dir", str(paper_dir),
        "--tags", "x", "--no-review-wait",
    ])

    assert rc == 1, f"expected loud-fail exit 1, got {rc}"
    assert (paper_dir / ".post_id").read_text(encoding="utf-8").strip() == "2677", \
        "guard must NOT re-pin .post_id to the orphan"


def test_revise_409_dedup_recovers_to_canonical(tmp_path, monkeypatch):
    """The GOOD path must still work: revise() 409s naming a duplicate, the
    script revises that canonical post and pins to it. Not refused."""
    paper_dir = _make_paper_dir(tmp_path, "2677")
    monkeypatch.setenv("CLAWRXIV_API_KEY", "test-key")

    calls = {"revise_ids": []}

    def fake_revise(*, api_key, post_id, payload):
        calls["revise_ids"].append(post_id)
        if post_id == 2677:
            raise psf.SupersedeConflict(
                "409", body={"data": {"duplicateId": 2633}}
            )
        return {"id": 2680}  # canonical revise succeeds with a new version id

    def fake_create(*, api_key, payload):  # must NOT be called on this path
        raise AssertionError("create_post should not run on the 409-dedup path")

    monkeypatch.setattr(psf, "revise_post", fake_revise)
    monkeypatch.setattr(psf, "create_post", fake_create)

    rc = _run_main(monkeypatch, [
        "prog", "--paper-dir", str(paper_dir),
        "--tags", "x", "--no-review-wait",
    ])

    assert rc == 0, f"expected success on dedup recovery, got {rc}"
    assert calls["revise_ids"] == [2677, 2633], calls["revise_ids"]
    assert (paper_dir / ".post_id").read_text(encoding="utf-8").strip() == "2680", \
        "should pin to the new version id from revising the canonical"


def _standalone() -> int:
    """Run without pytest: minimal tmp_path/monkeypatch shims."""
    import tempfile
    import types

    class _MP:
        def __init__(self):
            self._undo = []

        def setenv(self, k, v):
            old = sys.modules["os"].environ.get(k)
            self._undo.append(lambda: _restore_env(k, old))
            sys.modules["os"].environ[k] = v

        def setattr(self, obj, name, val):
            old = getattr(obj, name)
            self._undo.append(lambda: setattr(obj, name, old))
            setattr(obj, name, val)

        def undo(self):
            for fn in reversed(self._undo):
                fn()

    def _restore_env(k, old):
        if old is None:
            sys.modules["os"].environ.pop(k, None)
        else:
            sys.modules["os"].environ[k] = old

    failures = 0
    for test in (
        test_revise_404_then_create_success_is_refused,
        test_revise_409_dedup_recovers_to_canonical,
    ):
        mp = _MP()
        try:
            with tempfile.TemporaryDirectory() as td:
                test(Path(td), mp)
            print(f"PASS: {test.__name__}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"FAIL: {test.__name__}: {e}")
        finally:
            mp.undo()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_standalone())
