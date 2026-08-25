"""
Bug #6: opening a short inflated net worth by the full notional.

`net_worth` was `cash + longs + short_pnl`. The short sale proceeds are already in
`cash` and the borrowed shares were never carried as a liability, so shorting
$1,873 of stock instantly "earned" $1,845. That fed straight into total return,
Sharpe, alpha, max drawdown, the final rating and the dynamic-difficulty skill rating.

Correct: net worth = cash + longs + options - cost to buy back the borrowed shares.
"""

from config.settings import SHORT_LOCATE_FEE, SHORT_MARGIN_REQUIREMENT, TRANSACTION_FEE


def test_opening_a_short_does_not_create_value(market, player, company):
    """Net worth after shorting should drop by the fees, not jump by the notional."""
    nw_before = player.net_worth(market)

    assert player.short(market, company, 50) is True

    nw_after = player.net_worth(market)
    notional = company.price * 50
    expected_fees = notional * (TRANSACTION_FEE + SHORT_LOCATE_FEE)

    # The whole bug was a jump of roughly +notional. Assert direction and magnitude.
    assert nw_after < nw_before
    assert nw_before - nw_after == round(expected_fees, 6) or \
        abs((nw_before - nw_after) - expected_fees) < 1.0
    assert nw_after < nw_before + notional * 0.1


def test_short_gains_value_only_when_price_falls(market, player, company):
    player.short(market, company, 50)
    nw_at_open = player.net_worth(market)

    company.price = 80.0  # 20% fall on a 50 share short = +$1,000

    assert player.net_worth(market) - nw_at_open == 1000.0


def test_short_loses_value_when_price_rises(market, player, company):
    player.short(market, company, 50)
    nw_at_open = player.net_worth(market)

    company.price = 120.0

    assert player.net_worth(market) - nw_at_open == -1000.0


def test_round_trip_short_is_flat_when_price_does_not_move(market, player, company):
    """Short then immediately cover: you should be down fees only, never up."""
    nw_before = player.net_worth(market)

    player.short(market, company, 50)
    player.cover(market, company, 50)

    nw_after = player.net_worth(market)
    assert nw_after < nw_before
    assert nw_before - nw_after < company.price * 50 * 0.05  # fees only, not notional


def test_margin_equity_carries_the_short_liability(market, player, company):
    """Margin equity must use the same accounting as net worth."""
    equity_before = player.margin_equity(market)

    player.short(market, company, 50)

    assert player.margin_equity(market) < equity_before
    # equity and net worth agree while no options are held
    assert player.margin_equity(market) == player.net_worth(market)


def test_available_margin_shrinks_after_shorting(market, player, company):
    before = player.available_margin(market)

    player.short(market, company, 50)

    after = player.available_margin(market)
    assert after < before
    # The reserved amount is the margin requirement on the position, plus fees.
    assert after <= before - company.price * 50 * SHORT_MARGIN_REQUIREMENT + 1.0


def test_shorting_cannot_be_used_to_grow_reported_return(market, player, company):
    """The headline number a player sees must not move on opening a position."""
    return_before = player.total_return_pct(market)

    player.short(market, company, 50)

    assert player.total_return_pct(market) < return_before


def test_long_position_value_still_counts(market, player, company):
    """Guard against over-correcting: longs must still be additive."""
    nw_before = player.net_worth(market)
    player.buy(market, company, 10)
    company.price = 150.0

    # 10 shares bought at ~100 now worth 150 => up ~500 less fees
    assert player.net_worth(market) > nw_before + 400
