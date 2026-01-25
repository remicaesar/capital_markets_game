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
    volatility: float = field(default_factory=lambda: random.uniform(0.02, 0.08))
    beta: float = field(default_factory=lambda: random.uniform(0.6, 1.8))
    trend_short: int = 0
    price_history: List[float] = field(default_factory=list)
    volume_history: List[float] = field(default_factory=list)

    # Advanced metrics
    momentum_score: float = 0.0
    relative_strength: float = 50.0
    earnings_momentum: float = 0.0

    def __post_init__(self):
        self.price_history.append(self.price)
        self.volume_history.append(1.0)  # Normalized volume

    def update_price(self, base_change: float, regime_mult: Dict, algo_pressure: float,
                     psychology: Any, hidden_factors: Any):
        """Advanced price update with all factors"""

        # 1. Apply regime effects
        change = base_change * regime_mult["news_sensitivity"]
        change += regime_mult["trend_strength"] * self.trend_long

        # 2. Add algorithmic trading pressure
        change += algo_pressure

        # 3. Psychology effects
        psych_multiplier = 1.0
        if psychology.fear_greed_index > 80:  # Extreme greed
            psych_multiplier = 1.3 if change > 0 else 0.7
        elif psychology.fear_greed_index < 20:  # Extreme fear
            psych_multiplier = 0.7 if change > 0 else 1.5

        change *= psych_multiplier

        # 4. Hidden value reversion (weak force)
        if self.name in hidden_factors.true_values:
            true_value = hidden_factors.true_values[self.name]
            value_gap = (true_value - self.price) / self.price
            reversion_force = value_gap * regime_mult["mean_reversion"] * 0.02
            change += reversion_force

        # 5. Volatility and randomness
        random_shock = random.gauss(0, self.volatility * regime_mult["volatility_mult"])
        change += random_shock

        # 6. Herd behavior at high strength
        if psychology.herd_strength > 0.7:
            change *= (1 + psychology.herd_strength - 0.7)

        # 7. Apply the change
        self.price = max(1, round(self.price * (1 + change), 2))
        self.price_history.append(self.price)

        # 8. Update volume (spikes on big moves)
        volume = 1.0 + abs(change) * 10
        self.volume_history.append(volume)

        # 9. Update derived metrics
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