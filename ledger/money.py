"""Pure INR arithmetic: integer paise in, integer paise out; never binary floats."""

import re
from decimal import Decimal, InvalidOperation

MAX_MINOR = 1_000_000_000


def parse_money(value, *, allow_zero=False):
    """Accept decimal rupees without rounding; reject ambiguous or invalid input."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("Enter a positive amount with at most two decimal places.")
    if isinstance(value, str) and (
        len(value) > 64 or not re.fullmatch(r"\d+(?:\.\d{1,2})?", value, flags=re.ASCII)
    ):
        raise ValueError("Use ordinary decimal digits with at most two decimal places.")
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount.is_signed() or amount.as_tuple().exponent < -2:
            raise ValueError("Use a non-negative finite amount with at most two decimal places.")
        if (amount == 0 and not allow_zero) or amount > Decimal(MAX_MINOR) / 100:
            raise ValueError("Amount must be between 0.01 and 10,000,000.00 INR.")
        minor = amount * 100
        if minor != minor.to_integral_value():
            raise ValueError("Use at most two decimal places.")
        return int(minor)
    except InvalidOperation as exc:
        raise ValueError("Enter a valid decimal amount.") from exc


def format_money(minor):
    """Serialize paise as an exact two-place rupee string, including negatives."""
    return f"{Decimal(minor) / 100:.2f}"


def split_equal(amount_minor, participant_ids):
    """Assign remainder paise in ascending stable ID order and conserve the total."""
    ids = sorted(participant_ids)
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("At least one distinct participant is required.")
    if amount_minor <= 0 or amount_minor > MAX_MINOR:
        raise ValueError("Invalid expense amount.")
    base, remainder = divmod(amount_minor, len(ids))
    return {user_id: base + (index < remainder) for index, user_id in enumerate(ids)}
