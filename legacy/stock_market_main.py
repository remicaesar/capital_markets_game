# !/usr/bin/env python3
"""
Ultra Advanced Stock Market CLI Game
====================================
Implements sophisticated market mechanics:
• Hidden information and smart money movements
• Market regimes (bull/bear/volatile/sideways)
• Algorithmic trading competition
• Market psychology and sentiment extremes
• Crisis events and contagion
• Ambiguous news with multiple interpretations
• Dynamic difficulty scaling

Run:
$ pip install rich numpy
$ python ultra_advanced_stock_game.py
"""

import random
import math
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Tuple, List, Optional, Any
from collections import deque
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.align import Align
from rich.text import Text
from rich.columns import Columns
from rich.progress import Progress, BarColumn, TextColumn

console = Console()

# ------------------- CONFIG ------------------- #
INITIAL_CASH = 10_000
NUM_COMPANIES = 10
MAX_TURNS = 50  # Increased for more complex gameplay
SECTORS = ["Tech", "Energy", "Finance", "Retail", "Healthcare"]
TRANSACTION_FEE = 0.01
DIVIDEND_YIELD = 0.002

# ---------- ADVANCED DIFFICULTY SETTINGS ---------- #
BASE_FALSE_SIGNAL_CHANCE = 0.25
BASE_ALGO_INTENSITY = 0.5
BASE_CRISIS_PROBABILITY = 0.02
INFORMATION_NOISE = 0.3
SMART_MONEY_ADVANTAGE = 3  # Turns ahead they trade

# ------------- SECTOR CORRELATIONS -------------- #
SECTOR_CORRELATIONS = {
    ("Tech", "Finance"): 0.35,
    ("Energy", "Finance"): 0.25,
    ("Tech", "Retail"): 0.15,
    ("Healthcare", "Finance"): 0.20,
    ("Energy", "Retail"): -0.10,  # Negative correlation
}

# ------------ COMPANY NAMES ------------- #
COMPANY_NAMES = {
    "Tech": ["TechCore", "QuantumAI"],          # Established vs cutting-edge
    "Energy": ["PetroMax", "SolarTech"],        # Traditional vs renewable
    "Finance": ["MegaBank", "TradeDesk"],       # Conservative vs aggressive
    "Retail": ["ShopMart", "E-Tail"],           # Brick-and-mortar vs online
    "Healthcare": ["PharmaCorp", "BioLabs"],    # Big pharma vs biotech
}


# ====================== MARKET REGIMES ====================== #
@dataclass
class MarketRegime:
    """Market regime affects all trading dynamics"""
    current: str = "sideways"
    strength: float = 1.0
    turns_in_regime: int = 0

    REGIMES = {
        "bull": {
            "volatility_mult": 0.7,
            "trend_strength": 0.015,
            "correlation_mult": 0.7,
            "news_sensitivity": 0.6,
            "mean_reversion": 0.3,
            "description": "🐂 Bull Market - Optimism Reigns"
        },
        "bear": {
            "volatility_mult": 1.5,
            "trend_strength": -0.02,
            "correlation_mult": 1.8,
            "news_sensitivity": 2.0,
            "mean_reversion": 0.1,
            "description": "🐻 Bear Market - Fear Dominates"
        },
        "volatile": {
            "volatility_mult": 2.5,
            "trend_strength": 0.0,
            "correlation_mult": 0.5,
            "news_sensitivity": 3.0,
            "mean_reversion": 0.8,
            "description": "🌪️ Volatile Market - Chaos Rules"
        },
        "sideways": {
            "volatility_mult": 1.0,
            "trend_strength": 0.0,
            "correlation_mult": 1.0,
            "news_sensitivity": 1.0,
            "mean_reversion": 0.6,
            "description": "➡️ Sideways Market - Range Bound"
        }
    }

    def check_regime_change(self, market_returns: List[float], volatility: float):
        """Determine if regime should change"""
        if len(market_returns) < 5:
            return None

        avg_return = np.mean(market_returns[-5:])
        recent_vol = np.std(market_returns[-5:])

        # Regime detection logic
        if avg_return > 0.03 and recent_vol < 0.02:
            new_regime = "bull"
        elif avg_return < -0.025:
            new_regime = "bear"
        elif recent_vol > 0.04:
            new_regime = "volatile"
        else:
            new_regime = "sideways"

        if new_regime != self.current:
            old_regime = self.current
            self.current = new_regime
            self.strength = 0.3
            self.turns_in_regime = 0
            return f"📊 REGIME CHANGE: {self.REGIMES[old_regime]['description']} → {self.REGIMES[new_regime]['description']}"
        else:
            self.strength = min(1.0, self.strength + 0.15)
            self.turns_in_regime += 1
            return None


# ====================== HIDDEN FACTORS ====================== #
@dataclass
class HiddenFactors:
    """Hidden information that affects prices"""
    true_values: Dict[str, float] = field(default_factory=dict)
    insider_sentiment: Dict[str, float] = field(default_factory=dict)
    debt_levels: Dict[str, float] = field(default_factory=dict)
    smart_money_positions: Dict[str, str] = field(default_factory=dict)
    pending_news: List[Dict[str, Any]] = field(default_factory=list)

    def initialize(self, companies: Dict[str, Any]):
        """Set up hidden factors for all companies"""
        for name, company in companies.items():
            # True value can significantly diverge from market
            self.true_values[name] = company.price * random.uniform(0.4, 2.5)
            # Insider sentiment predicts future moves
            self.insider_sentiment[name] = random.uniform(-1, 1)
            # Hidden leverage amplifies crashes
            self.debt_levels[name] = random.uniform(0.1, 0.9)

        # Smart money takes positions before news
        num_positions = min(5, len(companies) // 4)
        for _ in range(num_positions):
            company = random.choice(list(companies.keys()))
            action = "accumulating" if random.random() > 0.5 else "distributing"
            self.smart_money_positions[company] = action


# ====================== MARKET PSYCHOLOGY ====================== #
@dataclass
class MarketPsychology:
    """Tracks market sentiment and crowd behavior"""
    fear_greed_index: float = 50.0  # 0=extreme fear, 100=extreme greed
    herd_strength: float = 0.5
    complacency: float = 0.0
    capitulation_risk: float = 0.0

    def update(self, market_return: float, volatility: float, regime: str):
        """Update psychological indicators"""
        # Fear/Greed responds to returns
        self.fear_greed_index += market_return * 200
        self.fear_greed_index -= volatility * 100

        # Extremes tend to reverse
        if self.fear_greed_index > 85:
            self.fear_greed_index -= random.uniform(10, 20)
        elif self.fear_greed_index < 15:
            self.fear_greed_index += random.uniform(10, 20)

        self.fear_greed_index = max(0, min(100, self.fear_greed_index))

        # Herd behavior increases at extremes
        if self.fear_greed_index < 20 or self.fear_greed_index > 80:
            self.herd_strength = min(1.0, self.herd_strength + 0.1)
        else:
            self.herd_strength = max(0.2, self.herd_strength - 0.05)

        # Complacency in bull markets
        if regime == "bull" and market_return > 0:
            self.complacency = min(1.0, self.complacency + 0.05)
        elif market_return < -0.03:
            self.complacency = 0

        # Capitulation risk in bear markets
        if regime == "bear" and self.fear_greed_index < 20:
            self.capitulation_risk = min(1.0, self.capitulation_risk + 0.1)
        else:
            self.capitulation_risk = max(0, self.capitulation_risk - 0.05)

    def get_sentiment_emoji(self) -> str:
        if self.fear_greed_index >= 80:
            return "🤑 Extreme Greed"
        elif self.fear_greed_index >= 60:
            return "😊 Greed"
        elif self.fear_greed_index >= 40:
            return "😐 Neutral"
        elif self.fear_greed_index >= 20:
            return "😰 Fear"
        else:
            return "😱 Extreme Fear"


# ====================== ALGORITHMIC TRADERS ====================== #
class AlgorithmicTraders:
    """Simulates different algo trading strategies"""

    def __init__(self):
        self.momentum_strength = 0.5
        self.contrarian_strength = 0.5
        self.arb_strength = 0.3

    def get_pressure(self, company: Any, market_data: Dict) -> float:
        """Calculate net algo trading pressure"""
        pressure = 0.0

        # Momentum traders
        if len(company.price_history) >= 3:
            momentum = (company.price - company.price_history[-3]) / company.price_history[-3]
            pressure += momentum * self.momentum_strength * 0.1

        # Contrarian traders (RSI-based)
        if len(company.price_history) >= 14:
            rsi = self._calculate_rsi(company.price_history[-14:])
            if rsi > 70:
                pressure -= self.contrarian_strength * 0.05
            elif rsi < 30:
                pressure += self.contrarian_strength * 0.05

        # Arbitrage pressure (true value vs market)
        if company.name in market_data.get("true_values", {}):
            true_value = market_data["true_values"][company.name]
            mispricing = (true_value - company.price) / company.price
            pressure += np.sign(mispricing) * min(abs(mispricing), 0.1) * self.arb_strength * 0.03

        return pressure

    def _calculate_rsi(self, prices: List[float]) -> float:
        """Calculate RSI indicator"""
        gains = []
        losses = []

        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        avg_gain = np.mean(gains) if gains else 0
        avg_loss = np.mean(losses) if losses else 0

        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))


