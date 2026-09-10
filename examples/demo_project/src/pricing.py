"""A tiny module with one real behaviour, used to demonstrate the auditor."""


def apply_discount(price_cents: int, percent: int) -> int:
    """Return the price after a percentage discount, floored at zero.

    Rounds half up, so a 33% discount on 1000 gives 670, not 669.
    """
    if percent < 0 or percent > 100:
        raise ValueError("percent must be between 0 and 100")
    reduction = (price_cents * percent + 50) // 100
    result = price_cents - reduction
    return result if result > 0 else 0
