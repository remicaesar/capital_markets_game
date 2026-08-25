"""
Company entity with advanced metrics and price dynamics
"""

import random
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class Company:
    name: str
    sector: str
    price: float
    trend_long: int
    volatility: float = field(default_factory=lambda: random.uniform(0.01, 0.04))
    beta: float = field(default_factory=lambda: random.uniform(0.6, 1.8))
    trend_short: int = 0
    price_history: List[float] = field(default_factory=list)
    volume_history: List[float] = field(default_factory=list)

    # Valuation metrics (visible to players)
    pe_ratio: float = field(default_factory=lambda: random.uniform(8, 35))
    growth_rate: float = field(default_factory=lambda: random.uniform(-0.02, 0.15))
    debt_level: str = field(default_factory=lambda: random.choice(["Low", "Medium", "High"]))
    earnings_per_share: float = 0.0  # Calculated from price / P/E

    # Technical metrics
    momentum_score: float = 0.0
    relative_strength: float = 50.0
    earnings_momentum: float = 0.0

    def __post_init__(self):
        self.price_history.append(self.price)
        self.volume_history.append(1.0)  # Normalized volume
        # Calculate initial EPS from price and P/E
        self.earnings_per_share = self.price / self.pe_ratio
        # Adjust characteristics based on sector
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
            self.debt_level = random.choices(
                ["Low", "Medium", "High"],
                weights=profile["debt_weights"]
            )[0]
            # Recalculate EPS with new P/E
            self.earnings_per_share = round(self.price / self.pe_ratio, 2)

    def get_debt_multiplier(self) -> float:
        """Returns crisis sensitivity multiplier based on debt level"""
        return {"Low": 0.8, "Medium": 1.0, "High": 1.4}[self.debt_level]

    def get_valuation_status(self) -> str:
        """Returns whether stock appears undervalued, fair, or overvalued"""
        # Compare P/E to growth (simplified PEG ratio concept)
        if self.growth_rate <= 0:
            if self.pe_ratio > 20:
                return "Overvalued"
            return "Fair"

        peg = self.pe_ratio / (self.growth_rate * 100)  # PEG ratio
        if peg < 1.0:
            return "Undervalued"
        elif peg > 2.0:
            return "Overvalued"
        return "Fair"

    def update_price(self, base_change: float, regime_mult: Dict, algo_pressure: float,
                     psychology: Any, hidden_factors: Any):
        """Advanced price update with valuation metrics"""

        # 1. Apply regime effects
        change = base_change * regime_mult["news_sensitivity"]
        change += regime_mult["trend_strength"] * self.trend_long

        # 2. Add algorithmic trading pressure
        change += algo_pressure

        # 3. Growth rate provides a baseline drift (per turn, so divide annual by ~50 turns)
        growth_per_turn = self.growth_rate / 50
        change += growth_per_turn

        # 4. Psychology effects (dampened to avoid extreme swings)
        psych_multiplier = 1.0
        if psychology.fear_greed_index > 80:  # Extreme greed
            psych_multiplier = 1.15 if change > 0 else 0.85
        elif psychology.fear_greed_index < 20:  # Extreme fear
            psych_multiplier = 0.85 if change > 0 else 1.25

        change *= psych_multiplier

        # 5. Debt level affects downside (high debt = bigger drops)
        if change < 0:
            change *= self.get_debt_multiplier()

        # 6. Hidden value reversion (weak force)
        if self.name in hidden_factors.true_values:
            true_value = hidden_factors.true_values[self.name]
            value_gap = (true_value - self.price) / self.price
            reversion_force = value_gap * regime_mult["mean_reversion"] * 0.02
            change += reversion_force

        # 7. Volatility and randomness
        random_shock = random.gauss(0, self.volatility * regime_mult["volatility_mult"])
        change += random_shock

        # 8. Herd behavior at high strength (dampened)
        if psychology.herd_strength > 0.7:
            change *= (1 + (psychology.herd_strength - 0.7) * 0.5)

        # 9. Clamp max daily change to ±8% and apply
        change = max(-0.08, min(0.08, change))
        old_price = self.price
        self.price = max(1, round(self.price * (1 + change), 2))
        self.price_history.append(self.price)

        # 10. Update P/E ratio (price changed, earnings grow slowly)
        # Earnings grow at growth_rate per turn
        self.earnings_per_share *= (1 + growth_per_turn)
        if self.earnings_per_share > 0:
            self.pe_ratio = round(self.price / self.earnings_per_share, 1)
            self.pe_ratio = max(3, min(100, self.pe_ratio))  # Clamp to reasonable range

        # 11. Update volume (spikes on big moves)
        volume = 1.0 + abs(change) * 10
        self.volume_history.append(volume)

        # 12. Update derived metrics
        self._update_metrics()

        return change

    def _update_metrics(self):
        """Update technical indicators"""
        if len(self.price_history) >= 10:
            # Momentum score
            short_ma = np.mean(self.price_history[-5:])
            long_ma = np.mean(self.price_history[-10:])
            self.momentum_score = (short_ma - long_ma) / long_ma

            # Relative strength
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