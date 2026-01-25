"""
Crisis event management system
"""

import random
from typing import Dict, List, Optional, Any


class CrisisEventSystem:
    """Manages rare but impactful crisis events"""

    CRISIS_EVENTS = [
        {
            "name": "flash_crash",
            "headline": "⚡ FLASH CRASH: Algorithmic cascade triggers market meltdown!",
            "min_impact": -0.15,
            "max_impact": -0.35,
            "duration": 1,
            "recovery_rate": 0.4,
            "trigger_condition": lambda psych, regime: psych.complacency > 0.7 and regime == "bull"
        },
        {
            "name": "liquidity_crisis",
            "headline": "💸 LIQUIDITY CRISIS: Credit markets freeze as counterparty risk soars!",
            "min_impact": -0.10,
            "max_impact": -0.25,
            "duration": 3,
            "recovery_rate": 0.15,
            "trigger_condition": lambda psych, regime: psych.fear_greed_index < 20 and regime == "bear"
        },
        {
            "name": "sector_scandal",
            "headline": "🚨 SCANDAL: Major fraud discovered in {sector} sector!",
            "min_impact": -0.20,
            "max_impact": -0.40,
            "duration": 5,
            "recovery_rate": 0.1,
            "trigger_condition": lambda psych, regime: random.random() < 0.1  # Random
        },
        {
            "name": "geopolitical_shock",
            "headline": "🌐 GEOPOLITICAL CRISIS: Global uncertainty spikes on international tensions!",
            "min_impact": -0.08,
            "max_impact": -0.20,
            "duration": 2,
            "recovery_rate": 0.25,
            "trigger_condition": lambda psych, regime: regime == "volatile"
        }
    ]

    def __init__(self):
        self.active_crises = []
        self.crisis_history = []

    def check_for_crisis(self, psychology: Any, regime: str) -> Optional[Dict]:
        """Check if a crisis should trigger"""
        from config.settings import BASE_CRISIS_PROBABILITY
        
        for crisis in self.CRISIS_EVENTS:
            if crisis["trigger_condition"](psychology, regime) and random.random() < BASE_CRISIS_PROBABILITY:
                return crisis
        return None 