# ====================== SIMPLIFIED NEWS SYSTEM ====================== #
@dataclass
class NewsEvent:
    """A single news event with clear, predictable effects"""
    headline: str
    effect: float  # Positive = good for stocks, negative = bad
    sector: Optional[str] = None  # None = affects whole market
    context: str = ""  # Explains the impact to players


class AdvancedNewsSystem:
    """Generates clear news events that players can learn from"""

    POSITIVE_SECTOR_NEWS = {
        "Tech": [
            ("TechCore announces breakthrough AI chip", 0.06, "New technology drives investor optimism"),
            ("QuantumAI wins major government contract", 0.05, "Secured revenue boosts sector confidence"),
            ("Tech sector sees record consumer spending", 0.04, "Strong demand signals healthy growth"),
        ],
        "Energy": [
            ("Oil prices surge on supply concerns", 0.06, "Higher oil prices benefit energy producers"),
            ("SolarTech receives renewable energy subsidies", 0.05, "Government support improves profit outlook"),
            ("Cold weather forecast boosts energy demand", 0.04, "Increased consumption means higher revenues"),
        ],
        "Finance": [
            ("Fed signals interest rate stability", 0.05, "Stable rates support bank lending margins"),
            ("MegaBank reports strong loan growth", 0.06, "Healthy lending indicates economic strength"),
            ("Credit markets show improved liquidity", 0.04, "Easier borrowing conditions help financials"),
        ],
        "Retail": [
            ("Holiday shopping season exceeds expectations", 0.06, "Consumer spending drives retail profits"),
            ("E-Tail expands same-day delivery nationwide", 0.05, "Service improvements attract more customers"),
            ("Consumer confidence hits 12-month high", 0.04, "Optimistic consumers spend more freely"),
        ],
        "Healthcare": [
            ("PharmaCorp drug receives FDA approval", 0.07, "New drug opens significant revenue stream"),
            ("BioLabs clinical trial shows positive results", 0.06, "Promising data raises acquisition interest"),
            ("Healthcare spending bill passes Congress", 0.05, "Increased funding benefits entire sector"),
        ],
    }

    NEGATIVE_SECTOR_NEWS = {
        "Tech": [
            ("Major data breach reported at tech firm", -0.06, "Security concerns trigger selloff"),
            ("Antitrust investigation announced", -0.05, "Regulatory scrutiny weighs on valuations"),
            ("Chip shortage disrupts production", -0.04, "Supply issues hurt near-term earnings"),
        ],
        "Energy": [
            ("Oil prices drop on oversupply fears", -0.06, "Lower prices squeeze producer margins"),
            ("Renewable subsidy cuts announced", -0.05, "Reduced support impacts profitability"),
            ("Mild weather reduces heating demand", -0.04, "Lower consumption hurts revenues"),
        ],
        "Finance": [
            ("Fed hints at aggressive rate hikes", -0.06, "Rising rates may slow loan demand"),
            ("Major bank reports loan defaults rising", -0.05, "Credit quality concerns spread to sector"),
            ("Banking regulations to tighten", -0.04, "New rules may reduce profit margins"),
        ],
        "Retail": [
            ("Consumer spending drops unexpectedly", -0.06, "Weak demand signals trouble ahead"),
            ("Shipping costs surge on fuel prices", -0.05, "Higher costs eat into profit margins"),
            ("Retail theft reaches record levels", -0.04, "Shrinkage hurts store profitability"),
        ],
        "Healthcare": [
            ("Drug pricing legislation advances", -0.06, "Price caps threaten pharma revenues"),
            ("Clinical trial fails to meet endpoints", -0.07, "Failed trial eliminates expected revenue"),
            ("Medicare reimbursement cuts proposed", -0.05, "Lower payments reduce sector income"),
        ],
    }

    MARKET_WIDE_NEWS = [
        ("Economic growth exceeds expectations", 0.04, "Strong GDP lifts all sectors"),
        ("Inflation data comes in lower than expected", 0.03, "Easing inflation supports stock valuations"),
        ("Trade deal reached with major partner", 0.04, "Reduced tariffs benefit exporters"),
        ("Unemployment drops to multi-year low", 0.03, "Strong job market boosts consumer spending"),
        ("Recession fears grow on weak data", -0.05, "Economic slowdown concerns trigger selling"),
        ("Inflation spikes above forecasts", -0.04, "Rising prices may force rate hikes"),
        ("Geopolitical tensions escalate", -0.04, "Uncertainty drives investors to safety"),
        ("Major hedge fund liquidates positions", -0.03, "Forced selling pressures prices"),
    ]

    def generate_news(self) -> NewsEvent:
        """Generate a single clear news event with context"""
        if random.random() < 0.6:
            sector = random.choice(SECTORS)
            if random.random() < 0.5:
                headline, effect, context = random.choice(self.POSITIVE_SECTOR_NEWS[sector])
                icon = "📈"
            else:
                headline, effect, context = random.choice(self.NEGATIVE_SECTOR_NEWS[sector])
                icon = "📉"
            return NewsEvent(
                headline=f"{icon} {headline}",
                effect=effect,
                sector=sector,
                context=f"{context} ({sector} sector {'+' if effect > 0 else ''}{effect*100:.0f}%)"
            )
        else:
            headline, effect, context = random.choice(self.MARKET_WIDE_NEWS)
            icon = "📈" if effect > 0 else "📉"
            return NewsEvent(
                headline=f"{icon} {headline}",
                effect=effect,
                sector=None,
                context=f"{context} (Market {'+' if effect > 0 else ''}{effect*100:.0f}%)"
            )

    def generate_turn_news(self, regime: str, psychology) -> list:
        """Generate 1-2 news events for the turn"""
        events = [self.generate_news()]
        if random.random() < 0.4:
            events.append(self.generate_news())
        return events


