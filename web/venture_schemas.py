"""
Pydantic models for the venture fund API

response_model is a projection: any key the state builder emits but a model here
does not declare is silently dropped. tests/test_venture_api.py checks every key
survives, so a new field must be declared here as well.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# Request Models
class NewFundRequest(BaseModel):
    seed: Optional[int] = None


class CommitRequest(BaseModel):
    game_id: str
    deal_id: int
    check: float = Field(ge=0, description="0 withdraws an earlier commitment")
    reserve: float = Field(ge=0)


class FollowOnRequest(BaseModel):
    game_id: str
    startup_id: int
    amount: float = Field(ge=0, description="0 passes on the round")


class AdvanceFundRequest(BaseModel):
    game_id: str


# State Models
class FundStatus(BaseModel):
    period: int
    max_periods: int
    investment_periods: int
    period_label: str
    phase: str
    fund_size: float
    management_fee_rate: float
    carry_rate: float
    lifetime_fees: float
    investable_capital: float
    min_check: float
    max_company_amount: float
    default_reserve_ratio: float
    invested: float
    reserved: float
    pending: float
    available: float
    fees_paid: float
    paid_in: float
    nav: float
    distributions: float
    net_distributions: float
    carry_accrued: float
    tvpi: float
    dpi: float
    gross_moic: float
    net_irr: Optional[float] = None


class DealState(BaseModel):
    id: int
    name: str
    sector: str
    stage: str
    pitch: str
    signals: Dict[str, int]
    raise_amount: float
    pre_money: float
    post_money: float
    committed_check: Optional[float] = None
    committed_reserve: Optional[float] = None


class FollowOnState(BaseModel):
    startup_id: int
    name: str
    round_name: str
    pre_money: float
    raise_amount: float
    post_money: float
    step_up: float
    down_round: bool
    ownership: float
    pro_rata: float
    reserve: float
    decision: Optional[float] = None


class RoundState(BaseModel):
    name: str
    period_label: str
    post_money: float
    price: float


class PositionState(BaseModel):
    id: int
    name: str
    sector: str
    stage: str
    entry_label: str
    status: str
    invested: float
    reserve: float
    ownership: float
    mark: float
    proceeds: float
    multiple: float
    rounds: List[RoundState]


class HistoryPoint(BaseModel):
    period: int
    label: str
    paid_in: float
    distributions: float
    net_distributions: float
    nav: float
    cumulative_net_cash_flow: float
    tvpi: float
    dpi: float


class WaterfallRowState(BaseModel):
    name: str
    preference: float
    converted: bool
    payout: float
    yours: float


class WaterfallState(BaseModel):
    rows: List[WaterfallRowState]
    common_payout: float


class ExitState(BaseModel):
    period_label: str
    name: str
    kind: str
    exit_value: float
    fund_proceeds: float
    fund_invested: float
    waterfall: Optional[WaterfallState] = None


class LogEntry(BaseModel):
    period_label: str
    text: str


class ReportDeal(BaseModel):
    name: str
    invested: float
    value: float
    multiple: float
    outcome: str
    share_of_value: float
    returned_fund: bool


class FundReport(BaseModel):
    headline: str
    rating: str
    fund_returners: List[str]
    deal_count: int
    losers: int
    paid_in: float
    invested: float
    fees_paid: float
    gross_proceeds: float
    carry_paid: float
    net_to_lps: float
    gross_moic: float
    tvpi: float
    dpi: float
    net_irr: Optional[float] = None
    deals: List[ReportDeal]


class VentureState(BaseModel):
    fund: FundStatus
    deals: List[DealState]
    follow_ons: List[FollowOnState]
    portfolio: List[PositionState]
    history: List[HistoryPoint]
    exits: List[ExitState]
    log: List[LogEntry]
    report: Optional[FundReport] = None
    seed: int


# Response Models
class NewFundResponse(BaseModel):
    game_id: str
    state: VentureState


class VentureStateResponse(BaseModel):
    state: VentureState


class VentureActionResponse(BaseModel):
    success: bool
    message: str
    state: VentureState


class AdvanceFundResponse(BaseModel):
    events: List[str]
    state: VentureState


class Mechanic(BaseModel):
    key: str
    title: str
    body: str


class MechanicsResponse(BaseModel):
    mechanics: List[Mechanic]
