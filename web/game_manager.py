"""
Game session management for the web UI
"""

import uuid
import random
import numpy as np
from typing import Dict, Optional, Tuple, List, Any
from dataclasses import dataclass

from models.market import Market
from models.player import Player
from config.settings import MAX_TURNS, TRANSACTION_FEE
from utils.save_manager import (
    save_game, load_game, deserialize_game_state, list_saves
)


@dataclass
class GameSession:
    """Holds a game session's state"""
    game_id: str
    market: Market
    player: Player
    seed: Optional[int]
    news_history: List[str]


class GameManager:
    """Manages multiple game sessions"""

    def __init__(self):
        self.sessions: Dict[str, GameSession] = {}

    def _initialize_random(self, seed: Optional[int] = None) -> int:
        """Initialize random number generators with seed"""
        if seed is None:
            seed = random.randint(0, 2**31 - 1)
        random.seed(seed)
        np.random.seed(seed)
        return seed

    def create_game(self, seed: Optional[int] = None) -> Tuple[str, GameSession]:
        """Create a new game session"""
        game_id = str(uuid.uuid4())[:8]
        actual_seed = self._initialize_random(seed)

        market = Market()
        player = Player()

        session = GameSession(
            game_id=game_id,
            market=market,
            player=player,
            seed=actual_seed,
            news_history=[]
        )

        self.sessions[game_id] = session
        return game_id, session

    def get_session(self, game_id: str) -> Optional[GameSession]:
        """Get a game session by ID"""
        return self.sessions.get(game_id)

    def delete_session(self, game_id: str) -> bool:
        """Delete a game session"""
        if game_id in self.sessions:
            del self.sessions[game_id]
            return True
        return False

    def get_game_state(self, session: GameSession) -> Dict[str, Any]:
        """Convert game state to API response format"""
        market = session.market
        player = session.player

        # Build company list
        companies = []
        for name, company in sorted(market.companies.items()):
            companies.append({
                "name": company.name,
                "sector": company.sector,
                "price": round(company.price, 2),
                "change_pct": round(company.get_change_pct() * 100, 2),
                "rsi": round(company.relative_strength, 1),
                "momentum": round(company.momentum_score * 100, 2),
                "volume": round(company.volume_history[-1] if company.volume_history else 1.0, 2),
                "trend": company.get_trend_indicator(),
                "beta": round(company.beta, 2)
            })

        # Build portfolio positions
        portfolio = []
        for name, (shares, avg_price) in player.portfolio.items():
            current_price = market.companies[name].price
            value = current_price * shares
            pnl = (current_price - avg_price) * shares
            pnl_pct = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
            portfolio.append({
                "company": name,
                "shares": shares,
                "avg_price": round(avg_price, 2),
                "current_price": round(current_price, 2),
                "value": round(value, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2)
            })

        # Build short positions
        short_positions = []
        for name, (shares, borrow_price) in player.short_positions.items():
            current_price = market.companies[name].price
            value = current_price * shares
            pnl = (borrow_price - current_price) * shares
            pnl_pct = ((borrow_price - current_price) / borrow_price * 100) if borrow_price > 0 else 0
            short_positions.append({
                "company": name,
                "shares": shares,
                "borrow_price": round(borrow_price, 2),
                "current_price": round(current_price, 2),
                "value": round(value, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2)
            })

        # Player stats
        player_stats = {
            "cash": round(player.cash, 2),
            "portfolio_value": round(player.portfolio_value(market), 2),
            "short_value": round(player.short_position_value(market), 2),
            "short_pnl": round(player.short_position_pnl(market), 2),
            "net_worth": round(player.net_worth(market), 2),
            "total_return_pct": round(player.total_return_pct(market), 2),
            "sharpe_ratio": round(player.calculate_sharpe_ratio(), 2),
            "max_drawdown": round(player.calculate_max_drawdown(), 2),
            "trade_count": player.trade_count,
            "total_fees_paid": round(player.total_fees_paid, 2),
            "total_slippage_paid": round(player.total_slippage_paid, 2),
            "total_borrow_fees_paid": round(player.total_borrow_fees_paid, 2),
            "margin_calls_received": player.margin_calls_received,
            "available_margin": round(player.available_margin(market), 2)
        }

        # Psychology
        psychology = {
            "fear_greed_index": round(market.psychology.fear_greed_index, 1),
            "herd_strength": round(market.psychology.herd_strength * 100, 1),
            "complacency": round(market.psychology.complacency * 100, 1),
            "capitulation_risk": round(market.psychology.capitulation_risk * 100, 1),
            "sentiment": market.psychology.get_sentiment_emoji()
        }

        return {
            "turn": market.turn,
            "max_turns": MAX_TURNS,
            "regime": market.regime.current,
            "companies": companies,
            "portfolio": portfolio,
            "short_positions": short_positions,
            "player": player_stats,
            "psychology": psychology,
            "news": session.news_history[-5:],  # Last 5 news items
            "game_over": market.turn > MAX_TURNS
        }

    def execute_action(self, session: GameSession, action: str, company_name: str, shares: int) -> Tuple[bool, str]:
        """Execute a trading action"""
        market = session.market
        player = session.player

        if company_name not in market.companies:
            return False, f"Company '{company_name}' not found"

        company = market.companies[company_name]

        # Redirect console output to capture messages
        import io
        import sys
        from contextlib import redirect_stdout

        # Temporarily suppress rich console output
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        try:
            if action == "buy":
                max_shares = int(player.cash // (company.price * (1 + TRANSACTION_FEE)))
                if shares > max_shares:
                    return False, f"Cannot afford {shares} shares. Max affordable: {max_shares}"
                success = player.buy(market, company, shares)
                if success:
                    return True, f"Bought {shares} shares of {company_name} at ${company.price:.2f}"
                return False, "Purchase failed - insufficient funds"

            elif action == "sell":
                if company_name not in player.portfolio:
                    return False, f"You don't own any {company_name} shares"
                owned = player.portfolio[company_name][0]
                if shares > owned:
                    return False, f"You only own {owned} shares of {company_name}"
                success = player.sell(market, company, shares)
                if success:
                    return True, f"Sold {shares} shares of {company_name}"
                return False, "Sale failed"

            elif action == "short":
                if company_name in player.portfolio:
                    return False, "Cannot short a stock you own. Sell your long position first."
                available_margin = player.available_margin(market)
                margin_per_share = company.price * 0.5
                fee_per_share = company.price * 0.015
                cost_per_share = margin_per_share + fee_per_share
                max_shares = int(available_margin // cost_per_share) if cost_per_share > 0 else 0
                if shares > max_shares:
                    return False, f"Insufficient margin. Max shortable: {max_shares}"
                success = player.short(market, company, shares)
                if success:
                    return True, f"Shorted {shares} shares of {company_name} at ${company.price:.2f}"
                return False, "Short failed - insufficient margin"

            elif action == "cover":
                if company_name not in player.short_positions:
                    return False, f"You don't have a short position in {company_name}"
                shorted = player.short_positions[company_name][0]
                if shares > shorted:
                    return False, f"You only have {shorted} shares shorted"
                success = player.cover(market, company, shares)
                if success:
                    return True, f"Covered {shares} shares of {company_name}"
                return False, "Cover failed - insufficient funds"

            else:
                return False, f"Unknown action: {action}"

        finally:
            sys.stdout = old_stdout

    def advance_turn(self, session: GameSession) -> Tuple[List[str], bool, Optional[Dict[str, Any]]]:
        """
        Advance the game by one turn.
        Returns: (news_events, game_over, final_stats)
        """
        market = session.market
        player = session.player

        # Suppress console output during turn processing
        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        try:
            # End of turn processing
            player.collect_dividends(market)
            player.pay_borrow_fees(market)
            player.update_metrics(market)

            # Check for margin calls
            margin_call_events = player.check_margin_call(market)

            # Advance turn and get news
            # Allow advancing through turn 50 (the last playable turn)
            if market.turn <= MAX_TURNS:
                news_events = market.advance_turn(player)
            else:
                news_events = []

            # Add margin call events to news
            if margin_call_events:
                news_events = margin_call_events + news_events

            # Store news history
            session.news_history.extend(news_events)

            # Check for game over (game ends after turn 50 advances to turn 51)
            game_over = market.turn > MAX_TURNS
            final_stats = None

            if game_over:
                final_stats = self._calculate_final_stats(market, player, session.seed)

            return news_events, game_over, final_stats

        finally:
            sys.stdout = old_stdout

    def _calculate_final_stats(self, market: Market, player: Player, seed: Optional[int]) -> Dict[str, Any]:
        """Calculate final game statistics"""
        worth = player.net_worth(market)
        ret = player.total_return_pct(market)
        sharpe = player.calculate_sharpe_ratio()
        max_dd = player.calculate_max_drawdown()

        # Market return for comparison
        initial_cap = sum(c.price_history[0] for c in market.companies.values())
        final_cap = market.get_market_cap()
        market_return = ((final_cap - initial_cap) / initial_cap) * 100

        alpha = ret - market_return

        # Performance rating
        if sharpe > 2.0 and alpha > 20:
            rating = "LEGENDARY"
            message = "You've mastered the markets!"
        elif sharpe > 1.5 and alpha > 10:
            rating = "EXPERT"
            message = "Outstanding risk-adjusted returns!"
        elif sharpe > 1.0 and alpha > 0:
            rating = "SKILLED"
            message = "You beat the market!"
        elif sharpe > 0.5:
            rating = "SOLID"
            message = "Positive risk-adjusted returns."
        elif ret > 0:
            rating = "BREAKEVEN"
            message = "Room for improvement."
        else:
            rating = "LEARNING"
            message = "The market humbled you. Study and try again."

        return {
            "final_net_worth": round(worth, 2),
            "total_return_pct": round(ret, 2),
            "market_return_pct": round(market_return, 2),
            "alpha": round(alpha, 2),
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown": round(max_dd, 2),
            "trade_count": player.trade_count,
            "total_fees_paid": round(player.total_fees_paid, 2),
            "rating": rating,
            "message": message,
            "seed": seed
        }

    def save_game_to_file(self, session: GameSession, slot: str = "websave") -> str:
        """Save game to file"""
        path = save_game(session.market, session.player, session.seed, slot)
        return str(path)

    def load_game_from_file(self, slot: str) -> Tuple[Optional[str], Optional[GameSession], Optional[str]]:
        """
        Load game from file.
        Returns: (game_id, session, error_message)
        """
        state = load_game(slot)
        if not state:
            return None, None, f"Save '{slot}' not found"

        try:
            market, player, seed = deserialize_game_state(state)

            # Re-initialize RNG
            if seed is not None:
                self._initialize_random(seed)

            game_id = str(uuid.uuid4())[:8]
            session = GameSession(
                game_id=game_id,
                market=market,
                player=player,
                seed=seed,
                news_history=[]
            )

            self.sessions[game_id] = session
            return game_id, session, None

        except Exception as e:
            return None, None, f"Error loading save: {str(e)}"

    def get_saves_list(self) -> List[Dict[str, Any]]:
        """Get list of available saves"""
        return list_saves()


# Global game manager instance
game_manager = GameManager()
