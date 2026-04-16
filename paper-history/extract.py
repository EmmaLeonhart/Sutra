"""Extract historical versions of the two paper files from git into paper-history/.

For each commit touching sutra-paper/paper.md (and its prior paths
s2-paper/paper.md, akasha-paper/paper.md) and language-paper/paper.md,
write the blob at that commit to
paper-history/<bucket>/NNN_<date>_<shorthash>_<slug>.md
in chronological (oldest-first) order.
"""
import subprocess
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_ROOT = REPO / "paper-history"

def slugify(s, maxlen=60):
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:maxlen]

def resolve_path_at(commit, candidate_paths):
    """Return the path that existed at this commit, or None."""
    for p in candidate_paths:
        r = subprocess.run(
            ["git", "cat-file", "-e", f"{commit}:{p}"],
            cwd=REPO, capture_output=True
        )
        if r.returncode == 0:
            return p
    return None

def extract(bucket, primary_path, fallback_paths):
    out_dir = OUT_ROOT / bucket
    out_dir.mkdir(parents=True, exist_ok=True)

    log = subprocess.check_output(
        ["git", "log", "--all", "--follow", "--format=%H|%ai|%s", "--", primary_path],
        cwd=REPO
    ).decode("utf-8", errors="replace").strip().splitlines()

    commits = []
    for line in log:
        h, ai, subject = line.split("|", 2)
        commits.append((h, ai, subject))
    commits.sort(key=lambda c: c[1])

    all_paths = [primary_path] + fallback_paths

    n_written = 0
    for idx, (h, ai, subject) in enumerate(commits, start=1):
        path = resolve_path_at(h, all_paths)
        if path is None:
            print(f"[skip] {h[:8]} — no paper.md at this commit")
            continue
        date_short = ai[:10].replace("-", "")
        time_short = ai[11:16].replace(":", "")
        slug = slugify(subject)
        short = h[:8]
        fname = f"{idx:03d}_{date_short}_{time_short}_{short}_{slug}.md"
        fpath = out_dir / fname
        blob = subprocess.check_output(
            ["git", "show", f"{h}:{path}"],
            cwd=REPO
        )
        header = (
            f"<!--\n"
            f"commit:  {h}\n"
            f"date:    {ai}\n"
            f"subject: {subject}\n"
            f"path:    {path}\n"
            f"-->\n\n"
        ).encode("utf-8")
        fpath.write_bytes(header + blob)
        n_written += 1
        print(f"[{idx:03d}] {ai[:10]} {short} {path} -> {fname}")
    print(f"\n{bucket}: wrote {n_written} versions")

if __name__ == "__main__":
    extract(
        "sutra-paper",
        "sutra-paper/paper.md",
        ["akasha-paper/paper.md", "S2-paper/paper.md", "s2-paper/paper.md"]
    )
    extract(
        "language-paper",
        "language-paper/paper.md",
        []
    )
    extract(
        "fly-brain-paper",
        "fly-brain-paper/paper.md",
        []
    )
