"""Run one claim's audit: baseline, then a mutation campaign on the claimed region.

Order matters and is enforced. The baseline runs first and a non-green baseline
short-circuits the whole claim to INCONCLUSIVE, because a campaign on a red or
uncollectable tree reports a perfect kill rate for free.

The second guard is subtler and is the one most campaigns miss: a mutant that
stops the check from *running at all* -- an import error, a collection failure,
a usage error -- looks exactly like a kill from the outside. It is not evidence
that the check reads the claimed behaviour. Those runs are counted separately
and excluded from the kill tally.
"""

from __future__ import annotations

import concurrent.futures
import tempfile
from pathlib import Path
from typing import Any, Callable

from . import baseline as baseline_mod
from . import mutants as mutants_mod
from . import static_scan
from .claims import Claim
from .runner import CommandResult, isolated_copy, run, verify_isolation
from .verdicts import ClaimResult, Verdict

#: exit codes that mean the check never ran; see baseline.DID_NOT_RUN_EXIT_CODES.
NON_EVIDENTIAL_EXITS = set(baseline_mod.DID_NOT_RUN_EXIT_CODES)


def _mutant_outcome(result: CommandResult) -> str:
    """'killed', 'survived', or 'did_not_run'."""
    combined = f"{result.stdout}\n{result.stderr}"
    if result.timed_out:
        return "did_not_run"
    if result.returncode in NON_EVIDENTIAL_EXITS or "INTERNALERROR" in combined:
        return "did_not_run"
    if baseline_mod.collected_count(combined) == 0:
        return "did_not_run"
    return "survived" if result.returncode == 0 else "killed"


def _run_one_mutant(root: Path, claim: Claim, mutant: mutants_mod.Mutant,
                    timeout_s: float) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="vacuity-") as tmp:
        sandbox = Path(tmp) / "tree"          # does not exist yet -- required
        isolated_copy(root, sandbox)
        target = sandbox / mutant.relative_path
        target.write_text(mutant.source, encoding="utf-8")
        if not verify_isolation(sandbox, mutant.relative_path, mutant.source):
            return {"mutant": mutant.key(), "description": mutant.description,
                    "outcome": "did_not_run",
                    "why": "sandbox did not contain the mutated bytes"}
        result = run(claim.check, cwd=sandbox, timeout_s=timeout_s)
        outcome = _mutant_outcome(result)
        return {"mutant": mutant.key(), "description": mutant.description,
                "outcome": outcome, "returncode": result.returncode,
                "collected": baseline_mod.collected_count(f"{result.stdout}\n{result.stderr}"),
                "duration_s": round(result.duration_s, 2)}


def audit_claim(root: Path, claim: Claim, *, max_mutants: int = 12,
                workers: int = 4, timeout_s: float = 600.0,
                progress: Callable[[str], None] | None = None) -> ClaimResult:
    root = Path(root).resolve()
    say = progress or (lambda _m: None)

    verified_path = root / claim.verifies
    if not verified_path.is_file():
        return ClaimResult(claim.id, Verdict.INCONCLUSIVE,
                           f"'verifies' path does not exist: {claim.verifies}")

    say(f"[{claim.id}] baseline: {claim.check_display}")
    base = baseline_mod.assess(run(claim.check, cwd=root, timeout_s=timeout_s))
    findings = [f.to_dict() for f in static_scan.scan_path(root / "tests", root)] \
        if (root / "tests").exists() else []

    if not base["green"]:
        return ClaimResult(
            claim.id, Verdict.INCONCLUSIVE,
            "baseline is not green, so no mutation result from it would mean "
            "anything: " + "; ".join(base["not_green_because"]),
            static_findings=findings, baseline=base)

    pool = mutants_mod.generate(verified_path, claim.verifies, claim.lines,
                                limit=max_mutants)
    if not pool:
        return ClaimResult(
            claim.id, Verdict.INCONCLUSIVE,
            f"no behaviour-changing mutation could be generated in {claim.verifies}"
            + (f" lines {claim.lines[0]}-{claim.lines[1]}" if claim.lines else ""),
            static_findings=findings, baseline=base)

    say(f"[{claim.id}] {len(pool)} mutants across {workers} workers")
    outcomes: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_run_one_mutant, root, claim, m, timeout_s) for m in pool]
        for fut in concurrent.futures.as_completed(futures):
            outcomes.append(fut.result())

    killed = [o for o in outcomes if o["outcome"] == "killed"]
    survived = [o for o in outcomes if o["outcome"] == "survived"]
    did_not_run = [o for o in outcomes if o["outcome"] == "did_not_run"]

    evidential = len(killed) + len(survived)
    discarded_note = (f"; {len(did_not_run)} were discarded because the check never ran"
                      if did_not_run else "")

    if evidential == 0:
        verdict = Verdict.INCONCLUSIVE
        reason = (f"all {len(outcomes)} mutants stopped the check from running "
                  f"(collection or usage errors), so none of them tested anything.")
    elif not killed:
        verdict = Verdict.VACUOUS
        reason = (f"0 of {evidential} mutants of {claim.verifies} turned the check red. "
                  f"Nothing that can be done to the claimed region makes this check fail, "
                  f"so green from it is not evidence for this claim{discarded_note}.")
    elif survived:
        verdict = Verdict.WEAK
        reason = (f"{len(killed)} of {evidential} mutants turned the check red, and "
                  f"{len(survived)} did not. The check is evidence, and it also accepts "
                  f"the wrong implementations listed below{discarded_note}.")
    else:
        verdict = Verdict.DISCRIMINATING
        reason = (f"all {evidential} mutants turned the check red{discarded_note}.")

    return ClaimResult(claim.id, verdict, reason,
                       mutants_applied=len(outcomes), mutants_killed=len(killed),
                       mutants_did_not_run=len(did_not_run),
                       survivors=survived + did_not_run,
                       static_findings=findings, baseline=base)
