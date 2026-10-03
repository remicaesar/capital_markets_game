"""
Simplified crisis event system with visible warning signs
"""

import random
from typing import Optional, List
from dataclasses import dataclass, field


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
    impact: float  # Negative percentage
    duration: int  # Turns remaining
    context: str


class CrisisEventSystem:
    """Manages crisis events with visible buildup"""

    def __init__(self):
        self.active_crisis: Optional[Crisis] = None
        self.warning_level = 0  # 0-3, accumulates each turn
        self.turns_since_crisis = 0
        self.crisis_history: List[str] = []

    def get_warning(self, regime: str, recent_returns: List[float]) -> Optional[CrisisWarning]:
        """Check for warning signs - these are VISIBLE to players"""

        # No warnings during active crisis or right after one
        if self.active_crisis or self.turns_since_crisis < 5:
            return None

        warnings = []

        # Warning 1: Market has been too calm (complacency)
        if regime == "bull" and self.turns_since_crisis > 15:
            warnings.append(CrisisWarning(
                "Market complacency rising - extended bull run increases correction risk",
                severity=1
            ))

        # Warning 2: Volatility spiking
        if regime == "volatile":
            warnings.append(CrisisWarning(
                "Elevated volatility signals unstable conditions",
                severity=2
            ))

        # Warning 3: Sharp recent losses (panic building)
        if len(recent_returns) >= 3:
            recent_avg = sum(recent_returns[-3:]) / 3
            if recent_avg < -0.03:
                warnings.append(CrisisWarning(
                    "Sustained losses may trigger panic selling",
                    severity=2
                ))

        # Return the most severe warning if any
        if warnings:
            warning = max(warnings, key=lambda w: w.severity)
            self.warning_level = min(3, self.warning_level + warning.severity)
            return warning

        # Gradually reduce warning level in calm conditions
        self.warning_level = max(0, self.warning_level - 1)
        return None

    def check_for_crisis(self, regime: str, recent_returns: List[float],
                         rng: random.Random) -> Optional[Crisis]:
        """Check if a crisis triggers - probability based on visible warning level"""

        self.turns_since_crisis += 1

        # Can't have two crises at once
        if self.active_crisis:
            return None

        # Need some warning buildup first (makes crises feel earned, not random)
        if self.warning_level < 2:
            return None

        # Base probability scales with warning level
        crisis_prob = 0.05 * self.warning_level  # 10-15% at level 2-3

        if rng.random() > crisis_prob:
            return None

        # Determine crisis type based on conditions
        if regime == "volatile" or (len(recent_returns) >= 3 and sum(recent_returns[-3:]) / 3 < -0.02):
            # Market crash type
            crisis = Crisis(
                name="market_crash",
                headline="MARKET CRASH: Panic selling triggers broad market decline!",
                impact=rng.uniform(-0.12, -0.20),
                duration=2,
                context="Widespread fear causes investors to liquidate positions"
            )
        else:
            # Flash correction type (shorter, less severe)
            crisis = Crisis(
                name="flash_correction",
                headline="FLASH CORRECTION: Sudden selloff catches traders off guard!",
                impact=rng.uniform(-0.08, -0.15),
                duration=1,
                context="Algorithmic trading amplifies the downturn"
            )

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
        if self.active_crisis:
            # Diminishing impact as crisis progresses
            return self.active_crisis.impact * 0.5
        return 0.0
