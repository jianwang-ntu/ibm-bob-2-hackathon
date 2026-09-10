"""The green-baseline guard.

A mutation campaign reports "N/N mutants killed". That number is meaningless
unless the UNMUTATED tree is green first, and "green" is not the same as
"exit code 0 from something".

Three ways a baseline looks green and is not, each of which has been observed
in the wild and each of which is checked here:

  * pytest exits **5** when it collected zero tests. Nothing ran. A campaign on
    top of this kills 100% of mutants because every run is exit 5.
  * pytest exits **4** on a usage error -- a bad flag, a missing plugin. Again
    nothing ran, and again every mutant "dies".
  * a suite can raise ``INTERNALERROR`` during collection and still be reported
    by a wrapper as "no failures".

So the guard is: exit code is 0, AND the run collected at least one test, AND
no internal error appeared on either stream.
"""

from __future__ import annotations

import re
from typing import Any

from .runner import CommandResult

#: pytest's documented exit codes that mean "your tests did not run".
DID_NOT_RUN_EXIT_CODES = {
    3: "INTERNAL_ERROR (pytest exit 3)",
    4: "USAGE_ERROR -- bad flag or missing plugin (pytest exit 4)",
    5: "NO_TESTS_COLLECTED (pytest exit 5)",
}

_COLLECTED_RE = re.compile(r"collected\s+(\d+)\s+items?")
_NO_TESTS_RE = re.compile(r"no tests ran", re.IGNORECASE)
_INTERNAL_RE = re.compile(r"INTERNALERROR")


def collected_count(output: str) -> int | None:
    """Number of tests pytest says it collected, or None if it never said.

    Returning None rather than 0 matters: "the runner never reported a count"
    and "the runner reported zero" are different failures, and only the second
    one is pytest telling us something.
    """
    hits = _COLLECTED_RE.findall(output or "")
    if not hits:
        return None
    return max(int(h) for h in hits)


def assess(result: CommandResult) -> dict[str, Any]:
    """Decide whether a baseline run counts as green, and say why not."""
    combined = f"{result.stdout}\n{result.stderr}"
    count = collected_count(combined)
    reasons: list[str] = []

    if result.timed_out:
        reasons.append(f"TIMED_OUT after {result.duration_s:.1f}s")
    if result.returncode in DID_NOT_RUN_EXIT_CODES:
        reasons.append(DID_NOT_RUN_EXIT_CODES[result.returncode])
    elif result.returncode != 0:
        reasons.append(f"NON_ZERO_EXIT ({result.returncode})")
    if _INTERNAL_RE.search(combined):
        reasons.append("INTERNALERROR in output")
    if count == 0:
        reasons.append("runner reported 'collected 0 items'")
    if count is None and result.returncode == 0 and _NO_TESTS_RE.search(combined):
        reasons.append("runner reported 'no tests ran'")

    return {
        "green": not reasons,
        "returncode": result.returncode,
        "collected": count,
        "duration_s": round(result.duration_s, 3),
        "not_green_because": reasons,
        "command": result.command,
    }
