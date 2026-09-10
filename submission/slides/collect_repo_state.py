#!/usr/bin/env python3
"""Measure the PUBLIC entry repository and write evidence/repo_state.json.

Every count the slide deck prints about the repository is produced here, from a
fresh ANONYMOUS clone -- not from the working tree, and not from the README.
The distinction matters: the deck's whole argument is that its numbers can be
rechecked by a judge, and a judge has only the public bytes.

  python3 collect_repo_state.py           # -> evidence/repo_state.json

Network: one anonymous `git clone` and one `python3 -m pytest` inside it.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
EV = HERE / "evidence"
REPO_URL = "https://github.com/jianwang-ntu/ibm-bob-2-hackathon"


def run(cmd, cwd=None, timeout=600):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def main() -> int:
    EV.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        clone = pathlib.Path(tmp) / "clone"
        rc, out, err = run(["git", "clone", "--quiet", REPO_URL, str(clone)])
        if rc != 0:
            print(f"anonymous clone FAILED rc={rc}: {err.strip()[:400]}", file=sys.stderr)
            return 1

        rc, head, _ = run(["git", "rev-parse", "HEAD"], cwd=clone)
        head = head.strip()
        rc, log, _ = run(["git", "log", "--format=%H%x09%an%x09%ae%x09%aI%x09%s"], cwd=clone)
        commits = [dict(zip(("sha", "author_name", "author_email", "date", "subject"),
                            line.split("\t")))
                   for line in log.strip().splitlines() if line]

        tracked = sorted(
            p.relative_to(clone).as_posix()
            for p in clone.rglob("*")
            if p.is_file() and ".git/" not in p.relative_to(clone).as_posix()
            and p.relative_to(clone).as_posix() != ".git")
        modules = [f for f in tracked
                   if f.startswith("vacuity_auditor/") and f.endswith(".py")
                   and not f.endswith("__init__.py")]
        test_files = [f for f in tracked if f.startswith("tests/") and f.endswith(".py")]

        rc, out, err = run(["python3", "-m", "pytest", "-q"], cwd=clone)
        m = re.search(r"(\d+) passed", out)
        tests_passed = int(m.group(1)) if m else None
        collected = None
        m2 = re.search(r"(\d+) failed", out)

        published = json.loads((clone / "evidence" / "self_audit.json").read_text("utf-8"))

        state = {
            "schema": "repo_state/v1",
            "repo_url": REPO_URL,
            "clone": "anonymous git clone, no credential presented",
            "head": head,
            "commits": commits,
            "commit_count": len(commits),
            "distinct_commit_authors": sorted({c["author_email"] for c in commits}),
            "tracked_files": len(tracked),
            "modules": sorted(modules),
            "module_count": len(modules),
            "test_files": sorted(test_files),
            "test_file_count": len(test_files),
            "tests_passed_in_clone": tests_passed,
            "tests_failed_in_clone": int(m2.group(1)) if m2 else 0,
            "pytest_returncode": rc,
            "licence": "MIT" if (clone / "LICENSE").exists() else None,
            "licence_sha256": hashlib.sha256(
                (clone / "LICENSE").read_bytes()).hexdigest()
            if (clone / "LICENSE").exists() else None,
            "readme_bytes": (clone / "README.md").stat().st_size,
            "published_self_audit_summary": published["summary"],
            "published_self_audit_kill_rates": {
                c["claim_id"]: [c["mutants_killed"],
                                c["mutants_applied"] - c["mutants_did_not_run"]]
                for c in published["claims"]},
        }
    (EV / "repo_state.json").write_text(json.dumps(state, indent=1) + "\n", "utf-8")
    print(f"wrote {EV / 'repo_state.json'}")
    print(f"  head {state['head']}  tracked {state['tracked_files']}  "
          f"modules {state['module_count']}  tests {state['tests_passed_in_clone']} passed")
    print(f"  commit authors: {state['distinct_commit_authors']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
