"""
Pydantic models for API request/response validation
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


# Request Models
class NewGameRequest(BaseModel):
    seed: Optional[int] = None


class ActionRequest(BaseModel):
    game_id: str
    action: str  # buy, sell, short, cover
    company: str
    shares: int = Field(gt=0, description="Must be a positive whole number of shares")


class AdvanceRequest(BaseModel):
    game_id: str


class SaveGameRequest(BaseModel):
    game_id: str
    slot: str = "websave"


class LoadGameRequest(BaseModel):
    slot: str


class PlaceOrderRequest(BaseModel):
    game_id: str
    order_type: str  # 'limit', 'stop_loss', 'take_profit'
    action: str  # 'buy', 'sell', 'short', 'cover'
    company: str
    shares: int = Field(gt=0, description="Must be a positive whole number of shares")
    limit_price: float = Field(gt=0)


class CancelOrderRequest(BaseModel):
    game_id: str
    order_id: int


class BuyOptionRequest(BaseModel):
    game_id: str
    company: str
    option_type: str  # 'call' or 'put'
    strike_price: float = Field(gt=0)
    contracts: int = Field(gt=0)


class OptionActionRequest(BaseModel):
    game_id: str
    option_id: int


# Response Models
class CompanyState(BaseModel):
    name: str
    sector: str
    price: float
    change_pct: float
    rsi: float
    momentum: float
    volume: float
    trend: str
    beta: float
    pe_ratio: float = 0.0
    growth_rate: float = 0.0
    debt_level: str = "Medium"
    valuation: str = "Fair"
    # response_model is a projection: any key not declared here is silently
    # dropped from the payload. These two feed the price/volume charts, and
    # their absence showed up only as a chart with a single flat data point.
    price_history: List[float] = []
    volume_history: List[float] = []


class PortfolioPosition(BaseModel):
    company: str
    shares: int
    avg_price: float
    current_price: float
    value: float
    pnl: float
    pnl_pct: float


class ShortPosition(BaseModel):
    company: str
    shares: int
    borrow_price: float
    current_price: float
    value: float
    pnl: float
    pnl_pct: float


class PsychologyState(BaseModel):
    fear_greed_index: float
    herd_strength: float
    complacency: float
    capitulation_risk: float
    sentiment: str


class PendingOrder(BaseModel):
    id: int
    order_type: str
    action: str
    company: str
    shares: int
    limit_price: float
    current_price: float
    created_turn: int
    created_price: float


class OptionPosition(BaseModel):
    id: int
    type: str  # 'call' or 'put'
    company: str
    strike_price: float
    premium: float
    contracts: int
    created_turn: int
    expiry_turn: int
    turns_remaining: int
    current_price: float
    current_value: float
    intrinsic_value: float
    total_premium_paid: float
    pnl: float
    in_the_money: bool


class OptionStrike(BaseModel):
    strike: float
    premium: float
    total_cost: float
    itm: bool


class PlayerStats(BaseModel):
    cash: float
    portfolio_value: float
    short_value: float
    short_pnl: float
    options_value: float = 0.0
    options_pnl: float = 0.0
    net_worth: float
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown: float
    trade_count: int
    total_fees_paid: float
    total_slippage_paid: float
    total_borrow_fees_paid: float
    margin_calls_received: int
    available_margin: float


class GameState(BaseModel):
    turn: int
    max_turns: int
    regime: str
    companies: List[CompanyState]
    portfolio: List[PortfolioPosition]
    short_positions: List[ShortPosition]
    pending_orders: List[PendingOrder] = []
    options_positions: List[OptionPosition] = []
    player: PlayerStats
    psychology: PsychologyState
    news: List[str]
    game_over: bool = False
    market_return_history: List[float] = []


class NewGameResponse(BaseModel):
    game_id: str
    state: GameState


class StateResponse(BaseModel):
    state: GameState


class ActionResponse(BaseModel):
    success: bool
    message: str
    state: GameState


class AdvanceResponse(BaseModel):
    news: List[str]
    state: GameState
    game_over: bool
    final_stats: Optional[Dict[str, Any]] = None


class SaveInfo(BaseModel):
    slot: str
    turn: int
    seed: Optional[int]
    timestamp: str


class SavesListResponse(BaseModel):
    saves: List[SaveInfo]


class SaveGameResponse(BaseModel):
    success: bool
    message: str
    path: str


class LoadGameResponse(BaseModel):
    success: bool
    message: str
    game_id: Optional[str] = None
    state: Optional[GameState] = None


class PlaceOrderResponse(BaseModel):
    success: bool
    message: str
    order: Optional[Dict[str, Any]] = None
    state: GameState


class CancelOrderResponse(BaseModel):
    success: bool
    message: str
    state: GameState


class OptionChainResponse(BaseModel):
    company: str
    current_price: float
    volatility: float
    calls: List[OptionStrike]
    puts: List[OptionStrike]


class BuyOptionResponse(BaseModel):
    success: bool
    message: str
    option: Optional[Dict[str, Any]] = None
    state: GameState


class OptionActionResponse(BaseModel):
    success: bool
    message: str
    state: GameState
