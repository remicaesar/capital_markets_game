"""
Hidden information system that affects prices
"""

import random
from dataclasses import dataclass, field
from typing import Dict, List, Any


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