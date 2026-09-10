"""The four verdicts, and the record one claim's audit produces.

There are four, and the fourth was added after running this tool on its own
example project. The first design had three -- DISCRIMINATING / VACUOUS /
INCONCLUSIVE -- and any surviving mutant made a claim VACUOUS. Measured, the
honest value-checking suite in ``examples/demo_project`` killed 8 of 10 mutants
and the deliberately vacuous one killed 2, and the three-verdict rule called
both of them VACUOUS. That rule answered a different question from the one on
the tin: a check that kills 8 of 10 mutants very obviously *can* go red.

So the bands now follow the question the tool actually asks:

  VACUOUS         killed nothing. No change to the claimed region turns this
                  check red, so green from it is not evidence for this claim.
  WEAK            killed some, and named survivors remain. The check is
                  evidence, and it also accepts specific wrong implementations.
                  This is where most machine-written tests land.
  DISCRIMINATING  killed every mutant that ran.
  INCONCLUSIVE    the audit could not reach a conclusion -- no green baseline,
                  no mutant generated, or every mutant stopped the check from
                  running at all.

INCONCLUSIVE is kept separate from the other three on purpose. "We could not
tell" read as "it passed" is the failure this whole tool is about.
"""

from __future__ import annotations

import dataclasses
import enum
from typing import Any


class Verdict(str, enum.Enum):
    DISCRIMINATING = "DISCRIMINATING"
    WEAK = "WEAK"
    VACUOUS = "VACUOUS"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclasses.dataclass
class ClaimResult:
    claim_id: str
    verdict: Verdict
    reason: str
    mutants_applied: int = 0
    mutants_killed: int = 0
    mutants_did_not_run: int = 0
    survivors: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    static_findings: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    baseline: dict[str, Any] | None = None

    @property
    def evidential(self) -> int:
        """Mutants that actually exercised the check.

        ``mutants_applied`` counts every run, including the ones where the
        mutation stopped the check from running at all. Reporting a kill rate
        over that total states a denominator the numerator was never measured
        against -- which is the same class of error the tool exists to find.
        """
        return self.mutants_applied - self.mutants_did_not_run

    @property
    def kill_rate(self) -> float | None:
        if self.evidential <= 0:
            return None
        return self.mutants_killed / self.evidential

    def to_dict(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d["verdict"] = self.verdict.value
        d["kill_rate"] = self.kill_rate
        return d
