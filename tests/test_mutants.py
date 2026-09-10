"""Mutation generation: valid, behaviour-changing, and scoped to the claim."""

import ast

from vacuity_auditor import mutants

MODULE = '''"""Module docstring -- behaviour-neutral."""


def clamp(value, low, high):
    """Function docstring -- also behaviour-neutral."""
    if value < low or value > high:
        raise ValueError("value out of range")
    return value + 0


def unrelated():
    return 42
'''


def _generate(source, tmp_path, **kwargs):
    path = tmp_path / "mod.py"
    path.write_text(source, encoding="utf-8")
    return mutants.generate(path, "mod.py", **kwargs)


def test_generates_mutants_at_all(tmp_path):
    """The accept path for the generator."""
    assert len(_generate(MODULE, tmp_path)) > 0


def test_every_mutant_is_valid_python(tmp_path):
    """An unparseable mutant is killed by any check, vacuous ones included."""
    for m in _generate(MODULE, tmp_path):
        ast.parse(m.source)


def test_every_mutant_actually_differs_from_the_original(tmp_path):
    normalised = ast.unparse(ast.parse(MODULE))
    for m in _generate(MODULE, tmp_path):
        assert m.source != normalised


def test_docstrings_are_never_mutated(tmp_path):
    """A docstring mutant survives every suite and would fake a VACUOUS verdict."""
    for m in _generate(MODULE, tmp_path):
        assert "Module docstring" not in m.source or "Module docstring -- behaviour-neutral." in m.source
        tree = ast.parse(m.source)
        assert ast.get_docstring(tree) == "Module docstring -- behaviour-neutral."


def test_exception_message_strings_are_never_mutated(tmp_path):
    """Equivalent mutants measure the operator, not the check."""
    for m in _generate(MODULE, tmp_path):
        assert "_vacuity_probe" not in m.source


def test_a_string_that_is_not_a_message_is_still_mutated(tmp_path):
    """Control for the exclusion above: it must not disable the operator wholesale."""
    source = 'def label():\n    return "plain"\n'
    ops = {m.operator for m in _generate(source, tmp_path)}
    assert "perturb_string" in ops


def test_region_limiting_excludes_other_functions(tmp_path):
    """A claim about one function must not be credited with a mutant elsewhere."""
    whole = _generate(MODULE, tmp_path)
    assert any(m.lineno == 12 for m in whole), "control: line 12 is mutable at all"
    scoped = _generate(MODULE, tmp_path, lines=(4, 9))
    assert scoped, "the claimed region must still yield mutants"
    assert all(4 <= m.lineno <= 9 for m in scoped)


def test_limit_caps_the_pool(tmp_path):
    assert len(_generate(MODULE, tmp_path, limit=2)) == 2


def test_comparison_flip_changes_the_operator(tmp_path):
    source = "def f(a, b):\n    return a == b\n"
    flipped = [m for m in _generate(source, tmp_path) if m.operator == "flip_comparison"]
    assert flipped and "a != b" in flipped[0].source


def test_blank_return_drops_the_computed_value(tmp_path):
    source = "def f(a):\n    return a * 2\n"
    blanked = [m for m in _generate(source, tmp_path) if m.operator == "blank_return"]
    assert blanked and "return None" in blanked[0].source


def test_mutant_keys_are_distinct(tmp_path):
    generated = _generate(MODULE, tmp_path)
    assert len({m.key() for m in generated}) == len(generated)
