"""Exact allocation properties, independent of HTTP and database behavior."""

from decimal import Decimal

import pytest

from ledger.money import format_money, parse_money, split_equal


@pytest.mark.parametrize("value", ["1200", "1200.00", Decimal("1200.00"), 1200])
def test_numeric_representations_have_same_minor_units(value):
    assert parse_money(value) == 120000


@pytest.mark.parametrize(
    "value", [True, False, "NaN", "Infinity", "-1", "0", "1.001", "10000000.01", None, [], {}]
)
def test_invalid_money_is_rejected(value):
    with pytest.raises(ValueError):
        parse_money(value)


def test_rounding_is_deterministic_conserving_and_not_membership_order_dependent():
    assert split_equal(10000, [3, 1, 2]) == {1: 3334, 2: 3333, 3: 3333}
    assert split_equal(1, [3, 2, 1]) == {1: 1, 2: 0, 3: 0}
    assert format_money(1) == "0.01"


@pytest.mark.parametrize("ids", [[], [1, 1]])
def test_invalid_participants_rejected(ids):
    with pytest.raises(ValueError):
        split_equal(100, ids)


def test_allocation_properties_over_many_amounts_and_group_sizes():
    for count in range(1, 20):
        for amount in [1, 2, 7, 99, 10000, 1000000000]:
            shares = split_equal(amount, list(range(count)))
            assert sum(shares.values()) == amount
            assert max(shares.values()) - min(shares.values()) <= 1


@pytest.mark.parametrize(
    "value", ["1e2", "1_00", "10.000", " 10 ", "+1.00", "-0.00", Decimal("-0.00"), "0e999", "0.000"]
)
def test_ordinary_decimal_contract_rejects_ambiguous_representations(value):
    with pytest.raises(ValueError):
        parse_money(value, allow_zero=True)


def test_allow_zero_is_explicit_for_custom_shares_only():
    assert parse_money("0.00", allow_zero=True) == 0
    with pytest.raises(ValueError):
        parse_money("0.00")
