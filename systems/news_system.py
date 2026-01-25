"""
Advanced news system with ambiguous interpretations
"""

import random
from typing import Tuple, List, Dict, Any

from config.settings import SECTORS


class AdvancedNewsSystem:
    """Generates ambiguous news with multiple interpretations"""

    AMBIGUOUS_NEWS_TEMPLATES = [
        {
            "headline": "📊 Fed signals '{policy}' approach to monetary policy",
            "interpretations": [
                {"effect": 0.05, "prob": 0.3, "sectors": ["Finance"], "delay": 0},
                {"effect": -0.04, "prob": 0.3, "sectors": ["Tech"], "delay": 1},
                {"effect": 0.0, "prob": 0.4, "sectors": None, "delay": 0}
            ]
        },
        {
            "headline": "🏛️ New regulations '{impact}' for {sector} sector",
            "interpretations": [
                {"effect": -0.06, "prob": 0.4, "sectors": ["{sector}"], "delay": 0},
                {"effect": 0.04, "prob": 0.3, "sectors": ["{sector}"], "delay": 2},  # Moat building
                {"effect": 0.02, "prob": 0.3, "sectors": ["Finance"], "delay": 1}
            ]
        },
        {
            "headline": "🌍 {region} markets show '{signal}' signals",
            "interpretations": [
                {"effect": 0.06, "prob": 0.25, "sectors": ["Energy", "Retail"], "delay": 0},
                {"effect": -0.05, "prob": 0.25, "sectors": ["Energy", "Retail"], "delay": 0},
                {"effect": 0.03, "prob": 0.25, "sectors": ["Finance"], "delay": 1},
                {"effect": -0.02, "prob": 0.25, "sectors": ["Tech"], "delay": 1}
            ]
        },
        {
            "headline": "💼 Major {sector} company reports '{result}' earnings",
            "interpretations": [
                {"effect": 0.08, "prob": 0.2, "sectors": ["{sector}"], "delay": 0},
                {"effect": 0.02, "prob": 0.3, "sectors": ["{sector}"], "delay": 0},
                {"effect": -0.04, "prob": 0.3, "sectors": ["{sector}"], "delay": 1},  # Sell the news
                {"effect": 0.0, "prob": 0.2, "sectors": None, "delay": 0}
            ]
        }
    ]

    def generate_news(self) -> Tuple[str, List[Dict]]:
        """Generate ambiguous news event"""
        template = random.choice(self.AMBIGUOUS_NEWS_TEMPLATES)

        # Fill in placeholders
        placeholders = {
            "policy": random.choice(["hawkish", "dovish", "data-dependent", "flexible"]),
            "impact": random.choice(["challenging", "transformative", "mixed implications", "uncertain"]),
            "sector": random.choice(SECTORS),
            "region": random.choice(["Asian", "European", "Emerging", "Developed"]),
            "signal": random.choice(["mixed", "concerning", "improving", "divergent"]),
            "result": random.choice(["surprising", "mixed", "above-consensus", "complex"])
        }

        headline = template["headline"]
        for key, value in placeholders.items():
            headline = headline.replace(f"{{{key}}}", value)

        # Process interpretations
        interpretations = []
        for interp in template["interpretations"]:
            processed = interp.copy()
            if processed["sectors"] and "{sector}" in processed["sectors"][0]:
                processed["sectors"] = [placeholders["sector"]]
            interpretations.append(processed)

        return headline, interpretations 