"""Claim-spec parsing and report rendering."""

import json

import pytest

from vacuity_auditor import claims, report
from vacuity_auditor.verdicts import ClaimResult, Verdict

SPEC = '''
[[claim]]
id = "a"
check = "python -m pytest tests -q"
verifies = "src/mod.py"
lines = [10, 40]

[[claim]]
id = "b"
check = ["python", "-m", "pytest", "tests/test_b.py"]
verifies = "src/other.py"
'''


def _write(tmp_path, text, name="vacuity.toml"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_loads_a_valid_spec(tmp_path):
    """ACCEPT PATH for the parser."""
    parsed = claims.load(_write(tmp_path, SPEC))
    assert [c.id for c in parsed] == ["a", "b"]
    assert parsed[0].check == ["python", "-m", "pytest", "tests", "-q"]
    assert parsed[0].lines == (10, 40)
    assert parsed[1].lines is None


def test_loads_a_json_spec(tmp_path):
    payload = json.dumps({"claim": [{"id": "a", "check": "pytest", "verifies": "m.py"}]})
    parsed = claims.load(_write(tmp_path, payload, "spec.json"))
    assert parsed[0].check == ["pytest"]


def test_rejects_a_missing_required_field(tmp_path):
    with pytest.raises(claims.ClaimSpecError, match="verifies"):
        claims.load(_write(tmp_path, '[[claim]]\nid = "a"\ncheck = "pytest"\n'))


def test_rejects_an_empty_check(tmp_path):
    with pytest.raises(claims.ClaimSpecError, match="non-empty"):
        claims.load(_write(tmp_path, '[[claim]]\nid = "a"\ncheck = ""\nverifies = "m.py"\n'))


def test_rejects_duplicate_claim_ids(tmp_path):
    text = ('[[claim]]\nid = "a"\ncheck = "pytest"\nverifies = "m.py"\n'
            '[[claim]]\nid = "a"\ncheck = "pytest"\nverifies = "m.py"\n')
    with pytest.raises(claims.ClaimSpecError, match="duplicate"):
        claims.load(_write(tmp_path, text))


def test_rejects_a_backwards_line_range(tmp_path):
    text = '[[claim]]\nid = "a"\ncheck = "pytest"\nverifies = "m.py"\nlines = [40, 10]\n'
    with pytest.raises(claims.ClaimSpecError, match="start is after end"):
        claims.load(_write(tmp_path, text))


def test_rejects_a_spec_with_no_claims(tmp_path):
    with pytest.raises(claims.ClaimSpecError, match="no .* entries"):
        claims.load(_write(tmp_path, "title = 'nothing here'\n"))


def _r(verdict, killed=1, applied=1, did_not_run=0):
    return ClaimResult("c", verdict, "reason", mutants_applied=applied,
                       mutants_killed=killed, mutants_did_not_run=did_not_run)


def test_the_rendered_ratio_and_the_kill_rate_share_one_denominator():
    """Runs where the check never executed are excluded from both, or neither."""
    result = _r(Verdict.WEAK, killed=3, applied=10, did_not_run=2)
    assert result.evidential == 8
    assert result.kill_rate == 3 / 8
    assert "3/8" in report.render([result])
    assert "3/10" not in report.render([result])


def test_kill_rate_is_none_when_nothing_was_evidential():
    assert _r(Verdict.INCONCLUSIVE, killed=0, applied=4, did_not_run=4).kill_rate is None


def test_exit_code_is_zero_only_when_everything_discriminates():
    assert report.exit_code([_r(Verdict.DISCRIMINATING)]) == 0


def test_each_band_gets_its_own_exit_code():
    assert report.exit_code([_r(Verdict.VACUOUS, 0)]) == 1
    assert report.exit_code([_r(Verdict.INCONCLUSIVE, 0, 0)]) == 2
    assert report.exit_code([_r(Verdict.WEAK, 1, 2)]) == 3


def test_vacuous_outranks_the_softer_bands():
    mixed = [_r(Verdict.DISCRIMINATING), _r(Verdict.WEAK, 1, 2), _r(Verdict.VACUOUS, 0)]
    assert report.exit_code(mixed) == 1


def test_inconclusive_outranks_weak():
    """'We could not tell' must not be softened by a claim that did report."""
    assert report.exit_code([_r(Verdict.WEAK, 1, 2), _r(Verdict.INCONCLUSIVE, 0, 0)]) == 2


def test_render_names_the_verdict_and_the_ratio():
    text = report.render([_r(Verdict.WEAK, 3, 7)])
    assert "WEAK" in text and "3/7" in text


def test_summary_counts_every_band_including_weak():
    """A summary that cannot express one of its own verdicts hides that verdict."""
    payload = json.loads(report.to_json([_r(Verdict.WEAK, 1, 2)]))
    assert set(payload["summary"]) == {"total", "discriminating", "weak", "vacuous", "inconclusive"}
    assert sum(v for k, v in payload["summary"].items() if k != "total") == payload["summary"]["total"]


def test_json_report_carries_the_summary_and_kill_rate():
    payload = json.loads(report.to_json([_r(Verdict.WEAK, 3, 6), _r(Verdict.VACUOUS, 0, 4)]))
    assert payload["claims"][0]["mutants_did_not_run"] == 0
    assert payload["summary"] == {"total": 2, "discriminating": 0, "weak": 1,
                                  "vacuous": 1, "inconclusive": 0}
    assert payload["claims"][0]["kill_rate"] == 0.5
