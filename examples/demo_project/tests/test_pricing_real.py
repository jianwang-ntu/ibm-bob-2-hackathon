"""A check that reads the behaviour it claims to read."""

from src.pricing import apply_discount


def test_ten_percent_off_a_round_price():
    assert apply_discount(1000, 10) == 900


def test_rounds_half_up():
    assert apply_discount(1000, 33) == 670


def test_full_discount_is_free():
    assert apply_discount(1000, 100) == 0


def test_rejects_an_impossible_percentage():
    try:
        apply_discount(1000, 101)
    except ValueError:
        return
    raise AssertionError("expected ValueError")
