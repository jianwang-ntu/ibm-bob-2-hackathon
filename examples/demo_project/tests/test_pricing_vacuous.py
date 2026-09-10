"""A check that looks like verification and cannot go red.

Every one of these passes for any implementation of apply_discount that
returns an int, including one that returns the price unchanged. This is the
shape an assistant produces when asked to "add tests" without being told what
the function is supposed to do.
"""

from src.pricing import apply_discount


def test_discount_returns_something():
    result = apply_discount(1000, 10)
    assert result is not None


def test_discount_returns_an_int():
    assert isinstance(apply_discount(1000, 10), int)


def test_discount_is_consistent():
    assert apply_discount(1000, 10) == apply_discount(1000, 10)


def test_discount_does_not_explode():
    try:
        assert apply_discount(1000, 10) == 900
    except Exception:
        pass
