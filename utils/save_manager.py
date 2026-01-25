"""
Save/Load system for game state persistence
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Default save directory
SAVE_DIR = Path.home() / ".capital_markets_game" / "saves"


def ensure_save_dir():
    """Create save directory if it doesn't exist"""
    SAVE_DIR.mkdir(parents=True, exist_ok=True)


def get_save_path(slot: str = "autosave") -> Path:
    """Get path for a save slot"""
    ensure_save_dir()
    return SAVE_DIR / f"{slot}.json"


def serialize_game_state(market: "Market", player: "Player", seed: Optional[int] = None) -> Dict[str, Any]:
    """Serialize complete game state to dictionary"""
    return {
        "version": 1,
        "timestamp": datetime.now().isoformat(),
        "seed": seed,
        "market": serialize_market(market),
        "player": serialize_player(player),
    }


def serialize_market(market: "Market") -> Dict[str, Any]:
    """Serialize market state"""
    return {
        "turn": market.turn,
        "market_history": market.market_history,
        "return_history": market.return_history,
        "companies": {
            name: serialize_company(company)
            for name, company in market.companies.items()
        },
        "regime": {
            "current": market.regime.current,
            "strength": market.regime.strength,
            "turns_in_regime": market.regime.turns_in_regime,
        },
        "psychology": {
            "fear_greed_index": market.psychology.fear_greed_index,
            "herd_strength": market.psychology.herd_strength,
            "complacency": market.psychology.complacency,
            "capitulation_risk": market.psychology.capitulation_risk,
        },
        "hidden_factors": {
            "true_values": market.hidden_factors.true_values,
            "insider_sentiment": market.hidden_factors.insider_sentiment,
            "debt_levels": market.hidden_factors.debt_levels,
            "smart_money_positions": market.hidden_factors.smart_money_positions,
            "pending_news": market.hidden_factors.pending_news,
        },
        "algos": {
            "momentum_strength": market.algos.momentum_strength,
            "contrarian_strength": market.algos.contrarian_strength,
            "arb_strength": market.algos.arb_strength,
        },
        "crisis_system": {
            "active_crises": [
                {
                    "crisis_name": ac["crisis"]["name"],
                    "remaining_duration": ac["remaining_duration"],
                }
                for ac in market.crisis_system.active_crises
            ],
            "crisis_history": market.crisis_system.crisis_history,
        },
    }


def serialize_company(company: "Company") -> Dict[str, Any]:
    """Serialize company state"""
    return {
        "name": company.name,
        "sector": company.sector,
        "price": company.price,
        "trend_long": company.trend_long,
        "volatility": company.volatility,
        "beta": company.beta,
        "trend_short": company.trend_short,
        "price_history": company.price_history,
        "volume_history": company.volume_history,
        "momentum_score": company.momentum_score,
        "relative_strength": company.relative_strength,
        "earnings_momentum": company.earnings_momentum,
    }


def serialize_player(player: "Player") -> Dict[str, Any]:
    """Serialize player state"""
    return {
        "cash": player.cash,
        "portfolio": {
            name: {"shares": shares, "avg_price": avg_price}
            for name, (shares, avg_price) in player.portfolio.items()
        },
        "short_positions": {
            name: {"shares": shares, "borrow_price": borrow_price}
            for name, (shares, borrow_price) in player.short_positions.items()
        },
        "trade_count": player.trade_count,
        "total_fees_paid": player.total_fees_paid,
        "total_slippage_paid": player.total_slippage_paid,
        "total_borrow_fees_paid": player.total_borrow_fees_paid,
        "margin_calls_received": player.margin_calls_received,
        "starting_cash": player.starting_cash,
        "trade_history": player.trade_history,
        "portfolio_values": player.portfolio_values,
        "skill_rating": player.skill_rating,
    }


def save_game(market: "Market", player: "Player", seed: Optional[int] = None,
              slot: str = "autosave") -> Path:
    """Save game state to file"""
    state = serialize_game_state(market, player, seed)
    save_path = get_save_path(slot)

    with open(save_path, 'w') as f:
        json.dump(state, f, indent=2)

    return save_path


def load_game(slot: str = "autosave") -> Optional[Dict[str, Any]]:
    """Load game state from file"""
    save_path = get_save_path(slot)

    if not save_path.exists():
        return None

    with open(save_path, 'r') as f:
        return json.load(f)


