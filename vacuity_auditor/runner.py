"""Running a check, and running it somewhere a mutation cannot leak.

The isolation rule here exists because of a specific way a mutation campaign
lies to you: if the sandbox directory already exists, a recursive copy nests
the tree one level deeper (``dst/src/...``) instead of replacing it. The check
then runs against the *stale* copy at the old path, never sees the mutation,
and -- if the stale copy happens to be red, or the path no longer resolves --
reports the mutant as killed. Every mutant "dies" and the campaign scores 100%.

So :func:`isolated_copy` refuses to write into a directory that already exists,
and :func:`verify_isolation` proves after the fact that the sandbox really does
contain the mutated bytes.
"""

from __future__ import annotations

import dataclasses
import os
import shutil
import subprocess
import time
from pathlib import Path

#: directories never worth copying into a sandbox; they are large, and none of
#: them can change a check's verdict.
SKIP_DIRS = {".git", ".hg", ".svn", "__pycache__", ".pytest_cache", ".mypy_cache",
             ".ruff_cache", ".tox", ".venv", "venv", "node_modules", ".idea"}


@dataclasses.dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool = False


def _ignore(_dir: str, names: list[str]) -> set[str]:
    return {n for n in names if n in SKIP_DIRS}


def isolated_copy(source: Path, dest: Path) -> Path:
    """Copy ``source``'s tree to ``dest``, which must not already exist.

    Raises FileExistsError rather than merging. A merge is how a sandbox ends
    up holding two trees and a check ends up reading the wrong one.
    """
    source = Path(source).resolve()
    dest = Path(dest)
    if dest.exists():
        raise FileExistsError(
            f"refusing to copy into an existing path: {dest}. "
            "A sandbox that already exists may already hold a stale tree, and a "
            "check run against a stale tree reports mutants killed that were "
            "never applied."
        )
    shutil.copytree(source, dest, ignore=_ignore, symlinks=True)
    return dest


def verify_isolation(sandbox: Path, relative_path: str, expected_source: str) -> bool:
    """Confirm the sandbox really holds the bytes we think we put there.

    Called after a mutation is written. If this is False the run is discarded
    as INCONCLUSIVE rather than counted as a kill.
    """
    target = Path(sandbox) / relative_path
    if not target.is_file():
        return False
    try:
        return target.read_text(encoding="utf-8") == expected_source
    except (OSError, UnicodeDecodeError):
        return False


def run(command: list[str], cwd: Path, timeout_s: float = 900.0,
        env_extra: dict[str, str] | None = None) -> CommandResult:
    """Run a check command and capture both streams.

    ``stderr`` is captured separately and never merged into ``stdout``: a
    scan that redirects stderr away cannot see the error that made the run
    meaningless, which is its own way of faking a clean result.
    """
    env = os.environ.copy()
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    if env_extra:
        env.update(env_extra)
    started = time.monotonic()
    try:
        proc = subprocess.run(
            command, cwd=str(cwd), capture_output=True, text=True,
            timeout=timeout_s, env=env, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            command=list(command), returncode=-1,
            stdout=(exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
            stderr=(exc.stderr or b"").decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or ""),
            duration_s=time.monotonic() - started, timed_out=True,
        )
    return CommandResult(
        command=list(command), returncode=proc.returncode,
        stdout=proc.stdout, stderr=proc.stderr,
        duration_s=time.monotonic() - started,
    )
