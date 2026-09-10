"""Sandbox isolation -- the guard against a campaign scoring 100% for free."""

from pathlib import Path

import pytest

from vacuity_auditor.runner import isolated_copy, run, verify_isolation


def _tree(root: Path) -> Path:
    src = root / "src"
    src.mkdir(parents=True)
    (src / "mod.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("junk", encoding="utf-8")
    return root


def test_isolated_copy_reproduces_the_tree(tmp_path):
    """The accept path: a copy into a fresh path really carries the files."""
    source = _tree(tmp_path / "source")
    dest = isolated_copy(source, tmp_path / "sandbox")
    assert (dest / "src" / "mod.py").read_text() == "VALUE = 1\n"


def test_isolated_copy_skips_vcs_and_cache_directories(tmp_path):
    source = _tree(tmp_path / "source")
    dest = isolated_copy(source, tmp_path / "sandbox")
    assert not (dest / ".git").exists()


def test_isolated_copy_refuses_an_existing_destination(tmp_path):
    """copytree into an existing dir nests the tree and the check reads a stale copy."""
    source = _tree(tmp_path / "source")
    existing = tmp_path / "sandbox"
    existing.mkdir()
    with pytest.raises(FileExistsError):
        isolated_copy(source, existing)


def test_verify_isolation_accepts_bytes_that_are_there(tmp_path):
    source = _tree(tmp_path / "source")
    dest = isolated_copy(source, tmp_path / "sandbox")
    (dest / "src" / "mod.py").write_text("VALUE = 2\n", encoding="utf-8")
    assert verify_isolation(dest, "src/mod.py", "VALUE = 2\n") is True


def test_verify_isolation_rejects_bytes_that_are_not(tmp_path):
    source = _tree(tmp_path / "source")
    dest = isolated_copy(source, tmp_path / "sandbox")
    assert verify_isolation(dest, "src/mod.py", "VALUE = 2\n") is False
    assert verify_isolation(dest, "src/absent.py", "anything") is False


def test_run_captures_both_streams_separately(tmp_path):
    result = run(["python3", "-c",
                  "import sys; sys.stdout.write('out'); sys.stderr.write('err'); sys.exit(3)"],
                 cwd=tmp_path)
    assert result.returncode == 3
    assert result.stdout == "out"
    assert result.stderr == "err"


def test_run_reports_a_timeout_rather_than_hanging(tmp_path):
    result = run(["python3", "-c", "import time; time.sleep(30)"], cwd=tmp_path, timeout_s=1.0)
    assert result.timed_out is True
