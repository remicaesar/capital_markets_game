"""
Market regime system that affects all trading dynamics
"""

import random
import numpy as np
from dataclasses import dataclass
from typing import List, Optional


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

    def check_regime_change(self, market_returns: List[float], volatility: float) -> Optional[str]:
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