# ====================== SIMPLIFIED CRISIS EVENTS ====================== #
@dataclass
class CrisisWarning:
    """Warning sign that a crisis may be coming"""
    message: str
    severity: int  # 1-3, higher = more likely crisis


@dataclass
class Crisis:
    """An active market crisis"""
    name: str
    headline: str
    impact: float
    duration: int
    context: str


class CrisisEventSystem:
    """Manages crisis events with visible buildup"""

    def __init__(self):
        self.active_crisis: Optional[Crisis] = None
        self.warning_level: int = 0
        self.turns_since_crisis: int = 0
        self.crisis_history: List[str] = []
        self.active_crises = []  # Legacy compatibility

    def get_warning(self, regime: str, recent_returns: List[float]) -> Optional[CrisisWarning]:
        """Check for warning signs - visible to players"""
        if self.active_crisis or self.turns_since_crisis < 5:
            return None
        warnings = []
        if regime == "bull" and self.turns_since_crisis > 15:
            warnings.append(CrisisWarning("Market complacency rising - extended bull run increases correction risk", 1))
        if regime == "volatile":
            warnings.append(CrisisWarning("Elevated volatility signals unstable conditions", 2))
        if len(recent_returns) >= 3 and sum(recent_returns[-3:]) / 3 < -0.03:
            warnings.append(CrisisWarning("Sustained losses may trigger panic selling", 2))
        if warnings:
            warning = max(warnings, key=lambda w: w.severity)
            self.warning_level = min(3, self.warning_level + warning.severity)
            return warning
        self.warning_level = max(0, self.warning_level - 1)
        return None

    def check_for_crisis(self, psychology_or_regime, regime_or_returns=None) -> Optional[Crisis]:
        """Check if a crisis triggers"""
        # Handle both old and new signatures
        if isinstance(psychology_or_regime, str):
            regime = psychology_or_regime
            recent_returns = regime_or_returns if regime_or_returns else []
        else:
            regime = regime_or_returns if regime_or_returns else "sideways"
            recent_returns = []

        self.turns_since_crisis += 1
        if self.active_crisis or self.warning_level < 2:
            return None
        crisis_prob = 0.05 * self.warning_level
        if random.random() > crisis_prob:
            return None

        if regime == "volatile" or (len(recent_returns) >= 3 and sum(recent_returns[-3:]) / 3 < -0.02):
            crisis = Crisis("market_crash", "MARKET CRASH: Panic selling triggers broad market decline!",
                          random.uniform(-0.12, -0.20), 2, "Widespread fear causes investors to liquidate positions")
        else:
            crisis = Crisis("flash_correction", "FLASH CORRECTION: Sudden selloff catches traders off guard!",
                          random.uniform(-0.08, -0.15), 1, "Algorithmic trading amplifies the downturn")

        self.active_crisis = crisis
        self.warning_level = 0
        self.turns_since_crisis = 0
        self.crisis_history.append(crisis.name)
        return crisis

    def process_active_crisis(self) -> Optional[str]:
        """Process ongoing crisis, return recovery message if crisis ends"""
        if not self.active_crisis:
            return None
        self.active_crisis.duration -= 1
        if self.active_crisis.duration <= 0:
            recovery_msg = f"Markets stabilize as {self.active_crisis.name.replace('_', ' ')} subsides"
            self.active_crisis = None
            return recovery_msg
        return None

    def get_crisis_impact(self) -> float:
        """Get the ongoing impact of active crisis"""
        return self.active_crisis.impact * 0.5 if self.active_crisis else 0.0


