"""vacuity-auditor -- ask of a verification check: can this ever go red?

The tool audits the *check*, not the code the check is pointed at. A check that
cannot fail is worse than no check, because it is read as evidence.
"""

__version__ = "0.1.0"

from .verdicts import Verdict, ClaimResult  # noqa: F401
