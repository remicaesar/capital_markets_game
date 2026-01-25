"""
Simplified news system with clear cause-and-effect
"""

import random
from typing import Tuple, Dict, Optional
from config.settings import SECTORS


class NewsEvent:
    """A single news event with clear, predictable effects"""

    def __init__(self, headline: str, effect: float, sector: Optional[str] = None,
                 context: str = ""):
        self.headline = headline
        self.effect = effect  # Positive = good for stocks, negative = bad
        self.sector = sector  # None = affects whole market
        self.context = context  # Explains the impact to players


class AdvancedNewsSystem:
    """Generates clear news events that players can learn from"""

    # Sector-specific positive events
    POSITIVE_SECTOR_NEWS = {
        "Tech": [
            ("TechCore announces breakthrough AI chip", 0.06,
             "New technology drives investor optimism"),
            ("QuantumAI wins major government contract", 0.05,
             "Secured revenue boosts sector confidence"),
            ("Tech sector sees record consumer spending", 0.04,
             "Strong demand signals healthy growth"),
        ],
        "Energy": [
            ("Oil prices surge on supply concerns", 0.06,
             "Higher oil prices benefit energy producers"),
            ("SolarTech receives renewable energy subsidies", 0.05,
             "Government support improves profit outlook"),
            ("Cold weather forecast boosts energy demand", 0.04,
             "Increased consumption means higher revenues"),
        ],
        "Finance": [
            ("Fed signals interest rate stability", 0.05,
             "Stable rates support bank lending margins"),
            ("MegaBank reports strong loan growth", 0.06,
             "Healthy lending indicates economic strength"),
            ("Credit markets show improved liquidity", 0.04,
             "Easier borrowing conditions help financials"),
        ],
        "Retail": [
            ("Holiday shopping season exceeds expectations", 0.06,
             "Consumer spending drives retail profits"),
            ("E-Tail expands same-day delivery nationwide", 0.05,
             "Service improvements attract more customers"),
            ("Consumer confidence hits 12-month high", 0.04,
             "Optimistic consumers spend more freely"),
        ],
        "Healthcare": [
            ("PharmaCorp drug receives FDA approval", 0.07,
             "New drug opens significant revenue stream"),
            ("BioLabs clinical trial shows positive results", 0.06,
             "Promising data raises acquisition interest"),
            ("Healthcare spending bill passes Congress", 0.05,
             "Increased funding benefits entire sector"),
        ],
    }

    # Sector-specific negative events
    NEGATIVE_SECTOR_NEWS = {
        "Tech": [
            ("Major data breach reported at tech firm", -0.06,
             "Security concerns trigger selloff"),
            ("Antitrust investigation announced", -0.05,
             "Regulatory scrutiny weighs on valuations"),
            ("Chip shortage disrupts production", -0.04,
             "Supply issues hurt near-term earnings"),
        ],
        "Energy": [
            ("Oil prices drop on oversupply fears", -0.06,
             "Lower prices squeeze producer margins"),
            ("Renewable subsidy cuts announced", -0.05,
             "Reduced support impacts profitability"),
            ("Mild weather reduces heating demand", -0.04,
             "Lower consumption hurts revenues"),
        ],
        "Finance": [
            ("Fed hints at aggressive rate hikes", -0.06,
             "Rising rates may slow loan demand"),
            ("Major bank reports loan defaults rising", -0.05,
             "Credit quality concerns spread to sector"),
            ("Banking regulations to tighten", -0.04,
             "New rules may reduce profit margins"),
        ],
        "Retail": [
            ("Consumer spending drops unexpectedly", -0.06,
             "Weak demand signals trouble ahead"),
            ("Shipping costs surge on fuel prices", -0.05,
             "Higher costs eat into profit margins"),
            ("Retail theft reaches record levels", -0.04,
             "Shrinkage hurts store profitability"),
        ],
        "Healthcare": [
            ("Drug pricing legislation advances", -0.06,
             "Price caps threaten pharma revenues"),
            ("Clinical trial fails to meet endpoints", -0.07,
             "Failed trial eliminates expected revenue"),
            ("Medicare reimbursement cuts proposed", -0.05,
             "Lower payments reduce sector income"),
        ],
    }

    # Market-wide events (affect all sectors)
    MARKET_WIDE_NEWS = [
        # Positive
        ("Economic growth exceeds expectations", 0.04,
         "Strong GDP lifts all sectors"),
        ("Inflation data comes in lower than expected", 0.03,
         "Easing inflation supports stock valuations"),
        ("Trade deal reached with major partner", 0.04,
         "Reduced tariffs benefit exporters"),
        ("Unemployment drops to multi-year low", 0.03,
         "Strong job market boosts consumer spending"),
        # Negative
        ("Recession fears grow on weak data", -0.05,
         "Economic slowdown concerns trigger selling"),
        ("Inflation spikes above forecasts", -0.04,
         "Rising prices may force rate hikes"),
        ("Geopolitical tensions escalate", -0.04,
         "Uncertainty drives investors to safety"),
        ("Major hedge fund liquidates positions", -0.03,
         "Forced selling pressures prices"),
    ]

    def generate_news(self) -> Tuple[str, Dict]:
        """Generate a single clear news event with context"""

        # 60% chance sector-specific, 40% market-wide
        if random.random() < 0.6:
            sector = random.choice(SECTORS)
            # 50/50 positive or negative
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
        events = []

        # Always generate 1 event
        events.append(self.generate_news())

        # 40% chance of a second event
        if random.random() < 0.4:
            events.append(self.generate_news())

        return events
