"""
A fictional startup: its cap table, the rounds it has raised, and the future it
was born with.

A startup's whole life - every later round, and how it ends - is generated the
moment it pitches (see systems/startup_outcomes.py) and kept in `schedule`. The
fund only ever sees events once their period arrives, the way a real investor
only learns the future by living through it.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from config.venture_settings import COMMON_SHARES_AT_ENTRY
from utils.venture_math import (
    PreferredClass, WaterfallResult, liquidation_waterfall, price_per_share,
)


@dataclass
class ScheduledEvent:
    period: int
    kind: str                     # "round" | "exit" | "shutdown"
    round_name: str = ""
    pre_money: float = 0.0
    raise_amount: float = 0.0
    exit_value: float = 0.0       # exits only: the price the company sells for
    recovery: float = 0.0         # shutdowns only: share of preferred raised recovered

    @property
    def post_money(self) -> float:
        return self.pre_money + self.raise_amount


@dataclass
class Series:
    """A closed priced round: one class of 1x non-participating preferred."""
    name: str
    period: int
    pre_money: float
    raise_amount: float
    price: float
    shares: float

    @property
    def post_money(self) -> float:
        return self.pre_money + self.raise_amount


@dataclass
class Startup:
    id: int
    name: str
    sector: str
    stage: str                    # the stage it was at when it pitched
    pitch: str
    signals: Dict[str, int]       # visible 1-5 scores: noisy hints of hidden quality
    offered_period: int
    schedule: List[ScheduledEvent]
    # Hidden: never sent to the player while the game is live
    quality: float = 0.0
    common_shares: float = COMMON_SHARES_AT_ENTRY
    series: List[Series] = field(default_factory=list)
    open_round: Optional[ScheduledEvent] = None
    status: str = "private"       # "private" | "exited" | "shut down" | "sold"

    # ---------------- cap table ----------------

    def shares_outstanding(self) -> float:
        return self.common_shares + sum(s.shares for s in self.series)

    def last_price(self) -> float:
        """Price per share of the latest round: what every share is marked at."""
        return self.series[-1].price if self.series else 0.0

    def last_post_money(self) -> float:
        return self.series[-1].post_money if self.series else 0.0

    def preferred_raised(self) -> float:
        return sum(s.raise_amount for s in self.series)

    def preferred_classes(self) -> List[PreferredClass]:
        return [PreferredClass(s.name, s.shares, s.raise_amount) for s in self.series]

    # ---------------- lifecycle ----------------

    def events_at(self, period: int) -> List[ScheduledEvent]:
        return [e for e in self.schedule if e.period == period]

    def close_round(self) -> Series:
        """Close the open round: new preferred shares are issued at the round price."""
        rnd = self.open_round
        price = price_per_share(rnd.pre_money, self.shares_outstanding())
        series = Series(rnd.round_name, rnd.period, rnd.pre_money, rnd.raise_amount,
                        price, rnd.raise_amount / price)
        self.series.append(series)
        self.open_round = None
        return series

    def liquidate(self, event: ScheduledEvent) -> WaterfallResult:
        """Run the waterfall for an exit or a shutdown and mark the company as done."""
        if event.kind == "shutdown":
            value = event.recovery * self.preferred_raised()
            self.status = "shut down"
        else:
            value = event.exit_value
            self.status = "exited"
        return liquidation_waterfall(value, self.common_shares, self.preferred_classes())
