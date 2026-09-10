"""A claim: which check, and what that check says it verifies.

The pairing is the whole idea. "Does the suite pass?" is not auditable; "does
`tests/test_baseline.py` actually read `vacuity_auditor/baseline.py`?" is.
Without the second half a campaign credits a check for killing mutants
somewhere else in the tree.
"""

from __future__ import annotations

import dataclasses
import json
import shlex
import tomllib
from pathlib import Path


@dataclasses.dataclass
class Claim:
    id: str
    check: list[str]
    verifies: str
    lines: tuple[int, int] | None = None
    description: str = ""

    @property
    def check_display(self) -> str:
        return " ".join(self.check)


class ClaimSpecError(ValueError):
    pass


def _one(raw: dict, index: int) -> Claim:
    for field in ("id", "check", "verifies"):
        if field not in raw:
            raise ClaimSpecError(f"claim #{index}: missing required field '{field}'")
    check = raw["check"]
    if isinstance(check, str):
        check = shlex.split(check)
    if not isinstance(check, list) or not check:
        raise ClaimSpecError(f"claim '{raw['id']}': 'check' must be a non-empty command")
    lines = raw.get("lines")
    if lines is not None:
        if not (isinstance(lines, (list, tuple)) and len(lines) == 2):
            raise ClaimSpecError(f"claim '{raw['id']}': 'lines' must be [start, end]")
        lines = (int(lines[0]), int(lines[1]))
        if lines[0] > lines[1]:
            raise ClaimSpecError(f"claim '{raw['id']}': 'lines' start is after end")
    return Claim(id=str(raw["id"]), check=[str(c) for c in check],
                 verifies=str(raw["verifies"]), lines=lines,
                 description=str(raw.get("description", "")))


def load(path: Path) -> list[Claim]:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        raw = json.loads(text)
    else:
        raw = tomllib.loads(text)
    entries = raw.get("claim")
    if not entries:
        raise ClaimSpecError(f"{path}: no [[claim]] entries found")
    claims = [_one(e, i) for i, e in enumerate(entries)]
    seen: set[str] = set()
    for c in claims:
        if c.id in seen:
            raise ClaimSpecError(f"duplicate claim id '{c.id}'")
        seen.add(c.id)
    return claims
