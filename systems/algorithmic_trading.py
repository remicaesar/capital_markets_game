"""
Algorithmic trading simulation with different strategies
"""

import numpy as np
from typing import Dict, List, Any


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