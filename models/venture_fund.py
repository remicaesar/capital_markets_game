"""
The venture fund: the player's $10M, its positions, fees, carry and track record.

A turn is half a year. Each turn the fund sees a few new startups (during the
five-year investment period) and pro-rata offers from portfolio companies that are
raising. `advance()` then closes those rounds, charges the management fee, moves
the clock, and lets whatever the portfolio's futures hold for the new period
happen: new rounds, exits, shutdowns.
"""

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from config.venture_settings import (
    DEALS_PER_PERIOD, FEE_PER_PERIOD, FUND_SIZE, INVESTABLE_CAPITAL,
    INVESTMENT_PERIODS, MAX_COMPANY_PCT, MAX_PERIODS, MIN_CHECK, PERIODS_PER_YEAR,
    SECONDARY_DISCOUNT,
)
from models.startup import ScheduledEvent, Startup
from systems.startup_outcomes import generate_startup
from utils.venture_math import WaterfallResult, carried_interest, irr, pro_rata_amount

# Money that differs by less than this is the same money (float rounding)
CENT = 0.01


def period_label(period: int) -> str:
    """'Y3 H2' for period 6. Period 0 is the day the fund opens."""
    if period <= 0:
        return "Start"
    year = (period - 1) // PERIODS_PER_YEAR + 1
    half = (period - 1) % PERIODS_PER_YEAR + 1
    return f"Y{year} H{half}"


@dataclass
class DealCommitment:
    """A cheque promised to a deal in this period's flow; it lands when the round closes."""
    check: float
    reserve: float


@dataclass
class ExitRecord:
    period: int
    startup_id: int
    name: str
    kind: str                     # "exit" | "shutdown" | "secondary"
    exit_value: float
    fund_proceeds: float
    fund_invested: float
    waterfall: Optional[WaterfallResult] = None
    fund_rows: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Position:
    startup: Startup
    entry_period: int
    shares: Dict[str, float] = field(default_factory=dict)    # series name -> shares held
    invested: float = 0.0
    reserve: float = 0.0          # earmarked for this company's future rounds
    proceeds: float = 0.0
    # Amount chosen for the round the company is raising right now. None = no answer
    # yet, which counts as passing when the round closes.
    follow_on: Optional[float] = None

    @property
    def active(self) -> bool:
        return self.startup.status == "private"

    def ownership(self) -> float:
        held = sum(self.shares.values())
        return held / self.startup.shares_outstanding() if held else 0.0

    def mark(self) -> float:
        """Value at the last round's price - how VC funds mark unrealised holdings."""
        return sum(self.shares.values()) * self.startup.last_price() if self.active else 0.0

    def pro_rata(self) -> float:
        rnd = self.startup.open_round
        return pro_rata_amount(self.ownership(), rnd.raise_amount) if rnd else 0.0

    def earmarked(self) -> float:
        """Capital held back for this company: its reserve, or the follow-on if larger."""
        return max(self.reserve, self.follow_on or 0.0) if self.active else 0.0

    def multiple(self) -> float:
        value = self.proceeds + self.mark()
        return value / self.invested if self.invested else 0.0


