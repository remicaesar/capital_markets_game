"""
Main market simulation with all systems integrated
"""

import random
import numpy as np
from typing import Dict, List, Any
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


class Market:
    def __init__(self):
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
        self.hidden_factors.initialize(self.companies)

    def _generate_companies(self):
        """Generate companies for each sector"""
        companies_per_sector = NUM_COMPANIES // len(SECTORS)
        extra = NUM_COMPANIES % len(SECTORS)

        for i, sector in enumerate(SECTORS):
            count = companies_per_sector + (1 if i < extra else 0)
            available_names = COMPANY_NAMES[sector].copy()

            for j in range(count):
                name = available_names[j] if j < len(available_names) else f"{sector}Corp{j + 1}"
                price = round(random.uniform(20, 150), 2)
                trend_long = random.choice([-1, 1])

                self.companies[name] = Company(name, sector, price, trend_long)

    def get_market_cap(self) -> float:
        """Calculate total market capitalization"""
        return sum(c.price for c in self.companies.values())

    def get_market_return(self) -> float:
        """Calculate market return for this turn"""
        if len(self.market_history) < 2:
            return 0.0
        return (self.market_history[-1] - self.market_history[-2]) / self.market_history[-2]

    def _apply_sector_correlations(self, sector_impacts: Dict[str, float]):
        """Apply correlations between sectors"""
        for (s1, s2), correlation in SECTOR_CORRELATIONS.items():
            if s1 in sector_impacts and sector_impacts[s1] != 0:
                sector_impacts[s2] = sector_impacts.get(s2, 0) + sector_impacts[s1] * correlation
            if s2 in sector_impacts and sector_impacts[s2] != 0:
                sector_impacts[s1] = sector_impacts.get(s1, 0) + sector_impacts[s2] * correlation

    def _process_smart_money(self) -> Dict[str, float]:
        """Smart money trades before news becomes public"""
        impacts = {}
        for company, action in self.hidden_factors.smart_money_positions.items():
            if action == "accumulating":
                impacts[company] = random.uniform(0.01, 0.03)
            else:  # distributing
                impacts[company] = random.uniform(-0.03, -0.01)
        return impacts

    def advance_turn(self, player):
        """Complex turn advancement with all systems"""

        # Track initial market cap
        initial_cap = self.get_market_cap()

        # 1. Check for regime change
        regime_msg = self.regime.check_regime_change(self.return_history,
                                                     np.std(self.return_history[-5:]) if len(
                                                         self.return_history) >= 5 else 0.02)

        # 2. Process smart money movements (hidden)
        smart_money_impacts = self._process_smart_money()

        # 3. Generate and process news
        displayed_events = []
        sector_impacts = {s: 0.0 for s in SECTORS}
        market_impact = 0.0

        # Generate 3-5 ambiguous news items (increased frequency)
        num_news = random.randint(3, 5)
        for _ in range(num_news):
            headline, interpretations = self.news_system.generate_news()

            # Choose interpretation based on probabilities and regime
            rand = random.random()
            cumulative = 0.0
            chosen_interp = None

            for interp in interpretations:
                # Adjust probability based on market psychology
                adj_prob = interp["prob"]
                if self.psychology.fear_greed_index < 30 and interp["effect"] < 0:
                    adj_prob *= 1.3  # Bad news more likely in fearful market
                elif self.psychology.fear_greed_index > 70 and interp["effect"] > 0:
                    adj_prob *= 1.3  # Good news more likely in greedy market

                cumulative += adj_prob
                if rand < cumulative:
                    chosen_interp = interp
                    break

            if not chosen_interp:
                chosen_interp = interpretations[-1]

            # Apply the interpretation
            if chosen_interp["delay"] == 0:
                if chosen_interp["sectors"]:
                    for sector in chosen_interp["sectors"]:
                        sector_impacts[sector] += chosen_interp["effect"]
                else:
                    market_impact += chosen_interp["effect"]

            # Always add the headline to displayed events
            displayed_events.append(headline)
            
        # Ensure we always have at least one news item
        if not displayed_events:
            headline, interpretations = self.news_system.generate_news()
            displayed_events.append(headline)

        # 4. Check for crisis events
        crisis = self.crisis_system.check_for_crisis(self.psychology, self.regime.current)
        if crisis:
            displayed_events.insert(0, crisis["headline"])
            # Apply crisis impact
            for company in self.companies.values():
                impact = random.uniform(crisis["min_impact"], crisis["max_impact"])
                # Higher beta = more crisis impact
                impact *= (0.5 + company.beta / 2)
                sector_impacts[company.sector] += impact

            self.crisis_system.active_crises.append({
                "crisis": crisis,
                "remaining_duration": crisis["duration"]
            })

        # 5. Process ongoing crises
        for active in self.crisis_system.active_crises[:]:
            active["remaining_duration"] -= 1
            if active["remaining_duration"] <= 0:
                # Crisis ending, partial recovery
                recovery = active["crisis"]["recovery_rate"]
                for company in self.companies.values():
                    sector_impacts[company.sector] += recovery * 0.1
                self.crisis_system.active_crises.remove(active)
                displayed_events.append(f"📈 Markets stabilize as {active['crisis']['name']} crisis abates")

        # 6. Apply sector correlations
        self._apply_sector_correlations(sector_impacts)

        # 7. Update each company
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
                                          self.psychology, self.hidden_factors)
            company_changes[company.name] = change

        # 8. Update market tracking
        self.market_history.append(self.get_market_cap())
        market_return = self.get_market_return()
        self.return_history.append(market_return)

        # 9. Update psychology
        market_volatility = np.std([c for c in company_changes.values()])
        self.psychology.update(market_return, market_volatility, self.regime.current)

        # 10. Update hidden factors
        # Rotate smart money positions occasionally
        if random.random() < 0.2:
            # Remove one position
            if self.hidden_factors.smart_money_positions:
                to_remove = random.choice(list(self.hidden_factors.smart_money_positions.keys()))
                del self.hidden_factors.smart_money_positions[to_remove]

            # Add new position
            company = random.choice(list(self.companies.keys()))
            if company not in self.hidden_factors.smart_money_positions:
                action = "accumulating" if random.random() > 0.5 else "distributing"
                self.hidden_factors.smart_money_positions[company] = action

        # 11. Return events for display
        if regime_msg:
            displayed_events.insert(0, regime_msg)

        # 12. Update difficulty based on player skill
        self._adjust_difficulty(player)

        self.turn += 1
        
        return displayed_events[:5]  # Return up to 5 news events

    def _adjust_difficulty(self, player):
        """Dynamically adjust difficulty based on player performance"""
        skill_mult = 0.5 + player.skill_rating

        # Adjust algo trading intensity
        self.algos.momentum_strength = min(1.0, 0.3 * skill_mult)
        self.algos.contrarian_strength = min(1.0, 0.3 * skill_mult)
        self.algos.arb_strength = min(0.5, 0.2 * skill_mult) 