"""Static vacuity patterns, each paired with a control that must NOT fire.

A detector tested only on the thing it is meant to catch cannot be shown to
discriminate -- it would score the same if it flagged everything.
"""

from vacuity_auditor.static_scan import scan_source

HONEST = '''
def test_addition_is_right():
    assert 2 + 2 == 4

def test_rejects_bad_input():
    import pytest
    with pytest.raises(ValueError):
        int("not a number")
'''


def _patterns(source):
    return {f.pattern for f in scan_source(source, "tests/t.py")}


def test_honest_tests_produce_no_findings():
    """The control for every case below. If this fires, the scanner flags everything."""
    assert _patterns(HONEST) == set()


def test_detects_a_test_with_no_assertion():
    src = "def test_it():\n    value = 1 + 1\n    print(value)\n"
    assert "no_assertion" in _patterns(src)


def test_detects_an_empty_body():
    src = "def test_it():\n    pass\n"
    assert "empty_body" in _patterns(src)


def test_detects_a_constant_assertion():
    src = "def test_it():\n    assert True\n"
    assert "constant_assertion" in _patterns(src)


def test_detects_a_self_comparison():
    src = "def test_it():\n    x = compute()\n    assert x == x\n"
    assert "self_comparison" in _patterns(src)


def test_detects_a_presence_only_none_check():
    src = "def test_it():\n    assert compute() is not None\n"
    assert "presence_only" in _patterns(src)


def test_detects_a_presence_only_isinstance_check():
    src = "def test_it():\n    assert isinstance(compute(), int)\n"
    assert "presence_only" in _patterns(src)


def test_detects_a_swallowed_assertion():
    src = ("def test_it():\n    try:\n        assert compute() == 4\n"
           "    except Exception:\n        pass\n")
    assert "swallowed_assertion" in _patterns(src)


def test_detects_an_unconditional_skip():
    src = "import pytest\n\ndef test_it():\n    pytest.skip('later')\n    assert compute() == 4\n"
    assert "unconditional_skip" in _patterns(src)


def test_a_guarded_skip_is_not_flagged():
    """A skip behind a condition is legitimate; flagging it would be noise."""
    src = ("import pytest, sys\n\ndef test_it():\n"
           "    if sys.platform == 'win32':\n        pytest.skip('posix only')\n"
           "    assert compute() == 4\n")
    assert "unconditional_skip" not in _patterns(src)


def test_a_real_value_assertion_is_not_presence_only():
    src = "def test_it():\n    assert compute() == 4\n"
    assert "presence_only" not in _patterns(src)


def test_non_test_functions_are_ignored():
    """Helper code is not a check and must not be scored as one."""
    src = "def helper():\n    pass\n\ndef build_thing():\n    return 1\n"
    assert _patterns(src) == set()


def test_findings_carry_a_location_and_a_name():
    src = "def test_named():\n    assert True\n"
    findings = scan_source(src, "tests/t.py")
    assert findings[0].test_name == "test_named"
    assert findings[0].relative_path == "tests/t.py"
    assert findings[0].lineno == 2


def test_a_file_that_does_not_parse_is_skipped_not_crashed(tmp_path):
    from pathlib import Path
    from vacuity_auditor.static_scan import scan_path
    bad = tmp_path / "tests"
    bad.mkdir()
    (bad / "test_broken.py").write_text("def test_x(:\n", encoding="utf-8")
    assert scan_path(Path(bad), Path(tmp_path)) == []
