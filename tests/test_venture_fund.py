"""
The fund's own accounting: fees, reserves, pro-rata, exits through the waterfall,
TVPI/DPI, the end-of-fund wind-down, and the report that names the fund-returner.

Startups here are hand-built (tests/venture_helpers.py) so every number is known.
"""

import pytest

from config.venture_settings import (
    FEE_PER_PERIOD, FUND_SIZE, INVESTABLE_CAPITAL, LIFETIME_FEES, MAX_COMPANY_PCT,
    MAX_PERIODS, MIN_CHECK, SECONDARY_DISCOUNT,
)
from models.startup import ScheduledEvent
from tests.venture_helpers import advance_to, crafted_startup, fund_offering, seed_round

A_ROUND = ScheduledEvent(4, "round", "Series A", 20_000_000, 5_000_000)


def _seed_backed(check=500_000, reserve=500_000, ending=None, rounds=(A_ROUND,)):
    """A fund holding `check` of a seed at $8M pre / $10M post (5% for $500k)."""
    ending = ending or ScheduledEvent(9, "exit", exit_value=100_000_000)
    startup = crafted_startup([seed_round(), *rounds, ending])
    fund = fund_offering(startup)
    ok, message = fund.commit_to_deal(startup.id, check, reserve)
    assert ok, message
    fund.advance()
    return fund, fund.positions[startup.id]


# --- fees -------------------------------------------------------------------

def test_fees_for_the_whole_life_are_set_aside_before_anything_is_invested():
    fund = fund_offering()
    assert LIFETIME_FEES == pytest.approx(2_000_000)          # 2% x $10M x 10 years
    assert fund.available() == pytest.approx(INVESTABLE_CAPITAL) == pytest.approx(8_000_000)


def test_a_fund_that_invests_nothing_still_pays_every_fee_and_returns_nothing():
    fund = fund_offering()
    advance_to(fund, MAX_PERIODS + 1)
    assert fund.is_over
    assert fund.fees_paid == pytest.approx(LIFETIME_FEES)
    assert fund.paid_in() == pytest.approx(LIFETIME_FEES)
    assert fund.tvpi() == 0
    assert fund.net_irr() == -1.0


def test_each_half_year_calls_one_period_of_fees():
    fund = fund_offering()
    fund.advance()
    assert fund.fees_paid == pytest.approx(FEE_PER_PERIOD) == pytest.approx(100_000)
    assert fund.history[-1]["cumulative_net_cash_flow"] == pytest.approx(-100_000)


# --- committing to deals ----------------------------------------------------

def test_a_commitment_reserves_its_follow_on_money_too():
    startup = crafted_startup([seed_round(), ScheduledEvent(9, "shutdown")])
    fund = fund_offering(startup)
    fund.commit_to_deal(startup.id, 500_000, 700_000)
    assert fund.available() == pytest.approx(INVESTABLE_CAPITAL - 1_200_000)

    fund.advance()
    pos = fund.positions[startup.id]
    assert pos.invested == pytest.approx(500_000)
    assert fund.reserved() == pytest.approx(700_000)
    assert fund.available() == pytest.approx(INVESTABLE_CAPITAL - 1_200_000)


def test_recommitting_replaces_the_earlier_numbers_and_zero_withdraws():
    startup = crafted_startup([seed_round(), ScheduledEvent(9, "shutdown")])
    fund = fund_offering(startup)
    fund.commit_to_deal(startup.id, 500_000, 500_000)
    fund.commit_to_deal(startup.id, 200_000, 0)
    assert fund.pending() == pytest.approx(200_000)
    ok, _ = fund.commit_to_deal(startup.id, 0, 0)
    assert ok and fund.pending() == 0

    fund.advance()
    assert startup.id not in fund.positions
    assert fund.passed == [startup]


@pytest.mark.parametrize("check,reserve,reason", [
    (MIN_CHECK - 1, 0, "Minimum"),
    (2_000_001, 0, "only raising"),                  # the round is $2M
    (1_500_000, FUND_SIZE * MAX_COMPANY_PCT, "capped"),
])
def test_commitments_outside_the_rules_are_refused(check, reserve, reason):
    startup = crafted_startup([seed_round(), ScheduledEvent(9, "shutdown")])
    fund = fund_offering(startup)
    ok, message = fund.commit_to_deal(startup.id, check, reserve)
    assert not ok
    assert reason in message
    assert fund.pending() == 0