# ====================== ENHANCED COMPANY ====================== #
@dataclass
class Company:
    name: str
    sector: str
    price: float
    trend_long: int
    volatility: float = field(default_factory=lambda: random.uniform(0.02, 0.08))
    beta: float = field(default_factory=lambda: random.uniform(0.6, 1.8))
    trend_short: int = 0
    price_history: List[float] = field(default_factory=list)
    volume_history: List[float] = field(default_factory=list)

    # Valuation metrics (visible to players)
    pe_ratio: float = field(default_factory=lambda: random.uniform(8, 35))
    growth_rate: float = field(default_factory=lambda: random.uniform(-0.02, 0.15))
    debt_level: str = field(default_factory=lambda: random.choice(["Low", "Medium", "High"]))
    earnings_per_share: float = 0.0

    # Technical metrics
    momentum_score: float = 0.0
    relative_strength: float = 50.0
    earnings_momentum: float = 0.0

    def __post_init__(self):
        self.price_history.append(self.price)
        self.volume_history.append(1.0)
        self.earnings_per_share = self.price / self.pe_ratio
        self._apply_sector_characteristics()

    def _apply_sector_characteristics(self):
        """Adjust valuation metrics based on sector norms"""
        sector_profiles = {
            "Tech": {"pe_range": (15, 40), "growth_range": (0.05, 0.20), "debt_weights": [0.5, 0.35, 0.15]},
            "Energy": {"pe_range": (8, 20), "growth_range": (-0.05, 0.08), "debt_weights": [0.2, 0.4, 0.4]},
            "Finance": {"pe_range": (8, 18), "growth_range": (0.0, 0.10), "debt_weights": [0.3, 0.4, 0.3]},
            "Retail": {"pe_range": (10, 25), "growth_range": (-0.02, 0.12), "debt_weights": [0.3, 0.4, 0.3]},
            "Healthcare": {"pe_range": (12, 35), "growth_range": (0.03, 0.18), "debt_weights": [0.4, 0.4, 0.2]},
        }
        if self.sector in sector_profiles:
            profile = sector_profiles[self.sector]
            self.pe_ratio = round(random.uniform(*profile["pe_range"]), 1)
            self.growth_rate = round(random.uniform(*profile["growth_range"]), 3)
            self.debt_level = random.choices(["Low", "Medium", "High"], weights=profile["debt_weights"])[0]
            self.earnings_per_share = round(self.price / self.pe_ratio, 2)

    def get_debt_multiplier(self) -> float:
        """Returns crisis sensitivity multiplier based on debt level"""
        return {"Low": 0.8, "Medium": 1.0, "High": 1.4}[self.debt_level]

    def get_valuation_status(self) -> str:
        """Returns whether stock appears undervalued, fair, or overvalued"""
        if self.growth_rate <= 0:
            return "Overvalued" if self.pe_ratio > 20 else "Fair"
        peg = self.pe_ratio / (self.growth_rate * 100)
        if peg < 1.0:
            return "Undervalued"
        elif peg > 2.0:
            return "Overvalued"
        return "Fair"

    def update_price(self, base_change: float, regime_mult: Dict, algo_pressure: float,
                     psychology: MarketPsychology, hidden_factors: HiddenFactors):
        """Advanced price update with valuation metrics"""

        # 1. Apply regime effects
        change = base_change * regime_mult["news_sensitivity"]
        change += regime_mult["trend_strength"] * self.trend_long

        # 2. Add algorithmic trading pressure
        change += algo_pressure

        # 3. Growth rate provides baseline drift
        growth_per_turn = self.growth_rate / 50
        change += growth_per_turn

        # 4. Psychology effects
        psych_multiplier = 1.0
        if psychology.fear_greed_index > 80:
            psych_multiplier = 1.3 if change > 0 else 0.7
        elif psychology.fear_greed_index < 20:
            psych_multiplier = 0.7 if change > 0 else 1.5
        change *= psych_multiplier

        # 5. Debt level affects downside
        if change < 0:
            change *= self.get_debt_multiplier()

        # 6. Hidden value reversion
        if self.name in hidden_factors.true_values:
            true_value = hidden_factors.true_values[self.name]
            value_gap = (true_value - self.price) / self.price
            reversion_force = value_gap * regime_mult["mean_reversion"] * 0.02
            change += reversion_force

        # 7. Volatility and randomness
        random_shock = random.gauss(0, self.volatility * regime_mult["volatility_mult"])
        change += random_shock

        # 8. Herd behavior
        if psychology.herd_strength > 0.7:
            change *= (1 + psychology.herd_strength - 0.7)

        # 9. Apply the change
        self.price = max(1, round(self.price * (1 + change), 2))
        self.price_history.append(self.price)

        # 10. Update P/E ratio as price changes
        self.earnings_per_share *= (1 + growth_per_turn)
        if self.earnings_per_share > 0:
            self.pe_ratio = round(self.price / self.earnings_per_share, 1)
            self.pe_ratio = max(3, min(100, self.pe_ratio))

        # 11. Update volume
        volume = 1.0 + abs(change) * 10
        self.volume_history.append(volume)

        # 12. Update derived metrics
        self._update_metrics()

        return change

    def _update_metrics(self):
        """Update technical indicators"""
        if len(self.price_history) >= 10:
            short_ma = np.mean(self.price_history[-5:])
            long_ma = np.mean(self.price_history[-10:])
            self.momentum_score = (short_ma - long_ma) / long_ma

            gains = []
            losses = []
            for i in range(len(self.price_history) - 9, len(self.price_history)):
                change = self.price_history[i] - self.price_history[i - 1]
                if change > 0:
                    gains.append(change)
                else:
                    losses.append(abs(change))

            avg_gain = np.mean(gains) if gains else 0
            avg_loss = np.mean(losses) if losses else 0

            if avg_loss > 0:
                rs = avg_gain / avg_loss
                self.relative_strength = 100 - (100 / (1 + rs))
            else:
                self.relative_strength = 100

    def get_change_pct(self) -> float:
        if len(self.price_history) < 2:
            return 0.0
        return (self.price - self.price_history[-2]) / self.price_history[-2]

    def get_trend_indicator(self) -> str:
        change = self.get_change_pct()
        volume = self.volume_history[-1] if self.volume_history else 1.0

        # High volume moves get special indicators
        if volume > 3:
            if change > 0.05:
                return "🚀🔥"  # Explosive move up
            elif change < -0.05:
                return "💥📉"  # Crash

        # Normal indicators
        if change > 0.03:
            return "🚀"
        elif change > 0.01:
            return "📈"
        elif change < -0.03:
            return "💥"
        elif change < -0.01:
            return "📉"
        else:
            return "➡️"


# ====================== PLAYER WITH ADVANCED METRICS ====================== #
@dataclass
class Player:
    cash: float = INITIAL_CASH
    portfolio: Dict[str, Tuple[int, float]] = field(default_factory=dict)
    trade_count: int = 0
    total_fees_paid: float = 0.0
    starting_cash: float = INITIAL_CASH

    # Advanced tracking
    trade_history: List[Dict] = field(default_factory=list)
    portfolio_values: List[float] = field(default_factory=list)
    skill_rating: float = 0.5

    def portfolio_value(self, market: "Market") -> float:
        return sum(market.companies[n].price * s for n, (s, _) in self.portfolio.items())

    def net_worth(self, market: "Market") -> float:
        return self.cash + self.portfolio_value(market)

    def total_return_pct(self, market: "Market") -> float:
        return ((self.net_worth(market) - self.starting_cash) / self.starting_cash) * 100

    def calculate_sharpe_ratio(self) -> float:
        """Calculate risk-adjusted returns"""
        if len(self.portfolio_values) < 2:
            return 0.0

        returns = []
        for i in range(1, len(self.portfolio_values)):
            ret = (self.portfolio_values[i] - self.portfolio_values[i - 1]) / self.portfolio_values[i - 1]
            returns.append(ret)

        if not returns or np.std(returns) == 0:
            return 0.0

        risk_free_rate = 0.001  # 0.1% per turn
        excess_returns = [r - risk_free_rate for r in returns]
        return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(MAX_TURNS)

    def calculate_max_drawdown(self) -> float:
        """Calculate maximum peak-to-trough decline"""
        if not self.portfolio_values:
            return 0.0

        peak = self.portfolio_values[0]
        max_dd = 0.0

        for value in self.portfolio_values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak if peak > 0 else 0
            max_dd = max(max_dd, drawdown)

        return max_dd * 100  # As percentage

    def buy(self, market: "Market", company: Company, shares: int):
        cost = company.price * shares * (1 + TRANSACTION_FEE)
        if cost > self.cash:
            console.print(f"[red]❌ Not enough cash. Need ${cost:,.2f}, have ${self.cash:,.2f}[/red]")
            return False

        fee = company.price * shares * TRANSACTION_FEE
        self.cash -= cost
        self.total_fees_paid += fee
        self.trade_count += 1

        # Update portfolio
        total_shares, avg_price = self.portfolio.get(company.name, (0, 0))
        new_avg = ((total_shares * avg_price) + (company.price * shares)) / (total_shares + shares)
        self.portfolio[company.name] = (total_shares + shares, new_avg)

        # Record trade
        self.trade_history.append({
            "type": "buy",
            "company": company.name,
            "shares": shares,
            "price": company.price,
            "turn": market.turn
        })

        console.print(f"[green]✅ Bought {shares} × {company.name} @ ${company.price:.2f} (Fee: ${fee:.2f})[/green]")
        return True

    def sell(self, market: "Market", company: Company, shares: int):
        if company.name not in self.portfolio:
            console.print("[red]❌ You don't own that stock.[/red]")
            return False

        owned_shares, avg_price = self.portfolio[company.name]
        if shares > owned_shares:
            console.print(f"[red]❌ You only own {owned_shares} shares.[/red]")
            return False

        gross_proceeds = company.price * shares
        fee = gross_proceeds * TRANSACTION_FEE
        net_proceeds = gross_proceeds - fee

        self.cash += net_proceeds
        self.total_fees_paid += fee
        self.trade_count += 1

        # Calculate P&L
        cost_basis = avg_price * shares
        gain_loss = gross_proceeds - cost_basis

        # Update portfolio
        remaining = owned_shares - shares
        if remaining:
            self.portfolio[company.name] = (remaining, avg_price)
        else:
            del self.portfolio[company.name]

        # Record trade
        self.trade_history.append({
            "type": "sell",
            "company": company.name,
            "shares": shares,
            "price": company.price,
            "pnl": gain_loss,
            "turn": market.turn
        })

        color = "green" if gain_loss >= 0 else "red"
        console.print(
            f"[{color}]💰 Sold {shares} × {company.name} @ ${company.price:.2f} | P/L: ${gain_loss:.2f} (Fee: ${fee:.2f})[/{color}]"
        )
        return True

    def collect_dividends(self, market: "Market"):
        dividend = sum(
            shares * market.companies[name].price * DIVIDEND_YIELD
            for name, (shares, _) in self.portfolio.items()
        )
        if dividend > 0:
            self.cash += dividend
            console.print(f"[cyan]🎁 Dividends collected: ${dividend:.2f}[/cyan]")

    def update_metrics(self, market: "Market"):
        """Update performance tracking"""
        self.portfolio_values.append(self.net_worth(market))

        # Update skill rating based on risk-adjusted performance
        if len(self.portfolio_values) >= 5:
            recent_sharpe = self.calculate_sharpe_ratio()
            if recent_sharpe > 1.0:
                self.skill_rating = min(1.0, self.skill_rating + 0.02)
            elif recent_sharpe < -0.5:
                self.skill_rating = max(0.0, self.skill_rating - 0.02)


