"""The green-baseline guard: every way a baseline looks green and is not."""

from vacuity_auditor import baseline
from vacuity_auditor.runner import CommandResult


def _result(returncode=0, stdout="", stderr="", timed_out=False):
    return CommandResult(command=["python", "-m", "pytest"], returncode=returncode,
                         stdout=stdout, stderr=stderr, duration_s=0.1,
                         timed_out=timed_out)


def test_a_real_green_run_is_accepted():
    """The accept path. Without this, a guard that refuses everything looks correct."""
    verdict = baseline.assess(_result(0, "collected 7 items\n7 passed in 0.10s"))
    assert verdict["green"] is True
    assert verdict["not_green_because"] == []
    assert verdict["collected"] == 7


def test_exit_5_no_tests_collected_is_not_green():
    verdict = baseline.assess(_result(5, "collected 0 items\nno tests ran"))
    assert verdict["green"] is False
    assert any("NO_TESTS_COLLECTED" in r for r in verdict["not_green_because"])


def test_exit_4_usage_error_is_not_green():
    verdict = baseline.assess(_result(4, "", "error: unrecognized arguments: --nope"))
    assert verdict["green"] is False
    assert any("USAGE_ERROR" in r for r in verdict["not_green_because"])


def test_internal_error_is_not_green_even_on_exit_zero():
    """Exit 0 with an INTERNALERROR on stderr is the case a wrapper reports as clean."""
    verdict = baseline.assess(_result(0, "collected 3 items", "INTERNALERROR> boom"))
    assert verdict["green"] is False
    assert any("INTERNALERROR" in r for r in verdict["not_green_because"])


def test_collected_zero_is_not_green_even_on_exit_zero():
    verdict = baseline.assess(_result(0, "collected 0 items"))
    assert verdict["green"] is False


def test_timeout_is_not_green():
    verdict = baseline.assess(_result(0, "collected 2 items", timed_out=True))
    assert verdict["green"] is False
    assert any("TIMED_OUT" in r for r in verdict["not_green_because"])


def test_collected_count_distinguishes_absent_from_zero():
    """None and 0 are different failures; collapsing them loses the distinction."""
    assert baseline.collected_count("no such line here") is None
    assert baseline.collected_count("collected 0 items") == 0
    assert baseline.collected_count("collected 12 items") == 12


def test_collected_count_takes_the_largest_report():
    assert baseline.collected_count("collected 3 items\ncollected 11 items") == 11
