"""
Venture money maths: dilution, pro-rata, the 1x non-participating waterfall, carry
and IRR. Every expected number here is worked out by hand in the comments, so a
failure says which rule broke rather than just that a number moved.
"""

import random

import pytest

from models.startup import ScheduledEvent
from utils.venture_math import (
    PreferredClass, carried_interest, irr, liquidation_waterfall, ownership_after_round,
    price_per_share, pro_rata_amount,
)
from tests.venture_helpers import crafted_startup, seed_round


# --- dilution ---------------------------------------------------------------

def test_a_round_dilutes_existing_holders_by_pre_over_post():
    # 10% before a $2M raise at $8M pre ($10M post): 10% x 8/10 = 8%
    assert ownership_after_round(0.10, 2_000_000, 10_000_000) == pytest.approx(0.08)


def test_investing_exactly_pro_rata_keeps_ownership_unchanged():
    pro_rata = pro_rata_amount(0.10, 2_000_000)
    assert pro_rata == pytest.approx(200_000)
    assert ownership_after_round(0.10, 2_000_000, 10_000_000, pro_rata) == pytest.approx(0.10)


def test_cap_table_rounds_issue_shares_at_the_round_price():
    a_round = ScheduledEvent(4, "round", "Series A", 20_000_000, 5_000_000)
    startup = crafted_startup([seed_round(), a_round, ScheduledEvent(9, "exit", exit_value=1)])

    seed = startup.close_round()
    # $8M pre over 10M common shares = $0.80; $2M buys 2.5M shares
    assert seed.price == pytest.approx(0.80)
    assert seed.shares == pytest.approx(2_500_000)

    startup.open_round = a_round
    series_a = startup.close_round()
    # $20M pre over 12.5M shares = $1.60; $5M buys 3.125M shares
    assert series_a.price == pytest.approx(1.60)
    assert series_a.shares == pytest.approx(3_125_000)

    # A $500k seed cheque held 5%; after the A it is 5% x 20/25 = 4%
    held = 500_000 / seed.price
    assert held / startup.shares_outstanding() == pytest.approx(
        ownership_after_round(0.05, 5_000_000, 25_000_000))
    assert held / startup.shares_outstanding() == pytest.approx(0.04)


def test_price_per_share_is_pre_money_over_shares():
    assert price_per_share(8_000_000, 10_000_000) == pytest.approx(0.8)


# --- liquidation waterfall --------------------------------------------------

COMMON = 10_000_000
SEED = PreferredClass("Seed", 2_500_000, 2_000_000)        # pref $0.80 a share
SERIES_A = PreferredClass("Series A", 3_125_000, 5_000_000)  # pref $1.60 a share


def test_exit_below_total_preferences_pays_them_pro_rata_and_common_nothing():
    # $3.5M against $7M of preferences: each series gets half its money back
    result = liquidation_waterfall(3_500_000, COMMON, [SEED, SERIES_A])
    assert result.payout_for("Seed") == pytest.approx(1_000_000)
    assert result.payout_for("Series A") == pytest.approx(2_500_000)
    assert result.common_payout == 0
    assert not any(r.converted for r in result.rows)


def test_middle_exit_seed_converts_while_series_a_keeps_its_preference():
    # $20M exit. If everyone converted: $20M / 15.625M shares = $1.28 a share,
    # which is below the A's $1.60 preference, so the A takes its $5M. The
    # remaining $15M is shared by 12.5M seed + common shares: $1.20 a share,
    # above the seed's $0.80 preference, so the seed converts for $3M.
    result = liquidation_waterfall(20_000_000, COMMON, [SEED, SERIES_A])
    rows = {r.name: r for r in result.rows}
    assert rows["Series A"].converted is False
    assert rows["Series A"].payout == pytest.approx(5_000_000)
    assert rows["Seed"].converted is True
    assert rows["Seed"].payout == pytest.approx(3_000_000)
    assert result.common_payout == pytest.approx(12_000_000)


