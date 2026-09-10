"""The whole audit, on throwaway projects, including the paths that must ACCEPT.

Every band is exercised here. A guard tested only on the input it is supposed
to refuse has never been shown to let anything through.
"""

import textwrap
from pathlib import Path

from vacuity_auditor.audit import audit_claim
from vacuity_auditor.claims import Claim
from vacuity_auditor.verdicts import Verdict

MODULE = "def add(a, b):\n    return a + b\n"


def _project(root: Path, test_body: str, module: str = MODULE) -> Path:
    (root / "src").mkdir(parents=True)
    (root / "src" / "__init__.py").write_text("", encoding="utf-8")
    (root / "src" / "calc.py").write_text(module, encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_calc.py").write_text(textwrap.dedent(test_body), encoding="utf-8")
    return root


def _claim(check="python3 -m pytest tests/test_calc.py -q"):
    return Claim(id="c", check=check.split(), verifies="src/calc.py")


def test_a_value_checking_suite_is_discriminating(tmp_path):
    """ACCEPT PATH. Without this the tool could refuse everything and look right."""
    _project(tmp_path, '''
        from src.calc import add

        def test_add():
            assert add(2, 3) == 5
    ''')
    result = audit_claim(tmp_path, _claim(), max_mutants=6, workers=3)
    assert result.verdict is Verdict.DISCRIMINATING, result.reason
    assert result.mutants_applied > 0
    assert result.mutants_killed == result.mutants_applied


def test_a_suite_that_swallows_its_assertion_is_vacuous(tmp_path):
    _project(tmp_path, '''
        from src.calc import add

        def test_add_does_not_explode():
            try:
                assert add(2, 3) == 5
            except Exception:
                pass
    ''')
    result = audit_claim(tmp_path, _claim(), max_mutants=6, workers=3)
    assert result.verdict is Verdict.VACUOUS, result.reason
    assert result.mutants_killed == 0
    assert result.mutants_applied > 0


def test_a_partial_suite_is_weak_not_vacuous(tmp_path):
    """A check that catches some wrong implementations is evidence, with gaps."""
    _project(tmp_path, '''
        from src.calc import add

        def test_add_returns_a_number():
            assert isinstance(add(2, 3), int)
    ''')
    result = audit_claim(tmp_path, _claim(), max_mutants=6, workers=3)
    assert result.verdict is Verdict.WEAK, result.reason
    assert 0 < result.mutants_killed < result.mutants_applied
    assert result.survivors


def test_a_red_baseline_short_circuits_to_inconclusive(tmp_path):
    """No mutation result from a red tree means anything, so none are run."""
    _project(tmp_path, '''
        from src.calc import add

        def test_add():
            assert add(2, 3) == 6
    ''')
    result = audit_claim(tmp_path, _claim(), max_mutants=6, workers=3)
    assert result.verdict is Verdict.INCONCLUSIVE
    assert result.mutants_applied == 0
    assert "baseline is not green" in result.reason


def test_a_suite_that_collects_nothing_is_inconclusive_not_perfect(tmp_path):
    """pytest exit 5. Left unguarded this scores a 100% kill rate."""
    _project(tmp_path, '''
        from src.calc import add

        def helper_not_a_test():
            assert add(2, 3) == 5
    ''')
    result = audit_claim(tmp_path, _claim(), max_mutants=6, workers=3)
    assert result.verdict is Verdict.INCONCLUSIVE
    assert result.mutants_killed == 0
    assert any("NO_TESTS_COLLECTED" in r for r in result.baseline["not_green_because"])


def test_a_missing_verifies_path_is_inconclusive(tmp_path):
    _project(tmp_path, '''
        from src.calc import add

        def test_add():
            assert add(2, 3) == 5
    ''')
    claim = Claim(id="c", check=["python3", "-m", "pytest", "-q"], verifies="src/absent.py")
    result = audit_claim(tmp_path, claim, max_mutants=4, workers=2)
    assert result.verdict is Verdict.INCONCLUSIVE
    assert "does not exist" in result.reason


def test_a_module_with_nothing_to_mutate_is_inconclusive(tmp_path):
    """No mutant generated is an unknown, never a pass."""
    _project(tmp_path, '''
        from src.calc import CONSTANT

        def test_constant():
            assert CONSTANT is not None
    ''', module="CONSTANT = object()\n")
    result = audit_claim(tmp_path, _claim(), max_mutants=4, workers=2)
    assert result.verdict is Verdict.INCONCLUSIVE
    assert "no behaviour-changing mutation" in result.reason


def test_the_audit_leaves_the_audited_tree_untouched(tmp_path):
    """Mutations happen in a sandbox. If this fails the tool corrupts its subject."""
    _project(tmp_path, '''
        from src.calc import add

        def test_add():
            assert add(2, 3) == 5
    ''')
    before = (tmp_path / "src" / "calc.py").read_text()
    audit_claim(tmp_path, _claim(), max_mutants=4, workers=2)
    assert (tmp_path / "src" / "calc.py").read_text() == before