def test_reserves_can_block_new_deals():
    deals = [crafted_startup([seed_round(), ScheduledEvent(9, "shutdown")], startup_id=i,
                             name=f"Co{i}") for i in range(5)]
    fund = fund_offering(*deals)
    for deal in deals[:4]:
        assert fund.commit_to_deal(deal.id, 1_000_000, 1_000_000)[0]
    # $8M is now promised: $4M in cheques and $4M in reserves
    ok, message = fund.commit_to_deal(deals[4].id, MIN_CHECK, 0)
    assert not ok and "free" in message


# --- pro-rata and dilution --------------------------------------------------

def test_taking_pro_rata_keeps_ownership_and_draws_on_the_reserve():
    fund, pos = _seed_backed()
    assert pos.ownership() == pytest.approx(0.05)
    advance_to(fund, 4)                              # the A is now raising
    assert pos.pro_rata() == pytest.approx(250_000)  # 5% of a $5M round

    ok, message = fund.decide_follow_on(pos.startup.id, pos.pro_rata())
    assert ok, message
    fund.advance()

    assert pos.ownership() == pytest.approx(0.05)
    assert pos.invested == pytest.approx(750_000)
    assert pos.reserve == pytest.approx(250_000)


def test_passing_on_a_round_dilutes_by_pre_over_post():
    fund, pos = _seed_backed()
    advance_to(fund, 4)
    fund.advance()                                   # no answer counts as passing
    assert pos.ownership() == pytest.approx(0.05 * 20 / 25)
    assert pos.invested == pytest.approx(500_000)


def test_follow_on_cannot_exceed_pro_rata():
    fund, pos = _seed_backed()
    advance_to(fund, 4)
    ok, _ = fund.decide_follow_on(pos.startup.id, pos.pro_rata() + 1_000)
    assert not ok
    assert pos.follow_on is None


def test_follow_on_beyond_the_reserve_needs_free_capital():
    fund, pos = _seed_backed(reserve=100_000)
    advance_to(fund, 4)
    before = fund.available()
    ok, _ = fund.decide_follow_on(pos.startup.id, 250_000)
    assert ok
    # The reserve covers $100k; the other $150k comes out of free capital
    assert fund.available() == pytest.approx(before - 150_000)


def test_a_down_round_marks_the_stake_down():
    down = ScheduledEvent(4, "round", "Series A", 5_000_000, 2_000_000)
    fund, pos = _seed_backed(rounds=(down,))
    assert pos.mark() == pytest.approx(500_000)
    advance_to(fund, 5)
    # $5M pre over 12.5M shares = $0.40 a share; 625k shares -> $250k
    assert pos.mark() == pytest.approx(250_000)


# --- exits ------------------------------------------------------------------

def test_an_exit_pays_the_fund_its_waterfall_share_and_releases_the_reserve():
    fund, pos = _seed_backed()
    advance_to(fund, 4)
    fund.advance()                                   # pass on the A: 4% left
    advance_to(fund, 9)                              # $100M exit, everyone converts

    assert pos.startup.status == "exited"
    assert pos.proceeds == pytest.approx(4_000_000)
    assert fund.distributions == pytest.approx(4_000_000)
    assert pos.reserve == 0 and fund.reserved() == 0
    record = fund.exits[-1]
    assert record.fund_proceeds == pytest.approx(4_000_000)
    assert record.fund_rows == [{"series": "Seed", "converted": True,
                                 "payout": pytest.approx(4_000_000)}]


def test_a_small_sale_returns_preferred_money_first():
    # Sold for $6M after raising $7M: preferences ($2M seed, $5M A) share it
    # pro-rata, 6/7 each. The fund's 25% of the seed series gets $2M x 6/7 x 0.25.
    sale = ScheduledEvent(9, "exit", exit_value=6_000_000)
    fund, pos = _seed_backed(ending=sale)
    advance_to(fund, 9)
    assert pos.proceeds == pytest.approx(2_000_000 * 6 / 7 * 0.25)
    assert fund.exits[-1].waterfall.common_payout == 0


