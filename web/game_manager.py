"""
Game session management for the web UI
"""

import uuid
import random
import logging
import numpy as np
from typing import Dict, Optional, Tuple, List, Any
from dataclasses import dataclass

from models.market import Market
from models.player import Player
from config.settings import MAX_TURNS, TRANSACTION_FEE, SHORT_MARGIN_REQUIREMENT, SHORT_LOCATE_FEE
from utils.save_manager import (
    save_game, load_game, serialize_game_state, deserialize_game_state, list_saves,
    InvalidSlotName
)
from web.session_store import SessionStore

logger = logging.getLogger(__name__)


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
        self.store = SessionStore()
        self._restore_sessions()

    def _persist_session(self, session: GameSession):
        """Serialize and persist a session to SQLite"""
        try:
            state = serialize_game_state(session.market, session.player, session.seed)
            self.store.save_session(
                session.game_id, state, session.news_history, session.seed
            )
        except Exception as e:
            logger.error(f"Failed to persist session {session.game_id}: {e}")

    def _restore_sessions(self):
        """Restore all sessions from SQLite on startup"""
        self.store.cleanup_expired()
        saved = self.store.load_all_sessions()
        restored = 0
        for game_id, data in saved.items():
            try:
                market, player, seed = deserialize_game_state(data["state"])
                session = GameSession(
                    game_id=game_id,
                    market=market,
                    player=player,
                    seed=seed,
                    news_history=data.get("news_history", []),
                )
                self.sessions[game_id] = session
                restored += 1
            except Exception as e:
                logger.warning(f"Failed to restore session {game_id}: {e}")
        if restored:
            logger.info(f"Restored {restored} session(s) from SQLite")

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
        self._persist_session(session)
        return game_id, session

    def get_session(self, game_id: str) -> Optional[GameSession]:
        """Get a game session by ID"""
        return self.sessions.get(game_id)

    def delete_session(self, game_id: str) -> bool:
        """Delete a game session"""
        if game_id in self.sessions:
            del self.sessions[game_id]
            self.store.delete_session(game_id)
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
                "beta": round(company.beta, 2),
                "pe_ratio": round(company.pe_ratio, 1),
                "growth_rate": round(company.growth_rate * 100, 1),
                "debt_level": company.debt_level,
                "valuation": company.get_valuation_status(),
                "price_history": [round(p, 2) for p in company.price_history],
                "volume_history": [round(v, 2) for v in company.volume_history]
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
            "options_value": round(player.options_value(market), 2),
            "options_pnl": round(player.options_pnl_realized, 2),
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

        # Pending orders
        pending_orders = []
        for order in player.pending_orders:
            company = market.companies.get(order["company"])
            current_price = company.price if company else 0
            pending_orders.append({
                "id": order["id"],
                "order_type": order["order_type"],
                "action": order["action"],
                "company": order["company"],
                "shares": order["shares"],
                "limit_price": round(order["limit_price"], 2),
                "current_price": round(current_price, 2),
                "created_turn": order["created_turn"],
                "created_price": round(order["created_price"], 2)
            })

        # Options positions
        options_positions = []
        for option in player.options_positions:
            company = market.companies.get(option.company)
            current_price = company.price if company else 0
            current_value = option.estimate_current_value(current_price, market.turn) if company else 0
            pnl = option.current_pnl(current_price, market.turn) if company else -option.total_premium_paid()

            options_positions.append({
                "id": option.id,
                "type": option.option_type.value,
                "company": option.company,
                "strike_price": round(option.strike_price, 2),
                "premium": round(option.premium, 2),
                "contracts": option.contracts,
                "created_turn": option.created_turn,
                "expiry_turn": option.expiry_turn,
                "turns_remaining": option.turns_remaining(market.turn),
                "current_price": round(current_price, 2),
                "current_value": round(current_value, 2),
                "intrinsic_value": round(option.intrinsic_value(current_price), 2),
                "total_premium_paid": round(option.total_premium_paid(), 2),
                "pnl": round(pnl, 2),
                "in_the_money": option.is_in_the_money(current_price)
            })

        # Calculate market return history for benchmark
        market_returns = []
        if market.market_history:
            initial_cap = market.market_history[0] if market.market_history else 1
            for cap in market.market_history:
                market_returns.append(float(round(((cap - initial_cap) / initial_cap) * 100, 2)) if initial_cap > 0 else 0.0)

        return {
            "turn": market.turn,
            "max_turns": MAX_TURNS,
            "regime": market.regime.current,
            "companies": companies,
            "portfolio": portfolio,
            "short_positions": short_positions,
            "pending_orders": pending_orders,
            "options_positions": options_positions,
            "player": player_stats,
            "psychology": psychology,
            "news": session.news_history[-5:],  # Last 5 news items
            "game_over": market.turn > MAX_TURNS,
            "market_return_history": market_returns,
        }

    def execute_action(self, session: GameSession, action: str, company_name: str, shares: int) -> Tuple[bool, str]:
        """Execute a trading action"""
        market = session.market
        player = session.player

        if not isinstance(shares, int) or isinstance(shares, bool) or shares <= 0:
            return False, "Share count must be a positive whole number"

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
                    self._persist_session(session)
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
                    self._persist_session(session)
                    return True, f"Sold {shares} shares of {company_name}"
                return False, "Sale failed"

            elif action == "short":
                if company_name in player.portfolio:
                    return False, "Cannot short a stock you own. Sell your long position first."
                available_margin = player.available_margin(market)
                margin_per_share = company.price * SHORT_MARGIN_REQUIREMENT
                fee_per_share = company.price * (SHORT_LOCATE_FEE + TRANSACTION_FEE)
                cost_per_share = margin_per_share + fee_per_share
                max_shares = int(available_margin // cost_per_share) if cost_per_share > 0 else 0
                if shares > max_shares:
                    return False, f"Insufficient margin. Max shortable: {max_shares}"
                success = player.short(market, company, shares)
                if success:
                    self._persist_session(session)
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
                    self._persist_session(session)
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

            # Process pending orders after price changes
            order_executions = player.process_pending_orders(market)

            # Process expired options
            option_events = player.process_expired_options(market)

            # Add all events to news
            if option_events:
                news_events = option_events + news_events
            if order_executions:
                news_events = order_executions + news_events
            if margin_call_events:
                news_events = margin_call_events + news_events

            # Store news history
            session.news_history.extend(news_events)

            # Check for game over (game ends after turn 50 advances to turn 51)
            game_over = market.turn > MAX_TURNS
            final_stats = None

            if game_over:
                final_stats = self._calculate_final_stats(market, player, session.seed)

            self._persist_session(session)
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
        try:
            state = load_game(slot)
        except InvalidSlotName as exc:
            return None, None, str(exc)

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
            self._persist_session(session)
            return game_id, session, None

        except Exception as e:
            return None, None, f"Error loading save: {str(e)}"

    def get_saves_list(self) -> List[Dict[str, Any]]:
        """Get list of available saves"""
        return list_saves()

    def place_order(self, session: GameSession, order_type: str, action: str,
                    company_name: str, shares: int, limit_price: float) -> Tuple[bool, str, Dict]:
        """Place a limit order, stop loss, or take profit order"""
        market = session.market
        player = session.player

        # Suppress console output
        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        try:
            result = player.place_order(market, order_type, action, company_name, shares, limit_price)
            if result[0]:  # success
                self._persist_session(session)
            return result
        finally:
            sys.stdout = old_stdout

    def cancel_order(self, session: GameSession, order_id: int) -> Tuple[bool, str]:
        """Cancel a pending order"""
        # Suppress console output
        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        try:
            result = session.player.cancel_order(order_id)
            if result[0]:
                self._persist_session(session)
            return result
        finally:
            sys.stdout = old_stdout

    def buy_option(self, session: GameSession, company_name: str, option_type: str,
                   strike_price: float, contracts: int) -> Tuple[bool, str, Dict]:
        """Buy a call or put option"""
        # Suppress console output
        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        try:
            result = session.player.buy_option(
                session.market, company_name, option_type, strike_price, contracts
            )
            if result[0]:
                self._persist_session(session)
            return result
        finally:
            sys.stdout = old_stdout

    def exercise_option(self, session: GameSession, option_id: int) -> Tuple[bool, str]:
        """Exercise an option"""
        # Suppress console output
        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        try:
            result = session.player.exercise_option(session.market, option_id)
            if result[0]:
                self._persist_session(session)
            return result
        finally:
            sys.stdout = old_stdout

    def sell_option(self, session: GameSession, option_id: int) -> Tuple[bool, str]:
        """Sell an option back to market"""
        # Suppress console output
        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        try:
            result = session.player.sell_option(session.market, option_id)
            if result[0]:
                self._persist_session(session)
            return result
        finally:
            sys.stdout = old_stdout

    def get_option_chain(self, session: GameSession, company_name: str) -> Dict:
        """Get available options for a company with pricing"""
        from models.options import options_manager, OptionType

        market = session.market
        if company_name not in market.companies:
            return {"error": f"Company '{company_name}' not found"}

        company = market.companies[company_name]
        strikes = options_manager.get_available_strikes(company)

        chain = {
            "company": company_name,
            "current_price": round(company.price, 2),
            "volatility": round(company.volatility, 4),
            "calls": [],
            "puts": []
        }

        for strike in strikes:
            # Calculate premiums for 5-turn expiry
            call_premium = options_manager.calculate_premium(
                company, strike, OptionType.CALL, 5
            )
            put_premium = options_manager.calculate_premium(
                company, strike, OptionType.PUT, 5
            )

            chain["calls"].append({
                "strike": strike,
                "premium": call_premium,
                "total_cost": round(call_premium * 100, 2),  # Per contract
                "itm": company.price > strike
            })

            chain["puts"].append({
                "strike": strike,
                "premium": put_premium,
                "total_cost": round(put_premium * 100, 2),
                "itm": company.price < strike
            })

        return chain


# Global game manager instance
game_manager = GameManager()
