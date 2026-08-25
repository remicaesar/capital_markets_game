"""
Save/Load system for game state persistence
"""

import json
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Default save directory
SAVE_DIR = Path.home() / ".capital_markets_game" / "saves"

# A save slot becomes a filename, so it must not be able to describe a path.
# Without this, slot "../../../../tmp/pwned" resolves outside SAVE_DIR entirely -
# and the web API takes the slot name straight from the request body.
VALID_SLOT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class InvalidSlotName(ValueError):
    """Raised when a save slot name could escape the save directory."""


def validate_slot(slot: str) -> str:
    """Return the slot unchanged, or raise InvalidSlotName."""
    if not isinstance(slot, str) or not VALID_SLOT.match(slot):
        raise InvalidSlotName(
            f"Invalid save slot {slot!r}. Use 1-64 letters, digits, '-' or '_', "
            "starting with a letter or digit."
        )
    return slot


def ensure_save_dir():
    """Create save directory if it doesn't exist"""
    SAVE_DIR.mkdir(parents=True, exist_ok=True)


def get_save_path(slot: str = "autosave") -> Path:
    """Get path for a save slot. Raises InvalidSlotName for unsafe names."""
    validate_slot(slot)
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
            "active_crisis": {
                "name": market.crisis_system.active_crisis.name,
                "headline": market.crisis_system.active_crisis.headline,
                "impact": market.crisis_system.active_crisis.impact,
                "duration": market.crisis_system.active_crisis.duration,
                "context": market.crisis_system.active_crisis.context,
            } if market.crisis_system.active_crisis else None,
            "warning_level": market.crisis_system.warning_level,
            "turns_since_crisis": market.crisis_system.turns_since_crisis,
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
        "pe_ratio": company.pe_ratio,
        "growth_rate": company.growth_rate,
        "debt_level": company.debt_level,
        "earnings_per_share": company.earnings_per_share,
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
        "next_order_id": player.next_order_id,
        "pending_orders": player.pending_orders,
        "options_pnl_realized": player.options_pnl_realized,
        "options_positions": [
            {
                "id": opt.id,
                "option_type": opt.option_type.value,
                "company": opt.company,
                "strike_price": opt.strike_price,
                "premium": opt.premium,
                "contracts": opt.contracts,
                "created_turn": opt.created_turn,
                "expiry_turn": opt.expiry_turn,
                "underlying_price_at_purchase": opt.underlying_price_at_purchase,
            }
            for opt in player.options_positions
        ],
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
        company.pe_ratio = cdata.get("pe_ratio", 15.0)
        company.growth_rate = cdata.get("growth_rate", 0.05)
        company.debt_level = cdata.get("debt_level", "Medium")
        company.earnings_per_share = cdata.get("earnings_per_share", company.price / company.pe_ratio)
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
    from systems.crisis_events import Crisis
    market.crisis_system = CrisisEventSystem()
    crisis_data = state["market"]["crisis_system"]
    market.crisis_system.crisis_history = crisis_data["crisis_history"]
    market.crisis_system.warning_level = crisis_data.get("warning_level", 0)
    market.crisis_system.turns_since_crisis = crisis_data.get("turns_since_crisis", 0)

    # Restore active crisis (singular)
    ac_data = crisis_data.get("active_crisis")
    if ac_data:
        market.crisis_system.active_crisis = Crisis(
            name=ac_data["name"],
            headline=ac_data["headline"],
            impact=ac_data["impact"],
            duration=ac_data["duration"],
            context=ac_data["context"],
        )

    # Restore player
    from models.options import Option, OptionType
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

    # Restore pending orders
    player.pending_orders = pdata.get("pending_orders", [])
    player.next_order_id = pdata.get("next_order_id", 1)

    # Restore options positions
    player.options_pnl_realized = pdata.get("options_pnl_realized", 0.0)
    player.options_positions = []
    for opt_data in pdata.get("options_positions", []):
        option = Option(
            id=opt_data["id"],
            option_type=OptionType(opt_data["option_type"]),
            company=opt_data["company"],
            strike_price=opt_data["strike_price"],
            premium=opt_data["premium"],
            contracts=opt_data["contracts"],
            created_turn=opt_data["created_turn"],
            expiry_turn=opt_data["expiry_turn"],
            underlying_price_at_purchase=opt_data["underlying_price_at_purchase"],
        )
        player.options_positions.append(option)

    # Sync options_manager ID counter
    from models.options import options_manager
    if player.options_positions:
        options_manager.next_option_id = max(o.id for o in player.options_positions) + 1

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