def test_a_shutdown_recovers_a_share_of_preferred_raised():
    shutdown = ScheduledEvent(9, "shutdown", recovery=0.1)
    fund, pos = _seed_backed(ending=shutdown)
    advance_to(fund, 9)
    # $7M preferred raised, 10% recovered = $700k, of which the seed's share is 2/7
    # and the fund owns 25% of the seed series
    assert pos.startup.status == "shut down"
    assert pos.proceeds == pytest.approx(700_000 * 2 / 7 * 0.25)


# --- fund metrics -----------------------------------------------------------

def test_tvpi_dpi_and_carry_after_a_big_exit():
    fund, pos = _seed_backed()
    advance_to(fund, 4)
    fund.advance()
    advance_to(fund, 9)
    # Paid in by period 9 (8 advances): $500k invested + 8 x $100k fees = $1.3M.
    # $4M back: $2.7M profit, 20% carry = $540k, LPs net $3.46M.
    assert fund.paid_in() == pytest.approx(1_300_000)
    assert fund.carry_realised() == pytest.approx(540_000)
    assert fund.dpi() == pytest.approx(3_460_000 / 1_300_000)
    assert fund.tvpi() == pytest.approx(fund.dpi())        # nothing left unrealised
    assert fund.gross_moic() == pytest.approx(8.0)
    assert fund.net_irr() > 0


def test_the_j_curve_dips_before_it_recovers():
    fund, pos = _seed_backed()
    advance_to(fund, MAX_PERIODS + 1)
    curve = [h["cumulative_net_cash_flow"] for h in fund.history]
    trough = min(curve)
    assert curve[0] == 0 and trough < 0
    assert curve.index(trough) < len(curve) - 1
    assert curve[-1] > trough


def test_unsold_companies_go_to_a_secondary_buyer_at_the_end():
    late = ScheduledEvent(MAX_PERIODS + 5, "exit", exit_value=1e9)
    fund, pos = _seed_backed(ending=late)
    advance_to(fund, MAX_PERIODS)
    mark = pos.mark()
    fund.advance()
    assert fund.is_over
    assert pos.startup.status == "sold"
    assert pos.proceeds == pytest.approx(mark * (1 - SECONDARY_DISCOUNT))
    assert fund.nav() == 0


def test_a_finished_fund_takes_no_more_actions():
    fund, pos = _seed_backed()
    advance_to(fund, MAX_PERIODS + 1)
    assert fund.advance() == []
    assert fund.commit_to_deal(1, MIN_CHECK, 0)[0] is False


# --- end-of-fund report -----------------------------------------------------

def test_the_report_names_the_deal_that_returned_the_fund():
    # $1M for 10% of a seed, then a $300M exit after the A: 8% of $300M = $24M
    winner = crafted_startup([seed_round(), A_ROUND,
                              ScheduledEvent(9, "exit", exit_value=300_000_000)],
                             startup_id=1, name="Rocketco")
    dud = crafted_startup([seed_round(), ScheduledEvent(5, "shutdown", recovery=0.0)],
                          startup_id=2, name="Dudco")
    fund = fund_offering(winner, dud)
    fund.commit_to_deal(1, 1_000_000, 0)
    fund.commit_to_deal(2, 1_000_000, 0)
    advance_to(fund, MAX_PERIODS + 1)

    report = fund.final_report()
    assert report["fund_returners"] == ["Rocketco"]
    assert "Rocketco returned the fund" in report["headline"]
    assert report["deals"][0]["name"] == "Rocketco"
    assert report["deals"][0]["share_of_value"] == pytest.approx(1.0)
    assert report["losers"] == 1


def test_without_a_fund_returner_the_report_says_so_and_names_the_best_deal():
    fund, pos = _seed_backed()                       # $4M back: 0.4x the fund
    advance_to(fund, MAX_PERIODS + 1)
    report = fund.final_report()
    assert report["fund_returners"] == []
    assert "No single deal returned the fund" in report["headline"]
    assert "Testco" in report["headline"]