# ====================== ADVANCED MARKET ====================== #
class Market:
    def __init__(self):
        self.companies: Dict[str, Company] = {}
        self.turn = 1
        self.market_history: List[float] = []
        self.return_history: List[float] = []

        # Advanced systems
        self.regime = MarketRegime()
        self.hidden_factors = HiddenFactors()
        self.psychology = MarketPsychology()
        self.algos = AlgorithmicTraders()
        self.news_system = AdvancedNewsSystem()
        self.crisis_system = CrisisEventSystem()

        # Initialize
        self._generate_companies()
        self.hidden_factors.initialize(self.companies)

    def _generate_companies(self):
        companies_per_sector = NUM_COMPANIES // len(SECTORS)
        extra = NUM_COMPANIES % len(SECTORS)

        for i, sector in enumerate(SECTORS):
            count = companies_per_sector + (1 if i < extra else 0)
            available_names = COMPANY_NAMES[sector].copy()

            for j in range(count):
                name = available_names[j] if j < len(available_names) else f"{sector}Corp{j + 1}"
                price = round(random.uniform(20, 150), 2)
                trend_long = random.choice([-1, 1])

                self.companies[name] = Company(name, sector, price, trend_long)

    def get_market_cap(self) -> float:
        return sum(c.price for c in self.companies.values())

    def get_market_return(self) -> float:
        """Calculate market return for this turn"""
        if len(self.market_history) < 2:
            return 0.0
        return (self.market_history[-1] - self.market_history[-2]) / self.market_history[-2]

    def _apply_sector_correlations(self, sector_impacts: Dict[str, float]):
        """Apply correlations between sectors"""
        for (s1, s2), correlation in SECTOR_CORRELATIONS.items():
            if s1 in sector_impacts and sector_impacts[s1] != 0:
                sector_impacts[s2] = sector_impacts.get(s2, 0) + sector_impacts[s1] * correlation
            if s2 in sector_impacts and sector_impacts[s2] != 0:
                sector_impacts[s1] = sector_impacts.get(s1, 0) + sector_impacts[s2] * correlation

    def _process_smart_money(self) -> Dict[str, float]:
        """Smart money trades before news becomes public"""
        impacts = {}
        for company, action in self.hidden_factors.smart_money_positions.items():
            if action == "accumulating":
                impacts[company] = random.uniform(0.01, 0.03)
            else:  # distributing
                impacts[company] = random.uniform(-0.03, -0.01)
        return impacts

    def advance_turn(self, player: Player):
        """Turn advancement with clear, understandable events"""

        # 1. Check for regime change
        regime_msg = self.regime.check_regime_change(self.return_history,
                                                     np.std(self.return_history[-5:]) if len(
                                                         self.return_history) >= 5 else 0.02)

        # 2. Process smart money movements (hidden)
        smart_money_impacts = self._process_smart_money()

        # 3. Generate and process news (simplified: 1-2 clear events)
        displayed_events = []
        sector_impacts = {s: 0.0 for s in SECTORS}
        market_impact = 0.0

        news_events = self.news_system.generate_turn_news(self.regime.current, self.psychology)

        for event in news_events:
            # Apply the effect directly - no hidden interpretations
            if event.sector:
                sector_impacts[event.sector] += event.effect
            else:
                market_impact += event.effect

            # Show headline with context so players understand what happened
            displayed_events.append(f"{event.headline}")
            displayed_events.append(f"  → {event.context}")

        # 4. Check for crisis warning (visible to player)
        warning = self.crisis_system.get_warning(self.regime.current, self.return_history)
        if warning:
            displayed_events.append(f"⚠️ WARNING: {warning.message}")

        # 5. Check for crisis events
        crisis = self.crisis_system.check_for_crisis(self.regime.current, self.return_history)
        if crisis:
            displayed_events.insert(0, f"🚨 {crisis.headline}")
            displayed_events.insert(1, f"  → {crisis.context}")
            for company in self.companies.values():
                impact = crisis.impact * (0.5 + company.beta / 2)
                sector_impacts[company.sector] += impact

        # 6. Process ongoing crisis and check for recovery
        recovery_msg = self.crisis_system.process_active_crisis()
        if recovery_msg:
            displayed_events.append(f"📈 {recovery_msg}")

        # Add ongoing crisis impact
        ongoing_impact = self.crisis_system.get_crisis_impact()
        if ongoing_impact != 0:
            market_impact += ongoing_impact
            displayed_events.append(f"⚠️ Crisis ongoing: market under pressure ({ongoing_impact*100:.1f}%)")

        # 7. Apply sector correlations
        self._apply_sector_correlations(sector_impacts)

        # 8. Update each company
        company_changes = {}
        regime_params = self.regime.REGIMES[self.regime.current]

        for company in self.companies.values():
            market_data = {
                "true_values": self.hidden_factors.true_values,
                "regime": self.regime.current
            }
            algo_pressure = self.algos.get_pressure(company, market_data)

            if company.name in smart_money_impacts:
                algo_pressure += smart_money_impacts[company.name]

            base_change = sector_impacts.get(company.sector, 0) + market_impact

            change = company.update_price(base_change, regime_params, algo_pressure,
                                          self.psychology, self.hidden_factors)
            company_changes[company.name] = change

        # 9. Update market tracking
        self.market_history.append(self.get_market_cap())
        market_return = self.get_market_return()
        self.return_history.append(market_return)

        # 10. Update psychology
        market_volatility = np.std([c for c in company_changes.values()])
        self.psychology.update(market_return, market_volatility, self.regime.current)

        # 11. Update hidden factors
        if random.random() < 0.2:
            if self.hidden_factors.smart_money_positions:
                to_remove = random.choice(list(self.hidden_factors.smart_money_positions.keys()))
                del self.hidden_factors.smart_money_positions[to_remove]
            company = random.choice(list(self.companies.keys()))
            if company not in self.hidden_factors.smart_money_positions:
                action = "accumulating" if random.random() > 0.5 else "distributing"
                self.hidden_factors.smart_money_positions[company] = action

        # 12. Add regime change message at top if any
        if regime_msg:
            displayed_events.insert(0, regime_msg)

        # 13. Display events with context
        if displayed_events:
            console.print(Panel("\n".join(displayed_events[:8]), title="📰 Market News", style="yellow"))

        # 14. Update difficulty based on player skill
        self._adjust_difficulty(player)

        self.turn += 1

    def _adjust_difficulty(self, player: Player):
        """Dynamically adjust difficulty based on player performance"""
        skill_mult = 0.5 + player.skill_rating

        # Adjust algo trading intensity
        self.algos.momentum_strength = min(1.0, 0.3 * skill_mult)
        self.algos.contrarian_strength = min(1.0, 0.3 * skill_mult)
        self.algos.arb_strength = min(0.5, 0.2 * skill_mult)

        # Adjust crisis probability (implicit through trigger conditions)
        # More skilled players face more crises

    def market_table(self, player: Player) -> Table:
        """Enhanced market display with valuation metrics"""
        progress = (self.turn - 1) / MAX_TURNS
        progress_bar = "█" * int(progress * 20) + "░" * (20 - int(progress * 20))

        # Title with regime indicator
        regime_desc = self.regime.REGIMES[self.regime.current]["description"]
        title = f"📈 Market - Turn {self.turn}/{MAX_TURNS} [{progress_bar}] | {regime_desc}"

        tbl = Table(title=title)
        tbl.add_column("Company", style="bold", min_width=10)
        tbl.add_column("Sector", style="dim", min_width=8)
        tbl.add_column("Price", justify="right", min_width=8)
        tbl.add_column("Change", justify="right", min_width=8)
        tbl.add_column("P/E", justify="right", min_width=6)
        tbl.add_column("Growth", justify="right", min_width=7)
        tbl.add_column("Debt", justify="center", min_width=6)
        tbl.add_column("Value", justify="center", min_width=10)

        sorted_companies = sorted(self.companies.values(), key=lambda c: (c.sector, c.name))
        current_sector = None

        for c in sorted_companies:
            if c.sector != current_sector:
                if current_sector is not None:
                    tbl.add_section()
                current_sector = c.sector

            change_pct = c.get_change_pct() * 100
            change_text = Text(f"{change_pct:+.1f}%")
            change_text.stylize("green" if change_pct >= 0 else "red")

            # P/E coloring (lower is generally better)
            pe_text = Text(f"{c.pe_ratio:.1f}")
            if c.pe_ratio < 12:
                pe_text.stylize("green")  # Cheap
            elif c.pe_ratio > 30:
                pe_text.stylize("red")  # Expensive

            # Growth coloring
            growth_text = Text(f"{c.growth_rate * 100:+.1f}%")
            if c.growth_rate > 0.10:
                growth_text.stylize("green bold")  # High growth
            elif c.growth_rate > 0:
                growth_text.stylize("green")
            else:
                growth_text.stylize("red")  # Negative growth

            # Debt coloring
            debt_text = Text(c.debt_level)
            if c.debt_level == "Low":
                debt_text.stylize("green")
            elif c.debt_level == "High":
                debt_text.stylize("red")

            # Valuation status
            val_status = c.get_valuation_status()
            val_text = Text(val_status)
            if val_status == "Undervalued":
                val_text.stylize("green bold")
            elif val_status == "Overvalued":
                val_text.stylize("red")

            # Highlight owned stocks
            name_style = "bold cyan" if c.name in player.portfolio else ""

            # Add warning for extreme moves
            if abs(change_pct) > 10:
                name_style = "bold yellow"

            tbl.add_row(
                Text(c.name, style=name_style),
                c.sector,
                f"${c.price:.2f}",
                change_text,
                pe_text,
                growth_text,
                debt_text,
                val_text,
            )

        return tbl

    def psychology_panel(self) -> Panel:
        """Display market psychology indicators"""
        sentiment = self.psychology.get_sentiment_emoji()

        # Create visual bars
        fear_greed_bar = self._create_bar(self.psychology.fear_greed_index, 100, 20)
        herd_bar = self._create_bar(self.psychology.herd_strength * 100, 100, 20)
        complacency_bar = self._create_bar(self.psychology.complacency * 100, 100, 20)

        text = f"""🧠 Market Psychology
{sentiment} ({self.psychology.fear_greed_index:.0f}/100)
Fear/Greed: {fear_greed_bar}
Herd Level: {herd_bar}
Complacency: {complacency_bar}"""

        if self.psychology.capitulation_risk > 0.5:
            text += "\n⚠️ [red]High capitulation risk![/red]"

        return Panel(text, title="🎭 Market Sentiment", style="magenta")

    def _create_bar(self, value: float, max_val: float, width: int) -> str:
        """Create a visual progress bar"""
        filled = int((value / max_val) * width)
        return "█" * filled + "░" * (width - filled)


