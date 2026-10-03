"""
Main market simulation with all systems integrated
"""

import random
import secrets
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.columns import Columns

from config.settings import NUM_COMPANIES, SECTORS, SECTOR_CORRELATIONS, TRANSACTION_FEE
from config.company_data import COMPANY_NAMES
from models.company import Company
from models.market_regime import MarketRegime
from systems.psychology import MarketPsychology
from systems.hidden_factors import HiddenFactors
from systems.algorithmic_trading import AlgorithmicTraders
from systems.news_system import AdvancedNewsSystem
from systems.crisis_events import CrisisEventSystem

console = Console()


def new_game_rng(seed: Optional[int] = None) -> Tuple[int, random.Random]:
    """Return the seed a game plays from (a fresh one when none is given) and its rng."""
    if seed is None:
        seed = secrets.randbelow(2**31)
    return seed, random.Random(seed)


class Market:
    def __init__(self, rng: Optional[random.Random] = None):
        # Every draw this game makes comes from its own rng, never the process-wide
        # `random` state: concurrent web games would otherwise disturb each other, and
        # a save could not carry the exact stream the game was playing from.
        self.rng = rng if rng is not None else random.Random()
        self.companies: Dict[str, Company] = {}
        self.turn = 1
        self.market_history: List[float] = []
        self.return_history: List[float] = []

        # Advanced systems
        self.regime = MarketRegime()
        self.hidden_factors = HiddenFactors()
        self.psychology = MarketPsychology()
        self.algos = AlgorithmicTraders()
        self.news_system = AdvancedNewsSystem()
        self.crisis_system = CrisisEventSystem()

        # Initialize
        self._generate_companies()
        self.hidden_factors.initialize(self.companies, self.rng)

    def _generate_companies(self):
        """Generate companies for each sector"""
        companies_per_sector = NUM_COMPANIES // len(SECTORS)
        extra = NUM_COMPANIES % len(SECTORS)

        for i, sector in enumerate(SECTORS):
            count = companies_per_sector + (1 if i < extra else 0)
            available_names = COMPANY_NAMES[sector].copy()

            for j in range(count):
                name = available_names[j] if j < len(available_names) else f"{sector}Corp{j + 1}"
                price = round(self.rng.uniform(20, 150), 2)
                trend_long = self.rng.choice([-1, 1])

                self.companies[name] = Company(name, sector, price, trend_long, rng=self.rng)

    def get_market_cap(self) -> float:
        """Calculate total market capitalization"""
        return sum(c.price for c in self.companies.values())

    def get_market_return(self) -> float:
        """Calculate market return for this turn"""
        if len(self.market_history) < 2:
            return 0.0
        return (self.market_history[-1] - self.market_history[-2]) / self.market_history[-2]

    def _apply_sector_correlations(self, sector_impacts: Dict[str, float]):
        """Apply correlations between sectors using original impacts (no feedback)"""
        original = dict(sector_impacts)
        for (s1, s2), correlation in SECTOR_CORRELATIONS.items():
            if s1 in original and original[s1] != 0:
                sector_impacts[s2] = sector_impacts.get(s2, 0) + original[s1] * correlation
            if s2 in original and original[s2] != 0:
                sector_impacts[s1] = sector_impacts.get(s1, 0) + original[s2] * correlation

    def _process_smart_money(self) -> Dict[str, float]:
        """Smart money trades before news becomes public"""
        impacts = {}
        for company, action in self.hidden_factors.smart_money_positions.items():
            if action == "accumulating":
                impacts[company] = self.rng.uniform(0.01, 0.03)
            else:  # distributing
                impacts[company] = self.rng.uniform(-0.03, -0.01)
        return impacts

    def advance_turn(self, player):
        """Turn advancement with clear, understandable events"""

        # Track initial market cap
        initial_cap = self.get_market_cap()

        # 1. Check for regime change
        regime_msg = self.regime.check_regime_change(self.return_history,
                                                     np.std(self.return_history[-5:]) if len(
                                                         self.return_history) >= 5 else 0.02)

        # 2. Process smart money movements (hidden)
        smart_money_impacts = self._process_smart_money()

        # 3. Generate and process news (simplified: 1-2 clear events)
        displayed_events = []
        sector_impacts = {s: 0.0 for s in SECTORS}
        market_impact = 0.0

        # Generate 1-2 news events with clear effects
        news_events = self.news_system.generate_turn_news(self.regime.current, self.psychology,
                                                           self.rng)

        for event in news_events:
            # Apply the effect directly - no hidden interpretations
            if event.sector:
                sector_impacts[event.sector] += event.effect
            else:
                market_impact += event.effect

            # Show headline with context so players understand what happened
            displayed_events.append(f"{event.headline}")
            displayed_events.append(f"  → {event.context}")

        # 4. Check for crisis warning (visible to player)
        warning = self.crisis_system.get_warning(self.regime.current, self.return_history)
        if warning:
            displayed_events.append(f"⚠️ WARNING: {warning.message}")

        # 5. Check for crisis events
        crisis = self.crisis_system.check_for_crisis(self.regime.current, self.return_history,
                                                    self.rng)
        if crisis:
            displayed_events.insert(0, f"🚨 {crisis.headline}")
            displayed_events.insert(1, f"  → {crisis.context}")
            # Apply crisis impact to all companies
            for company in self.companies.values():
                impact = crisis.impact * (0.5 + company.beta / 2)
                sector_impacts[company.sector] += impact

        # 6. Process ongoing crisis and check for recovery
        recovery_msg = self.crisis_system.process_active_crisis()
        if recovery_msg:
            displayed_events.append(f"📈 {recovery_msg}")

        # Add ongoing crisis impact
        ongoing_impact = self.crisis_system.get_crisis_impact()
        if ongoing_impact != 0:
            market_impact += ongoing_impact
            displayed_events.append(f"⚠️ Crisis ongoing: market under pressure ({ongoing_impact*100:.1f}%)")

        # 8. Apply sector correlations
        self._apply_sector_correlations(sector_impacts)

        # 9. Update each company
        company_changes = {}
        regime_params = self.regime.REGIMES[self.regime.current]

        for company in self.companies.values():
            # Get algorithmic trading pressure
            market_data = {
                "true_values": self.hidden_factors.true_values,
                "regime": self.regime.current
            }
            algo_pressure = self.algos.get_pressure(company, market_data)

            # Smart money impact (if any)
            if company.name in smart_money_impacts:
                algo_pressure += smart_money_impacts[company.name]

            # Base change from news and sector
            base_change = sector_impacts.get(company.sector, 0) + market_impact

            # Update price with all factors
            change = company.update_price(base_change, regime_params, algo_pressure,
                                          self.psychology, self.hidden_factors, self.rng)
            company_changes[company.name] = change

        # 10. Update market tracking
        self.market_history.append(self.get_market_cap())
        market_return = self.get_market_return()
        self.return_history.append(market_return)

        # 11. Update psychology
        market_volatility = np.std([c for c in company_changes.values()])
        self.psychology.update(market_return, market_volatility, self.regime.current, self.rng)

        # 12. Update hidden factors - rotate smart money positions occasionally
        if self.rng.random() < 0.2:
            if self.hidden_factors.smart_money_positions:
                to_remove = self.rng.choice(list(self.hidden_factors.smart_money_positions.keys()))
                del self.hidden_factors.smart_money_positions[to_remove]

            company = self.rng.choice(list(self.companies.keys()))
            if company not in self.hidden_factors.smart_money_positions:
                action = "accumulating" if self.rng.random() > 0.5 else "distributing"
                self.hidden_factors.smart_money_positions[company] = action

        # 13. Add regime change message at top if any
        if regime_msg:
            displayed_events.insert(0, regime_msg)

        # 14. Update difficulty based on player skill
        self._adjust_difficulty(player)

        self.turn += 1

        return displayed_events[:8]  # Show more events since we include context

    def _adjust_difficulty(self, player):
        """Dynamically adjust difficulty based on player performance"""
        skill_mult = 0.5 + player.skill_rating

        # Adjust algo trading intensity
        self.algos.momentum_strength = min(1.0, 0.3 * skill_mult)
        self.algos.contrarian_strength = min(1.0, 0.3 * skill_mult)
        self.algos.arb_strength = min(0.5, 0.2 * skill_mult) 