"""Unit tests for the paper-submit script.

Covers the pure-function helpers that don't hit the network. The actual
submit() and fetch_review() paths are exercised by the GitHub Actions
workflow against the live clawRxiv API.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make scripts/ importable.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from paper_submit_and_fetch import (  # noqa: E402
    extract_h1_title,
    next_version_number,
    read_paper,
    read_post_id,
    render_review_markdown,
)


def test_extract_h1_title_present() -> None:
    assert extract_h1_title("# Yantra\n\nbody") == "Yantra"


def test_extract_h1_title_with_trailing_spaces() -> None:
    assert extract_h1_title("#   Yantra: A System  \n\nbody") == "Yantra: A System"


def test_extract_h1_title_absent_returns_none() -> None:
    assert extract_h1_title("## Subhead first\n\nbody") is None


def test_read_post_id_missing(tmp_path: Path) -> None:
    assert read_post_id(tmp_path) is None


def test_read_post_id_present(tmp_path: Path) -> None:
    (tmp_path / ".post_id").write_text("4242\n", encoding="utf-8")
    assert read_post_id(tmp_path) == 4242


def test_read_post_id_garbage_returns_none(tmp_path: Path) -> None:
    (tmp_path / ".post_id").write_text("not-a-number", encoding="utf-8")
    assert read_post_id(tmp_path) is None


def test_read_post_id_empty_returns_none(tmp_path: Path) -> None:
    (tmp_path / ".post_id").write_text("   \n", encoding="utf-8")
    assert read_post_id(tmp_path) is None


def test_read_paper_extracts_abstract(tmp_path: Path) -> None:
    (tmp_path / "paper.md").write_text(
        "# Title\n\n## Abstract\n\nFirst paragraph.\n\n"
        "Second paragraph.\n\n## Introduction\n\nbody",
        encoding="utf-8",
    )
    content, skill, abstract = read_paper(tmp_path)
    assert "First paragraph." in abstract
    assert "Second paragraph." in abstract
    assert "Introduction" not in abstract
    assert skill is None  # no SKILL.md present


def test_read_paper_picks_up_skill(tmp_path: Path) -> None:
    (tmp_path / "paper.md").write_text(
        "# T\n\n## Abstract\n\nA.\n\n## Next\n\nbody", encoding="utf-8",
    )
    (tmp_path / "SKILL.md").write_text("reviewer guidance", encoding="utf-8")
    _, skill, _ = read_paper(tmp_path)
    assert skill == "reviewer guidance"


def test_read_paper_falls_back_when_no_abstract(tmp_path: Path) -> None:
    (tmp_path / "paper.md").write_text(
        "# T\n\nNo abstract section here, just body. " + "x" * 1000,
        encoding="utf-8",
    )
    _, _, abstract = read_paper(tmp_path)
    # Falls back to first 500 chars.
    assert len(abstract) == 500


def test_read_paper_abstract_handles_unnumbered_next_heading(tmp_path: Path) -> None:
    # The Alignment-repo regression: an earlier version of the regex
    # required the next H2 to start with a digit. We match `\n## ` now,
    # so an `## Introduction` (no digit) cleanly bounds the abstract.
    (tmp_path / "paper.md").write_text(
        "# T\n\n## Abstract\n\nReal abstract text.\n\n## Introduction\n\nbody",
        encoding="utf-8",
    )
    _, _, abstract = read_paper(tmp_path)
    assert abstract == "Real abstract text."


def test_read_paper_missing_paper_md_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_paper(tmp_path)


def test_next_version_number_empty_dir(tmp_path: Path) -> None:
    assert next_version_number(tmp_path) == 1


def test_next_version_number_missing_dir(tmp_path: Path) -> None:
    assert next_version_number(tmp_path / "does-not-exist") == 1


def test_next_version_number_counts_existing(tmp_path: Path) -> None:
    (tmp_path / "v1_post10_review.json").write_text("{}", encoding="utf-8")
    (tmp_path / "v2_post11_review.json").write_text("{}", encoding="utf-8")
    # Non-matching files don't count.
    (tmp_path / "random.txt").write_text("x", encoding="utf-8")
    assert next_version_number(tmp_path) == 3


def test_render_review_markdown_with_rating() -> None:
    md = render_review_markdown(
        {"rating": "weak accept", "body": "ok-ish"}, version=1, post_id=42,
    )
    assert "Review v1 · post 42" in md
    assert "**Rating:** weak accept" in md
    assert "ok-ish" in md


def test_render_review_markdown_falls_back_to_json_dump() -> None:
    md = render_review_markdown({"unexpected_shape": True}, version=5, post_id=7)
    assert "Review v5 · post 7" in md
    assert "unexpected_shape" in md


def test_render_review_markdown_prefers_review_over_body() -> None:
    md = render_review_markdown(
        {"review": "the actual review", "body": "ignored"},
        version=1, post_id=1,
    )
    assert "the actual review" in md
    assert "ignored" not in md


def test_yantra_paper_md_abstract_extracts_cleanly() -> None:
    """The actual paper.md in this repo extracts a non-trivial abstract.

    Guards against future edits that accidentally break the H2 structure
    and cause submission to fall back to the 500-char prefix (which then
    truncates mid-sentence — the bug that bit the Alignment paper).
    """
    paper_dir = ROOT / "paper"
    if not (paper_dir / "paper.md").exists():
        pytest.skip("paper/paper.md not present")
    content, _, abstract = read_paper(paper_dir)
    # Should be substantive, not the 500-char fallback.
    assert len(abstract) > 500
    # Should not bleed into the next section.
    assert "## 1. Introduction" not in abstract
    assert "## Introduction" not in abstract