class VentureFund:
    def __init__(self, rng: Optional[random.Random] = None):
        # The fund's own rng is used for one thing only: seeding each startup in the
        # deal flow. Choices never consume from it, so deal flow is choice-independent.
        self.rng = rng if rng is not None else random.Random()
        self.period = 1
        self.fees_paid = 0.0
        self.distributions = 0.0          # gross cash returned by exits, before carry
        self.positions: Dict[int, Position] = {}
        self.deal_flow: List[Startup] = []
        self.commitments: Dict[int, DealCommitment] = {}
        self.passed: List[Startup] = []
        self.exits: List[ExitRecord] = []
        self.log: List[Tuple[int, str]] = []
        self.history: List[Dict[str, float]] = []
        self._next_id = 1
        self._names = set()

        self._record_history(period=0)
        self._generate_deal_flow()

    # ------------------------------------------------------------------ status

    @property
    def is_over(self) -> bool:
        return self.period > MAX_PERIODS

    @property
    def in_investment_period(self) -> bool:
        return self.period <= INVESTMENT_PERIODS

    # ------------------------------------------------------------------ capital

    def invested(self) -> float:
        return sum(p.invested for p in self.positions.values())

    def paid_in(self) -> float:
        """Capital LPs have actually sent: every investment plus every fee."""
        return self.invested() + self.fees_paid

    def reserved(self) -> float:
        return sum(p.earmarked() for p in self.positions.values())

    def pending(self) -> float:
        return sum(c.check + c.reserve for c in self.commitments.values())

    def available(self) -> float:
        """Capital free for new deals: investable, minus invested, reserved and promised."""
        return INVESTABLE_CAPITAL - self.invested() - self.reserved() - self.pending()

    def nav(self) -> float:
        return sum(p.mark() for p in self.positions.values())

    # ------------------------------------------------------------------ metrics

    def carry_realised(self) -> float:
        return carried_interest(self.distributions, self.paid_in())

    def carry_accrued(self) -> float:
        """Carry the GP would earn if the fund ended at today's marks."""
        return carried_interest(self.distributions + self.nav(), self.paid_in())

    def net_distributions(self) -> float:
        return self.distributions - self.carry_realised()

    def tvpi(self) -> float:
        """Net total value to paid-in: (cash back + marks - carry) / cash in."""
        paid_in = self.paid_in()
        if not paid_in:
            return 0.0
        return (self.distributions + self.nav() - self.carry_accrued()) / paid_in

    def dpi(self) -> float:
        """Net distributions to paid-in: the part of TVPI that is real cash."""
        paid_in = self.paid_in()
        return self.net_distributions() / paid_in if paid_in else 0.0

    def gross_moic(self) -> float:
        """Multiple on invested capital, before fees and carry: the deals alone."""
        invested = self.invested()
        if not invested:
            return 0.0
        return (sum(p.proceeds for p in self.positions.values()) + self.nav()) / invested

    def lp_cash_flows(self) -> List[float]:
        """Per-period LP cash flows (paid in negative, returned positive), oldest first."""
        flows = []
        for prev, cur in zip(self.history, self.history[1:]):
            flows.append(cur["cumulative_net_cash_flow"] - prev["cumulative_net_cash_flow"])
        return flows

    def net_irr(self) -> Optional[float]:
        """LP net IRR, valuing what is still held at its marks (net of accrued carry)."""
        flows = self.lp_cash_flows()
        if not flows:
            return None
        flows[-1] += self.nav() - (self.carry_accrued() - self.carry_realised())
        return irr(flows, PERIODS_PER_YEAR)

    def _record_history(self, period: int):
        self.history.append({
            "period": period,
            "paid_in": self.paid_in(),
            "distributions": self.distributions,
            "net_distributions": self.net_distributions(),
            "nav": self.nav(),
            "cumulative_net_cash_flow": self.net_distributions() - self.paid_in(),
            "tvpi": self.tvpi(),
            "dpi": self.dpi(),
        })

    # ------------------------------------------------------------------ actions

    def _company_limit(self) -> float:
        return FUND_SIZE * MAX_COMPANY_PCT

    def commit_to_deal(self, deal_id: int, check: float, reserve: float) -> Tuple[bool, str]:
        """
        Back a startup in this period's deal flow with `check` now and `reserve` held
        back for its later rounds. A cheque of 0 withdraws an earlier commitment.
        Committing again to the same deal replaces the earlier numbers.
        """
        if self.is_over:
            return False, "The fund has ended - no further investments"
        if not self.in_investment_period:
            return False, "The investment period is over - the fund only makes follow-ons now"
        deal = next((d for d in self.deal_flow if d.id == deal_id), None)
        if deal is None:
            return False, "That startup is not in this period's deal flow"

        if check == 0:
            if self.commitments.pop(deal_id, None) is None:
                return False, f"No commitment to {deal.name} to withdraw"
            return True, f"Withdrew from {deal.name}"

        if check < MIN_CHECK:
            return False, f"Minimum cheque is ${MIN_CHECK:,.0f}"
        if reserve < 0:
            return False, "Reserve cannot be negative"
        if check > deal.open_round.raise_amount + CENT:
            return False, f"{deal.name} is only raising ${deal.open_round.raise_amount:,.0f}"
        if check + reserve > self._company_limit() + CENT:
            return False, (f"Cheque plus reserve is capped at ${self._company_limit():,.0f} "
                           f"per company ({MAX_COMPANY_PCT:.0%} of the fund)")

        previous = self.commitments.get(deal_id)
        free = self.available() + (previous.check + previous.reserve if previous else 0.0)
        if check + reserve > free + CENT:
            return False, f"Only ${free:,.0f} is free for new deals"

        self.commitments[deal_id] = DealCommitment(check, reserve)
        ownership = check / deal.open_round.post_money
        return True, (f"Committed ${check:,.0f} to {deal.name} for {ownership:.2%} "
                      f"(+${reserve:,.0f} reserved for follow-ons)")

    def decide_follow_on(self, startup_id: int, amount: float) -> Tuple[bool, str]:
        """Answer a portfolio company's open round: any amount from 0 (pass) up to pro-rata."""
        if self.is_over:
            return False, "The fund has ended - no further investments"
        pos = self.positions.get(startup_id)
        if pos is None or not pos.active or pos.startup.open_round is None:
            return False, "That company is not raising right now"
        pro_rata = pos.pro_rata()
        if amount < 0 or amount > pro_rata + CENT:
            return False, f"Follow-on must be between $0 and your pro-rata of ${pro_rata:,.0f}"
        amount = min(amount, pro_rata)

        exposure = pos.invested + max(pos.reserve, amount)
        if exposure > self._company_limit() + CENT:
            return False, (f"That would put ${exposure:,.0f} into {pos.startup.name}, over the "
                           f"${self._company_limit():,.0f} per-company cap")
        # Reserves cover the follow-on first; only the excess needs free capital
        extra = max(pos.reserve, amount) - pos.earmarked()
        if extra > self.available() + CENT:
            return False, (f"Reserve covers ${pos.reserve:,.0f}; the remaining "
                           f"${amount - pos.reserve:,.0f} is more than the ${self.available():,.0f} free")

        pos.follow_on = amount
        if amount == 0:
            return True, f"Passing on {pos.startup.name}'s {pos.startup.open_round.round_name}"
        return True, f"Following on with ${amount:,.0f} in {pos.startup.name}'s {pos.startup.open_round.round_name}"

    # ------------------------------------------------------------------ the turn

    def advance(self) -> List[str]:
        """Close this period's rounds, charge fees, and play out the next half-year."""
        if self.is_over:
            return []
        closing: List[str] = []
        happening: List[str] = []

        # The half-year ends: its rounds close and its fee is called
        ended = self.period
        self._close_entry_rounds(closing)
        self._close_follow_on_rounds(closing)
        self.fees_paid += FEE_PER_PERIOD
        self.period += 1

        # The next half-year begins: the portfolio's futures play out
        if self.is_over:
            self._wind_down(happening)
        else:
            for pos in list(self.positions.values()):
                if pos.active:
                    for event in pos.startup.events_at(self.period):
                        self._apply_event(pos, event, happening)
            self._generate_deal_flow()

        self._record_history(ended)
        self.log.extend((ended, e) for e in closing)
        self.log.extend((min(self.period, MAX_PERIODS), e) for e in happening)
        return closing + happening

    def _generate_deal_flow(self):
        self.deal_flow = []
        self.commitments = {}
        if self.is_over or not self.in_investment_period:
            return
        for _ in range(DEALS_PER_PERIOD):
            startup = generate_startup(self.rng.getrandbits(32), self._next_id,
                                       self.period, self._names)
            self._names.add(startup.name)
            self._next_id += 1
            self.deal_flow.append(startup)

    def _close_entry_rounds(self, events: List[str]):
        for deal in self.deal_flow:
            series = deal.close_round()
            commitment = self.commitments.get(deal.id)
            if commitment is None:
                self.passed.append(deal)
                continue
            pos = Position(deal, entry_period=self.period, reserve=commitment.reserve)
            pos.shares[series.name] = commitment.check / series.price
            pos.invested = commitment.check
            self.positions[deal.id] = pos
            events.append(f"✅ Invested ${commitment.check:,.0f} in {deal.name} ({series.name}) "
                          f"at ${series.post_money / 1e6:,.1f}M post - {pos.ownership():.2%} owned")

    def _close_follow_on_rounds(self, events: List[str]):
        for pos in self.positions.values():
            startup = pos.startup
            if not pos.active or startup.open_round is None:
                continue
            before = pos.ownership()
            amount = pos.follow_on or 0.0
            series = startup.close_round()
            if amount > 0:
                pos.shares[series.name] = amount / series.price
                pos.invested += amount
                pos.reserve = max(0.0, pos.reserve - amount)
                events.append(f"➕ Followed on ${amount:,.0f} in {startup.name} {series.name}: "
                              f"ownership {before:.2%} → {pos.ownership():.2%}")
            else:
                events.append(f"➖ Passed on {startup.name} {series.name}: diluted "
                              f"{before:.2%} → {pos.ownership():.2%}")
            pos.follow_on = None

    def _apply_event(self, pos: Position, event: ScheduledEvent, events: List[str]):
        startup = pos.startup
        if event.kind == "round":
            previous_post = startup.last_post_money()
            startup.open_round = event
            step = event.pre_money / previous_post if previous_post else 1.0
            label = "📉 DOWN ROUND" if step < 1 else "📈"
            events.append(f"{label} {startup.name} is raising a {event.round_name}: "
                          f"${event.raise_amount / 1e6:,.1f}M at ${event.pre_money / 1e6:,.1f}M pre "
                          f"({step:.2f}x the last post). Your pro-rata: ${pos.pro_rata():,.0f}")
            return

        result = startup.liquidate(event)
        fund_rows = []
        proceeds = 0.0
        for row in result.rows:
            held = pos.shares.get(row.name, 0.0)
            if held:
                payout = row.payout * held / row.shares
                proceeds += payout
                fund_rows.append({"series": row.name, "converted": row.converted, "payout": payout})
        self._book_proceeds(pos, proceeds)
        self.exits.append(ExitRecord(self.period, startup.id, startup.name, event.kind,
                                     result.exit_value, proceeds, pos.invested, result, fund_rows))
        if event.kind == "shutdown":
            events.append(f"💀 {startup.name} shut down. Assets sold for ${result.exit_value / 1e6:,.2f}M; "
                          f"preferred got it first. You recovered ${proceeds:,.0f} of ${pos.invested:,.0f}")
        else:
            events.append(f"💰 {startup.name} exited for ${result.exit_value / 1e6:,.1f}M. You received "
                          f"${proceeds:,.0f} on ${pos.invested:,.0f} ({proceeds / pos.invested:.1f}x)")

    def _wind_down(self, events: List[str]):
        """End of fund life: sell what is left to a secondary buyer below its mark."""
        for pos in self.positions.values():
            if not pos.active:
                continue
            proceeds = pos.mark() * (1 - SECONDARY_DISCOUNT)
            pos.startup.status = "sold"
            self._book_proceeds(pos, proceeds)
            self.exits.append(ExitRecord(MAX_PERIODS, pos.startup.id, pos.startup.name, "secondary",
                                         proceeds, proceeds, pos.invested))
            events.append(f"🔁 Fund term over: sold {pos.startup.name} to a secondary buyer for "
                          f"${proceeds:,.0f} ({SECONDARY_DISCOUNT:.0%} below its last mark)")

    def _book_proceeds(self, pos: Position, proceeds: float):
        pos.proceeds += proceeds
        pos.reserve = 0.0
        pos.follow_on = None
        self.distributions += proceeds

    # ------------------------------------------------------------------ report

    def final_report(self) -> Dict[str, Any]:
        """The end-of-fund letter to LPs: the numbers, and which deals made them."""
        positions = sorted(self.positions.values(), key=lambda p: p.proceeds + p.mark(), reverse=True)
        total_value = self.distributions + self.nav()
        returners = [p for p in positions if p.proceeds + p.mark() >= FUND_SIZE]

        if len(returners) == 1:
            headline = f"{returners[0].startup.name} returned the fund on its own"
        elif returners:
            headline = f"{', '.join(p.startup.name for p in returners)} each returned the fund"
        elif positions and total_value > 0:
            best = positions[0]
            best_value = best.proceeds + best.mark()
            headline = (f"No single deal returned the fund. Your best, {best.startup.name}, "
                        f"returned {best_value / FUND_SIZE:.2f}x the fund - "
                        f"{best_value / total_value:.0%} of everything you got back")
        else:
            headline = "No deal returned any capital"

        tvpi = self.tvpi()
        if tvpi >= 3:
            rating = "🦄 TOP-DECILE FUND. LPs will be lining up for Fund II."
        elif tvpi >= 2:
            rating = "🏆 TOP-QUARTILE FUND. A real track record to raise Fund II on."
        elif tvpi >= 1.5:
            rating = "👍 DECENT FUND. Positive - though over ten years an index fund may have done as well."
        elif tvpi >= 1:
            rating = "🙂 RETURNED CAPITAL. After ten years, LPs got their money back."
        else:
            rating = "😢 LOST LP MONEY. Plenty of real funds do - the power law is unforgiving."

        deals = []
        for p in positions:
            value = p.proceeds + p.mark()
            deals.append({
                "id": p.startup.id,
                "name": p.startup.name,
                "invested": p.invested,
                "value": value,
                "multiple": value / p.invested if p.invested else 0.0,
                "outcome": p.startup.status,
                "share_of_value": value / total_value if total_value else 0.0,
                "returned_fund": value >= FUND_SIZE,
            })

        return {
            "headline": headline,
            "rating": rating,
            "fund_returners": [p.startup.name for p in returners],
            "deal_count": len(positions),
            "losers": sum(1 for d in deals if d["multiple"] < 1),
            "paid_in": self.paid_in(),
            "invested": self.invested(),
            "fees_paid": self.fees_paid,
            "gross_proceeds": self.distributions,
            "carry_paid": self.carry_accrued(),
            "net_to_lps": self.distributions + self.nav() - self.carry_accrued(),
            "gross_moic": self.gross_moic(),
            "tvpi": tvpi,
            "dpi": self.dpi(),
            "net_irr": self.net_irr(),
            "deals": deals,
        }