def deserialize_game_state(state: Dict[str, Any]) -> tuple:
    """Deserialize game state, returns (market, player, seed)"""
    from models.market import Market
    from models.player import Player
    from models.company import Company
    from models.market_regime import MarketRegime
    from systems.psychology import MarketPsychology
    from systems.hidden_factors import HiddenFactors
    from systems.algorithmic_trading import AlgorithmicTraders
    from systems.crisis_events import CrisisEventSystem

    # Create empty market (skip company generation)
    market = Market.__new__(Market)
    market.companies = {}
    market.turn = state["market"]["turn"]
    market.market_history = state["market"]["market_history"]
    market.return_history = state["market"]["return_history"]

    # Restore companies
    for name, cdata in state["market"]["companies"].items():
        company = Company.__new__(Company)
        company.name = cdata["name"]
        company.sector = cdata["sector"]
        company.price = cdata["price"]
        company.trend_long = cdata["trend_long"]
        company.volatility = cdata["volatility"]
        company.beta = cdata["beta"]
        company.trend_short = cdata["trend_short"]
        company.price_history = cdata["price_history"]
        company.volume_history = cdata["volume_history"]
        company.momentum_score = cdata["momentum_score"]
        company.relative_strength = cdata["relative_strength"]
        company.earnings_momentum = cdata["earnings_momentum"]
        market.companies[name] = company

    # Restore regime
    market.regime = MarketRegime()
    market.regime.current = state["market"]["regime"]["current"]
    market.regime.strength = state["market"]["regime"].get("strength", 1.0)
    market.regime.turns_in_regime = state["market"]["regime"]["turns_in_regime"]

    # Restore psychology
    market.psychology = MarketPsychology()
    psych_data = state["market"]["psychology"]
    market.psychology.fear_greed_index = psych_data["fear_greed_index"]
    market.psychology.herd_strength = psych_data["herd_strength"]
    market.psychology.complacency = psych_data["complacency"]
    market.psychology.capitulation_risk = psych_data["capitulation_risk"]

    # Restore hidden factors
    market.hidden_factors = HiddenFactors()
    hf_data = state["market"]["hidden_factors"]
    market.hidden_factors.true_values = hf_data["true_values"]
    market.hidden_factors.insider_sentiment = hf_data["insider_sentiment"]
    market.hidden_factors.debt_levels = hf_data["debt_levels"]
    market.hidden_factors.smart_money_positions = hf_data["smart_money_positions"]
    market.hidden_factors.pending_news = hf_data["pending_news"]

    # Restore algos
    market.algos = AlgorithmicTraders()
    algo_data = state["market"]["algos"]
    market.algos.momentum_strength = algo_data["momentum_strength"]
    market.algos.contrarian_strength = algo_data["contrarian_strength"]
    market.algos.arb_strength = algo_data["arb_strength"]

    # Restore news system (stateless, just create new)
    from systems.news_system import AdvancedNewsSystem
    market.news_system = AdvancedNewsSystem()

    # Restore crisis system
    market.crisis_system = CrisisEventSystem()
    crisis_data = state["market"]["crisis_system"]
    market.crisis_system.crisis_history = crisis_data["crisis_history"]

    # Restore active crises by finding matching crisis definitions
    for ac in crisis_data["active_crises"]:
        for crisis_def in CrisisEventSystem.CRISIS_EVENTS:
            if crisis_def["name"] == ac["crisis_name"]:
                market.crisis_system.active_crises.append({
                    "crisis": crisis_def,
                    "remaining_duration": ac["remaining_duration"],
                })
                break

    # Restore player
    player = Player.__new__(Player)
    pdata = state["player"]
    player.cash = pdata["cash"]
    player.portfolio = {
        name: (pinfo["shares"], pinfo["avg_price"])
        for name, pinfo in pdata["portfolio"].items()
    }
    player.short_positions = {
        name: (sinfo["shares"], sinfo["borrow_price"])
        for name, sinfo in pdata.get("short_positions", {}).items()
    }
    player.trade_count = pdata["trade_count"]
    player.total_fees_paid = pdata["total_fees_paid"]
    player.total_slippage_paid = pdata.get("total_slippage_paid", 0.0)
    player.total_borrow_fees_paid = pdata.get("total_borrow_fees_paid", 0.0)
    player.margin_calls_received = pdata.get("margin_calls_received", 0)
    player.starting_cash = pdata["starting_cash"]
    player.trade_history = pdata["trade_history"]
    player.portfolio_values = pdata["portfolio_values"]
    player.skill_rating = pdata["skill_rating"]

    return market, player, state.get("seed")


def list_saves() -> list:
    """List all available save files"""
    ensure_save_dir()
    saves = []
    for save_file in SAVE_DIR.glob("*.json"):
        try:
            with open(save_file, 'r') as f:
                data = json.load(f)
                saves.append({
                    "slot": save_file.stem,
                    "timestamp": data.get("timestamp"),
                    "turn": data.get("market", {}).get("turn", 0),
                    "seed": data.get("seed"),
                })
        except (json.JSONDecodeError, KeyError):
            continue
    return sorted(saves, key=lambda x: x.get("timestamp", ""), reverse=True)


def delete_save(slot: str) -> bool:
    """Delete a save file"""
    save_path = get_save_path(slot)
    if save_path.exists():
        save_path.unlink()
        return True
    return False
