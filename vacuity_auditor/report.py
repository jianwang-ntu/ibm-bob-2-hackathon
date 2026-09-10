"""Rendering an audit, and the exit code it earns."""

from __future__ import annotations

import json
from typing import Any, Iterable

from .verdicts import ClaimResult, Verdict

_MARK = {Verdict.DISCRIMINATING: "DISCRIMINATING", Verdict.WEAK: "WEAK",
         Verdict.VACUOUS: "VACUOUS", Verdict.INCONCLUSIVE: "INCONCLUSIVE"}


def render(results: Iterable[ClaimResult]) -> str:
    results = list(results)
    width = max([len(r.claim_id) for r in results] + [10])
    lines = ["", f"{'CLAIM'.ljust(width)}  {'VERDICT':<15} KILLED  DETAIL",
             "-" * (width + 60)]
    for r in results:
        ratio = f"{r.mutants_killed}/{r.evidential}" if r.evidential > 0 else "-"
        lines.append(f"{r.claim_id.ljust(width)}  {_MARK[r.verdict]:<15} {ratio:>6}  {r.reason}")
        for s in r.survivors:
            note = s.get("why") or f"exit {s.get('returncode')}"
            lines.append(f"{' ' * width}    - {s['outcome']}: {s['mutant']} ({s['description']}) [{note}]")
    static = results[0].static_findings if results else []
    if static:
        lines += ["", f"static vacuity candidates ({len(static)}) -- these locate, they do not decide:"]
        for f in static[:20]:
            lines.append(f"  {f['pattern']:<22} {f['relative_path']}:{f['lineno']}  {f['test_name']}  -- {f['detail']}")
        if len(static) > 20:
            lines.append(f"  ... and {len(static) - 20} more")
    lines.append("")
    return "\n".join(lines)


def to_json(results: Iterable[ClaimResult]) -> str:
    results = list(results)
    payload: dict[str, Any] = {
        "claims": [r.to_dict() for r in results],
        "summary": {
            "total": len(results),
            "discriminating": sum(1 for r in results if r.verdict is Verdict.DISCRIMINATING),
            "weak": sum(1 for r in results if r.verdict is Verdict.WEAK),
            "vacuous": sum(1 for r in results if r.verdict is Verdict.VACUOUS),
            "inconclusive": sum(1 for r in results if r.verdict is Verdict.INCONCLUSIVE),
        },
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def exit_code(results: Iterable[ClaimResult]) -> int:
    """0 clean, 1 any VACUOUS, 2 any INCONCLUSIVE, 3 any WEAK.

    Each band gets its own code on purpose. "This check is not evidence",
    "we could not tell", and "it is evidence with these named gaps" call for
    three different actions, and collapsing them is how an unknown gets read
    as a pass.
    """
    results = list(results)
    if any(r.verdict is Verdict.VACUOUS for r in results):
        return 1
    if any(r.verdict is Verdict.INCONCLUSIVE for r in results):
        return 2
    if any(r.verdict is Verdict.WEAK for r in results):
        return 3
    return 0