# ====================== ENHANCED UI FUNCTIONS ====================== #
def display_advanced_stats(player: Player, market: Market) -> Panel:
    """Display comprehensive player statistics"""
    net_worth = player.net_worth(market)
    total_return = player.total_return_pct(market)
    sharpe = player.calculate_sharpe_ratio()
    max_dd = player.calculate_max_drawdown()

    # Win rate calculation
    winning_trades = sum(1 for t in player.trade_history if t.get("pnl", 0) > 0)
    total_trades = sum(1 for t in player.trade_history if t["type"] == "sell")
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

    # Skill rating indicator
    skill_stars = "⭐" * int(player.skill_rating * 5)

    stats_text = f"""💰 Cash: ${player.cash:,.2f}
📊 Portfolio: ${player.portfolio_value(market):,.2f}
💎 Net Worth: ${net_worth:,.2f}
📈 Total Return: {total_return:+.1f}%
📊 Sharpe Ratio: {sharpe:+.2f}
📉 Max Drawdown: -{max_dd:.1f}%
🎯 Win Rate: {win_rate:.1f}%
🔄 Total Trades: {player.trade_count}
💸 Fees Paid: ${player.total_fees_paid:.2f}
🌟 Skill Rating: {skill_stars}"""

    return Panel(stats_text, title="📋 Advanced Stats", style="cyan")