def test_large_exit_everyone_converts_and_shares_pro_rata():
    # $156.25M over 15.625M shares = $10 a share for everyone
    result = liquidation_waterfall(156_250_000, COMMON, [SEED, SERIES_A])
    assert all(r.converted for r in result.rows)
    assert result.payout_for("Seed") == pytest.approx(25_000_000)
    assert result.payout_for("Series A") == pytest.approx(31_250_000)
    assert result.common_payout == pytest.approx(100_000_000)


def test_preferred_never_takes_both_preference_and_a_common_share():
    """Non-participating: a series is paid its preference OR its as-converted share."""
    rng = random.Random(3)
    for _ in range(500):
        classes = [PreferredClass(f"S{i}", rng.uniform(1e5, 5e6), rng.uniform(1e5, 2e7))
                   for i in range(rng.randint(1, 5))]
        result = liquidation_waterfall(rng.uniform(0, 3e8), COMMON, classes)
        for row in result.rows:
            if row.converted:
                assert row.payout == pytest.approx(row.shares * result.price_per_common_share)
                assert row.payout >= row.preference - 1e-6
            else:
                assert row.payout <= row.preference + 1e-6


def test_waterfall_pays_out_exactly_the_exit_value():
    rng = random.Random(5)
    for _ in range(500):
        classes = [PreferredClass(f"S{i}", rng.uniform(1e5, 5e6), rng.uniform(1e5, 2e7))
                   for i in range(rng.randint(1, 5))]
        exit_value = rng.uniform(0, 3e8)
        result = liquidation_waterfall(exit_value, COMMON, classes)
        paid = sum(r.payout for r in result.rows) + result.common_payout
        assert paid == pytest.approx(exit_value)


def test_no_series_holding_its_preference_would_rather_convert():
    """
    The waterfall's choices are an equilibrium. (A converted series already gets at
    least its preference - checked above - so only the holders need checking.)
    """
    rng = random.Random(7)
    for _ in range(300):
        classes = [PreferredClass(f"S{i}", rng.uniform(1e5, 5e6), rng.uniform(1e5, 2e7))
                   for i in range(rng.randint(2, 4))]
        exit_value = rng.uniform(1e6, 2e8)
        result = liquidation_waterfall(exit_value, COMMON, classes)
        for row in result.rows:
            if row.converted:
                continue
            others_pref = sum(r.preference for r in result.rows
                              if not r.converted and r is not row)
            as_common = COMMON + sum(r.shares for r in result.rows if r.converted) + row.shares
            if_converted = max(0.0, exit_value - others_pref) * row.shares / as_common
            assert row.payout >= if_converted - 1e-6


# --- carry, fees, IRR -------------------------------------------------------

def test_carry_is_twenty_percent_of_profit_above_paid_in_capital():
    # LPs paid in $10M; $15M came back: $5M profit, $1M carry
    assert carried_interest(15_000_000, 10_000_000) == pytest.approx(1_000_000)


def test_no_carry_until_lps_have_their_capital_back():
    assert carried_interest(9_999_999, 10_000_000) == 0
    assert carried_interest(10_000_000, 10_000_000) == 0


def test_irr_of_a_double_in_five_years():
    assert irr([-100, 0, 0, 0, 0, 200]) == pytest.approx(2 ** (1 / 5) - 1)


def test_irr_annualises_half_year_periods():
    # 10% in one half-year compounds to 21% a year
    assert irr([-100, 110], periods_per_year=2) == pytest.approx(0.21)


def test_irr_is_minus_100_percent_when_nothing_comes_back():
    assert irr([-100, -10, 0]) == -1.0


def test_irr_finds_a_loss_when_fees_are_still_being_called_at_the_end():
    # Money back before the end, then one more fee call: the flows change sign twice,
    # and the root that matters is the small negative one, not a spurious one.
    flows = [-100] * 10 + [60] * 9 + [-10]
    rate = irr(flows, periods_per_year=2)
    assert rate is not None
    assert -0.3 < rate < 0
