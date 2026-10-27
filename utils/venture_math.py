"""
Money maths for venture fund mode: dilution, pro-rata, the liquidation waterfall,
carry and IRR.

Everything here is a pure function of its arguments, so each rule can be read and
tested on its own, away from the game loop.
"""

from dataclasses import dataclass
from typing import List, Optional, Sequence

from config.venture_settings import CARRY_RATE


# ---------------------------------------------------------------------------
# Priced rounds and dilution
# ---------------------------------------------------------------------------

def price_per_share(pre_money: float, shares_outstanding: float) -> float:
    """A priced round sets the price: pre-money valuation over the shares that exist."""
    return pre_money / shares_outstanding


def ownership_after_round(ownership: float, raise_amount: float, post_money: float,
                          participation: float = 0.0) -> float:
    """
    Ownership after a round in which `participation` of the `raise_amount` is ours.

    Everyone's existing stake shrinks by pre/post; new money buys participation/post.
    Investing exactly the pro-rata amount leaves ownership unchanged.
    """
    pre_money = post_money - raise_amount
    return ownership * pre_money / post_money + participation / post_money


def pro_rata_amount(ownership: float, raise_amount: float) -> float:
    """The cheque that keeps ownership constant through a round: ownership x round size."""
    return ownership * raise_amount


# ---------------------------------------------------------------------------
# Liquidation waterfall (1x non-participating preferred, all series pari passu)
# ---------------------------------------------------------------------------

@dataclass
class PreferredClass:
    name: str
    shares: float
    preference: float        # 1x: the amount that series invested


@dataclass
class WaterfallRow:
    name: str
    shares: float
    preference: float
    converted: bool          # True = took its share as common, False = took its preference
    payout: float


@dataclass
class WaterfallResult:
    exit_value: float
    rows: List[WaterfallRow]     # one per preferred class, in the order given
    common_shares: float
    common_payout: float
    price_per_common_share: float

    def payout_for(self, name: str) -> float:
        return next(r.payout for r in self.rows if r.name == name)


def liquidation_waterfall(exit_value: float, common_shares: float,
                          preferred: Sequence[PreferredClass]) -> WaterfallResult:
    """
    Split an exit between preferred series and common.

    Each preferred series may take its 1x preference OR convert to common and share
    pro-rata, whichever pays more - never both (non-participating). Preferences are
    pari passu: if the exit does not cover them all, they are paid pro-rata to size
    and common gets nothing.

    Converting only makes sense when the per-share price as common beats a series'
    preference per share. Series convert one at a time, cheapest preference-per-share
    first; each conversion lowers the common price a little, so the loop re-checks
    who still wants to convert until nobody else does.
    """
    exit_value = max(0.0, exit_value)
    converting = set()

    while True:
        holding_pref = [p for p in preferred if p.name not in converting]
        total_pref = sum(p.preference for p in holding_pref)

        if exit_value <= total_pref:
            # Not enough to cover the preferences: they share what there is.
            scale = exit_value / total_pref if total_pref > 0 else 0.0
            rows = [WaterfallRow(p.name, p.shares, p.preference, False, p.preference * scale)
                    for p in preferred]
            return WaterfallResult(exit_value, rows, common_shares, 0.0, 0.0)

        residual = exit_value - total_pref
        as_common = common_shares + sum(p.shares for p in preferred if p.name in converting)
        pps = residual / as_common if as_common > 0 else 0.0

        better_off_converting = [p for p in holding_pref if p.shares * pps > p.preference]
        if not better_off_converting:
            break
        converting.add(min(better_off_converting, key=lambda p: p.preference / p.shares).name)

    rows = []
    for p in preferred:
        if p.name in converting:
            rows.append(WaterfallRow(p.name, p.shares, p.preference, True, p.shares * pps))
        else:
            rows.append(WaterfallRow(p.name, p.shares, p.preference, False, p.preference))
    return WaterfallResult(exit_value, rows, common_shares, common_shares * pps, pps)


# ---------------------------------------------------------------------------
# Fund economics
# ---------------------------------------------------------------------------

def carried_interest(total_value: float, paid_in: float, carry_rate: float = CARRY_RATE) -> float:
    """
    The GP's carry on `total_value` returned (or held) for LPs.

    Whole-fund ("European") waterfall with no hurdle: LPs first get back every dollar
    they paid in - fees included - and only the profit above that is split
    80/20. Below 1x the GP earns no carry at all.
    """
    return carry_rate * max(0.0, total_value - paid_in)


def irr(cash_flows: Sequence[float], periods_per_year: int = 1) -> Optional[float]:
    """
    Annualised internal rate of return of evenly spaced cash flows (negative = paid
    in, positive = returned): the rate that makes their present value zero.
    Returns -1.0 when nothing ever comes back, None when no rate fits.

    A fund's flows change sign more than once (fees keep being called after exits
    start), so the present value can cross zero at more than one rate. The scan
    looks for every crossing and takes the one closest to zero - the economically
    meaningful one - then narrows it down by bisection.
    """
    if not any(cf < 0 for cf in cash_flows):
        return None
    if not any(cf > 0 for cf in cash_flows):
        return -1.0

    def npv(rate: float) -> float:
        return sum(cf / (1 + rate) ** t for t, cf in enumerate(cash_flows))

    grid = [-0.95 + i * 0.005 for i in range(int(2.95 / 0.005) + 1)]   # -95% .. +200% a period
    values = [npv(r) for r in grid]
    brackets = [(grid[i], grid[i + 1]) for i in range(len(grid) - 1)
                if values[i] == 0 or values[i] * values[i + 1] < 0]
    if not brackets:
        return None
    lo, hi = min(brackets, key=lambda b: min(abs(b[0]), abs(b[1])))

    f_lo = npv(lo)
    for _ in range(100):
        mid = (lo + hi) / 2
        f_mid = npv(mid)
        if f_lo * f_mid <= 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    period_rate = (lo + hi) / 2
    return (1 + period_rate) ** periods_per_year - 1