def display_portfolio_analysis(player: Player, market: Market) -> Table:
    """Enhanced portfolio display with risk metrics"""
    tbl = Table(title="📊 Portfolio Analysis")
    tbl.add_column("Company", style="bold")
    tbl.add_column("Shares", justify="right")
    tbl.add_column("Avg Cost", justify="right")
    tbl.add_column("Current", justify="right")
    tbl.add_column("Value", justify="right")
    tbl.add_column("P/L", justify="right")
    tbl.add_column("%", justify="right")
    tbl.add_column("% of Port", justify="right")
    tbl.add_column("Beta", justify="right")

    if not player.portfolio:
        tbl.add_row("No holdings", "", "", "", "", "", "", "", "")
        return tbl

    total_value = player.portfolio_value(market)
    total_cost = 0
    portfolio_beta = 0

    for name, (shares, avg) in sorted(player.portfolio.items()):
        company = market.companies[name]
        cur = company.price
        value = cur * shares
        cost = avg * shares
        pl = value - cost
        pl_pct = (pl / cost * 100) if cost > 0 else 0
        port_pct = (value / total_value * 100) if total_value > 0 else 0

        total_cost += cost
        portfolio_beta += company.beta * (value / total_value) if total_value > 0 else 0

        pl_text = Text(f"${pl:,.2f}")
        pl_text.stylize("green" if pl >= 0 else "red")

        pct_text = Text(f"{pl_pct:+.1f}%")
        pct_text.stylize("green" if pl_pct >= 0 else "red")

        # Highlight concentrated positions
        port_pct_text = Text(f"{port_pct:.1f}%")
        if port_pct > 30:
            port_pct_text.stylize("yellow")

        tbl.add_row(
            name,
            f"{shares:,}",
            f"${avg:.2f}",
            f"${cur:.2f}",
            f"${value:,.2f}",
            pl_text,
            pct_text,
            port_pct_text,
            f"{company.beta:.2f}"
        )

    # Total row
    total_pl = total_value - total_cost
    total_pl_pct = (total_pl / total_cost * 100) if total_cost > 0 else 0

    total_pl_text = Text(f"${total_pl:,.2f}")
    total_pl_text.stylize("bold green" if total_pl >= 0 else "bold red")

    total_pct_text = Text(f"{total_pl_pct:+.1f}%")
    total_pct_text.stylize("bold green" if total_pl_pct >= 0 else "bold red")

    tbl.add_section()
    tbl.add_row(
        "[bold]TOTAL[/bold]",
        "",
        "",
        "",
        f"[bold]${total_value:,.2f}[/bold]",
        total_pl_text,
        total_pct_text,
        "[bold]100%[/bold]",
        f"[bold]{portfolio_beta:.2f}[/bold]"
    )

    return tbl


def display_market_analysis(market: Market) -> Panel:
    """Show market analysis hints with valuation insights"""
    hints = []

    # Valuation-based hints
    undervalued = [c for c in market.companies.values() if c.get_valuation_status() == "Undervalued"]
    overvalued = [c for c in market.companies.values() if c.get_valuation_status() == "Overvalued"]

    if undervalued:
        names = ", ".join([c.name for c in undervalued[:3]])
        hints.append(f"💎 Potentially undervalued: {names}")

    if overvalued:
        names = ", ".join([c.name for c in overvalued[:3]])
        hints.append(f"⚠️ Potentially overvalued: {names}")

    # High growth opportunities
    high_growth = [c for c in market.companies.values() if c.growth_rate > 0.12]
    if high_growth:
        names = ", ".join([c.name for c in high_growth])
        hints.append(f"🚀 High growth stocks: {names}")

    # Risky debt situations
    high_debt = [c for c in market.companies.values() if c.debt_level == "High"]
    if high_debt and market.regime.current in ["bear", "volatile"]:
        names = ", ".join([c.name for c in high_debt])
        hints.append(f"💸 High debt (risky in this market): {names}")

    # Regime hints
    if market.regime.turns_in_regime > 8:
        hints.append("📊 This market regime has persisted for a while...")

    # Psychology hints
    if market.psychology.fear_greed_index > 75:
        hints.append("🤔 The market seems quite euphoric - be cautious of high P/E stocks")
    elif market.psychology.fear_greed_index < 25:
        hints.append("😰 Fear is dominating - undervalued stocks may be opportunities")

    # Crisis hints
    if market.crisis_system.active_crisis:
        hints.append(f"🚨 Active crisis: {market.crisis_system.active_crisis.name.replace('_', ' ')}")

    # Crisis warning
    if market.crisis_system.warning_level >= 2:
        hints.append("⚠️ Market stress building - consider reducing high-debt positions")

    if not hints:
        hints.append("🔍 Markets appear relatively stable")

    return Panel("\n".join(hints), title="🔮 Market Analysis", style="yellow")


# ====================== INPUT HELPERS ====================== #
def get_int_input(prompt: str, min_val: int = 0, max_val: Optional[int] = None) -> int:
    while True:
        try:
            value = int(input(prompt))
            if value < min_val:
                console.print(f"[red]Please enter a value ≥ {min_val}[/red]")
                continue
            if max_val is not None and value > max_val:
                console.print(f"[red]Please enter a value ≤ {max_val}[/red]")
                continue
            return value
        except ValueError:
            console.print("[red]Please enter a valid number[/red]")
        except KeyboardInterrupt:
            return 0


def get_company_input(market: Market) -> str:
    while True:
        name = input("Company name: ").strip()
        if name in market.companies:
            return name
        for n in market.companies:
            if n.lower() == name.lower():
                return n
        console.print(f"[red]'{name}' not found. Available companies:[/red]")
        for i, n in enumerate(sorted(market.companies)):
            console.print(f"  {n}", end="  ")
            if (i + 1) % 4 == 0:
                console.print()
        console.print()


