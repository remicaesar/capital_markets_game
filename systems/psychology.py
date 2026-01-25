"""
Market psychology and sentiment tracking
"""

import random
from dataclasses import dataclass


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