# ====================== MAIN GAME LOOP ====================== #
def main():
    market = Market()
    player = Player()

    welcome = """
🎯 Goal: Beat the market with $10,000 starting capital!
⚠️ WARNING: This market is ULTRA REALISTIC:
   • News can be misleading or have delayed effects
   • Algorithmic traders compete against you
   • Market psychology drives irrational moves
   • Hidden forces affect prices
   • Crisis events can strike anytime

📊 Commands: buy, sell, hold, analysis, hints, guide, quit
💡 Watch for: RSI extremes, momentum shifts, regime changes
"""

    console.print(Panel("[bold red]ULTRA ADVANCED STOCK MARKET GAME[/bold red]" + welcome, style="red"))
    input("\nPress Enter to begin your trading career...")

    while market.turn <= MAX_TURNS:
        console.clear()

        # Main display
        market_table = market.market_table(player)
        stats_panel = display_advanced_stats(player, market)
        psych_panel = market.psychology_panel()

        # Layout
        console.print(Columns([market_table, Columns([stats_panel, psych_panel])]))
        console.print()
        console.print(display_portfolio_analysis(player, market))

        # Actions
        console.print("\n[bold]Actions:[/bold] buy | sell | hold | analysis | hints | guide | quit")
        action = input("\n> ").strip().lower()

        if action == "buy":
            cname = get_company_input(market)
            if not cname:
                continue
            company = market.companies[cname]
            max_shares = int(player.cash // (company.price * (1 + TRANSACTION_FEE)))
            if max_shares == 0:
                console.print("[red]❌ Not enough cash to buy any shares.[/red]")
                input("\nPress Enter to continue...")
                continue
            console.print(f"Max affordable shares: {max_shares:,}")
            console.print(f"RSI: {company.relative_strength:.0f} | Momentum: {company.momentum_score * 100:+.1f}%")
            qty = get_int_input("Shares to buy: ", 1, max_shares)
            if qty:
                player.buy(market, company, qty)

        elif action == "sell":
            if not player.portfolio:
                console.print("[yellow]No holdings to sell.[/yellow]")
                input("\nPress Enter to continue...")
                continue
            cname = get_company_input(market)
            if cname not in player.portfolio:
                console.print("[red]❌ You don't own that stock.[/red]")
                input("\nPress Enter to continue...")
                continue
            owned = player.portfolio[cname][0]
            console.print(f"Shares owned: {owned:,}")
            qty = get_int_input("Shares to sell: ", 1, owned)
            if qty:
                player.sell(market, market.companies[cname], qty)

        elif action == "hold":
            console.print("[blue]⏩ Holding positions...[/blue]")

        elif action == "analysis":
            console.clear()
            console.print(display_market_analysis(market))
            console.print()

            # Sector analysis
            sector_performance = {}
            for company in market.companies.values():
                if company.sector not in sector_performance:
                    sector_performance[company.sector] = []
                sector_performance[company.sector].append(company.get_change_pct())

            console.print("[bold]Sector Performance:[/bold]")
            for sector, changes in sorted(sector_performance.items()):
                avg_change = np.mean(changes) * 100
                color = "green" if avg_change > 0 else "red"
                console.print(f"  {sector}: [{color}]{avg_change:+.1f}%[/{color}]")

            input("\nPress Enter to continue...")
            continue

        elif action == "hints":
            hints = [
                "💡 Low P/E + High Growth = potentially undervalued opportunity",
                "💡 High P/E + Negative Growth = danger zone, avoid!",
                "💡 High debt stocks crash harder during crises - reduce exposure",
                "💡 Low debt stocks are defensive - good for uncertain markets",
                "💡 Growth stocks outperform in bull markets",
                "💡 Value stocks (low P/E) outperform in bear markets",
                "💡 Watch the 'Value' column - undervalued stocks often rebound",
                "💡 Crisis warnings appear before crashes - take them seriously",
                "💡 Sector news affects both companies in that sector",
                "💡 Diversify across sectors to reduce risk",
            ]
            console.print(Panel(random.choice(hints), title="💡 Trading Wisdom", style="cyan"))
            input("\nPress Enter to continue...")
            continue

        elif action == "guide":
            guide = """
[bold cyan]📊 VALUATION METRICS GUIDE[/bold cyan]

[bold]P/E Ratio (Price/Earnings)[/bold]
  • Shows how much you pay for $1 of company profit
  • [green]Low P/E (<12)[/green] = Cheap, may be undervalued
  • [red]High P/E (>30)[/red] = Expensive, may be overvalued
  • Compare within sectors - Tech has higher P/E than Energy

[bold]Growth Rate[/bold]
  • Annual earnings growth rate
  • [green]+10% or higher[/green] = High growth, justifies higher P/E
  • [red]Negative[/red] = Declining company, risky

[bold]Debt Level[/bold]
  • [green]Low[/green] = Safe, loses less during crises
  • [yellow]Medium[/yellow] = Average risk
  • [red]High[/red] = Risky, drops 40% more during downturns

[bold]Value Status[/bold]
  • [green]Undervalued[/green] = P/E is low relative to growth (buy signal)
  • Fair = Reasonably priced
  • [red]Overvalued[/red] = P/E is high relative to growth (sell signal)

[bold cyan]💡 STRATEGY TIPS[/bold cyan]
  • Bull market: Buy high-growth stocks, accept higher P/E
  • Bear market: Buy low P/E, low debt defensive stocks
  • Before crisis: Reduce high-debt positions
  • After crash: Hunt for undervalued opportunities
"""
            console.print(Panel(guide, title="📚 Investor's Guide", style="blue"))
            input("\nPress Enter to continue...")
            continue

        elif action == "quit":
            if input("Really quit? (y/N): ").lower().startswith("y"):
                break
            continue

        else:
            console.print("[red]Invalid command.[/red]")
            input("\nPress Enter to continue...")
            continue

        # End of turn
        player.collect_dividends(market)
        player.update_metrics(market)

        if market.turn < MAX_TURNS:
            input("\nPress Enter to advance to next turn...")
            market.advance_turn(player)

    # Game Over
    console.clear()
    worth = player.net_worth(market)
    ret = player.total_return_pct(market)
    sharpe = player.calculate_sharpe_ratio()
    max_dd = player.calculate_max_drawdown()

    # Market return for comparison
    market_return = ((market.get_market_cap() - sum(c.price_history[0] for c in market.companies.values())) /
                     sum(c.price_history[0] for c in market.companies.values())) * 100

    alpha = ret - market_return

    # Performance rating
    if sharpe > 2.0 and alpha > 20:
        msg, style = "🏅 LEGENDARY TRADER! You've mastered the markets!", "bold green"
    elif sharpe > 1.5 and alpha > 10:
        msg, style = "🏆 EXPERT PERFORMANCE! Outstanding risk-adjusted returns!", "bold cyan"
    elif sharpe > 1.0 and alpha > 0:
        msg, style = "🎉 SKILLED TRADER! You beat the market!", "green"
    elif sharpe > 0.5:
        msg, style = "👍 SOLID PERFORMANCE! Positive risk-adjusted returns.", "yellow"
    elif ret > 0:
        msg, style = "🙂 Break-even trader. Room for improvement.", "yellow"
    else:
        msg, style = "😢 The market humbled you. Study and try again.", "red"

    summary = f"""
Final Net Worth: ${worth:,.2f}
Total Return: {ret:+.1f}%
Market Return: {market_return:+.1f}%
Alpha (Outperformance): {alpha:+.1f}%
Sharpe Ratio: {sharpe:+.2f}
Maximum Drawdown: -{max_dd:.1f}%
Total Trades: {player.trade_count}
Fees Paid: ${player.total_fees_paid:.2f}

{msg}
"""

    console.print(Panel("🎮 [bold]GAME OVER[/bold]\n" + summary, style=style))


# ====================== ENTRY POINT ====================== #
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Game interrupted. Thanks for playing![/yellow]")
    except Exception as e:
        console.print(f"\n[red]An error occurred: {e}[/red]")
        console.print("[yellow]Please ensure you have required packages: pip install rich numpy[/yellow]")
