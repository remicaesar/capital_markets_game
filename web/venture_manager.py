"""
Venture fund session management for the web UI
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from config.venture_glossary import MECHANICS
from config.venture_settings import (
    CARRY_RATE, DEFAULT_RESERVE_RATIO, FUND_SIZE, INVESTABLE_CAPITAL, INVESTMENT_PERIODS,
    LIFETIME_FEES, MANAGEMENT_FEE_RATE, MAX_COMPANY_PCT, MAX_PERIODS, MIN_CHECK,
)
from models.market import new_game_rng
from models.venture_fund import ExitRecord, VentureFund, period_label
from web.session_store import VentureSessionStore

logger = logging.getLogger(__name__)

# How many log lines and exits the state payload carries
RECENT_LOG = 40


@dataclass
class VentureSession:
    game_id: str
    seed: int
    fund: VentureFund
    # Every successful action, in order. Replaying them on a fund built from the
    # same seed reproduces this session exactly - that is how sessions persist.
    actions: List[List[Any]] = field(default_factory=list)


def apply_action(fund: VentureFund, action: List[Any]) -> Tuple[bool, str, List[str]]:
    """The one place an action touches the fund, used both live and on replay."""
    kind = action[0]
    if kind == "commit":
        ok, message = fund.commit_to_deal(int(action[1]), float(action[2]), float(action[3]))
        return ok, message, []
    if kind == "follow_on":
        ok, message = fund.decide_follow_on(int(action[1]), float(action[2]))
        return ok, message, []
    if kind == "advance":
        if fund.is_over:
            return False, "The fund has ended", []
        return True, "", fund.advance()
    return False, f"Unknown action {kind!r}", []


class VentureManager:
    """Manages venture fund sessions"""

    def __init__(self, store: Optional[VentureSessionStore] = None):
        self.sessions: Dict[str, VentureSession] = {}
        self.store = store if store is not None else VentureSessionStore()
        self._restore_sessions()

    def _restore_sessions(self):
        for game_id, data in self.store.load_all_sessions().items():
            try:
                self.sessions[game_id] = self._replay(game_id, data["seed"], data["actions"])
            except Exception as e:
                logger.warning(f"Failed to restore venture session {game_id}: {e}")

    @staticmethod
    def _replay(game_id: str, seed: int, actions: List[List[Any]]) -> VentureSession:
        _, rng = new_game_rng(seed)
        session = VentureSession(game_id, seed, VentureFund(rng))
        for action in actions:
            ok, message, _ = apply_action(session.fund, action)
            if not ok:
                raise ValueError(f"replayed action {action} failed: {message}")
            session.actions.append(action)
        return session

    def _persist(self, session: VentureSession):
        try:
            self.store.save_session(session.game_id, session.seed, session.actions)
        except Exception as e:
            logger.error(f"Failed to persist venture session {session.game_id}: {e}")

    # ---------------------------------------------------------------- actions

    def create_game(self, seed: Optional[int] = None) -> Tuple[str, VentureSession]:
        game_id = str(uuid.uuid4())[:8]
        actual_seed, rng = new_game_rng(seed)
        session = VentureSession(game_id, actual_seed, VentureFund(rng))
        self.sessions[game_id] = session
        self._persist(session)
        return game_id, session

    def get_session(self, game_id: str) -> Optional[VentureSession]:
        return self.sessions.get(game_id)

    def act(self, session: VentureSession, action: List[Any]) -> Tuple[bool, str, List[str]]:
        ok, message, events = apply_action(session.fund, action)
        if ok:
            session.actions.append(action)
            self._persist(session)
        return ok, message, events

    # ---------------------------------------------------------------- state

    @staticmethod
    def _exit_state(record: ExitRecord) -> Dict[str, Any]:
        waterfall = None
        if record.waterfall is not None:
            yours = {r["series"]: r["payout"] for r in record.fund_rows}
            waterfall = {
                "rows": [{
                    "name": row.name,
                    "preference": round(row.preference, 2),
                    "converted": row.converted,
                    "payout": round(row.payout, 2),
                    "yours": round(yours.get(row.name, 0.0), 2),
                } for row in record.waterfall.rows],
                "common_payout": round(record.waterfall.common_payout, 2),
            }
        return {
            "period_label": period_label(record.period),
            "name": record.name,
            "kind": record.kind,
            "exit_value": round(record.exit_value, 2),
            "fund_proceeds": round(record.fund_proceeds, 2),
            "fund_invested": round(record.fund_invested, 2),
            "waterfall": waterfall,
        }

    def get_state(self, session: VentureSession) -> Dict[str, Any]:
        """Everything the browser shows. Hidden futures (schedule, quality) never leave."""
        fund = session.fund
        irr = fund.net_irr()

        status = {
            "period": fund.period,
            "max_periods": MAX_PERIODS,
            "investment_periods": INVESTMENT_PERIODS,
            "period_label": period_label(min(fund.period, MAX_PERIODS)),
            "phase": "over" if fund.is_over else ("investing" if fund.in_investment_period
                                                  else "harvesting"),
            "fund_size": FUND_SIZE,
            "management_fee_rate": MANAGEMENT_FEE_RATE,
            "carry_rate": CARRY_RATE,
            "lifetime_fees": LIFETIME_FEES,
            "investable_capital": INVESTABLE_CAPITAL,
            "min_check": MIN_CHECK,
            "max_company_amount": FUND_SIZE * MAX_COMPANY_PCT,
            "default_reserve_ratio": DEFAULT_RESERVE_RATIO,
            "invested": round(fund.invested(), 2),
            "reserved": round(fund.reserved(), 2),
            "pending": round(fund.pending(), 2),
            "available": round(fund.available(), 2),
            "fees_paid": round(fund.fees_paid, 2),
            "paid_in": round(fund.paid_in(), 2),
            "nav": round(fund.nav(), 2),
            "distributions": round(fund.distributions, 2),
            "net_distributions": round(fund.net_distributions(), 2),
            "carry_accrued": round(fund.carry_accrued(), 2),
            "tvpi": round(fund.tvpi(), 4),
            "dpi": round(fund.dpi(), 4),
            "gross_moic": round(fund.gross_moic(), 4),
            "net_irr": None if irr is None else round(irr, 4),
        }

        deals = []
        for deal in fund.deal_flow:
            rnd = deal.open_round
            commitment = fund.commitments.get(deal.id)
            deals.append({
                "id": deal.id,
                "name": deal.name,
                "sector": deal.sector,
                "stage": deal.stage,
                "pitch": deal.pitch,
                "signals": dict(deal.signals),
                "raise_amount": round(rnd.raise_amount, 2),
                "pre_money": round(rnd.pre_money, 2),
                "post_money": round(rnd.post_money, 2),
                "committed_check": round(commitment.check, 2) if commitment else None,
                "committed_reserve": round(commitment.reserve, 2) if commitment else None,
            })

        follow_ons = []
        portfolio = []
        for pos in sorted(fund.positions.values(), key=lambda p: p.proceeds + p.mark(), reverse=True):
            startup = pos.startup
            rnd = startup.open_round
            if pos.active and rnd is not None:
                step = rnd.pre_money / startup.last_post_money()
                follow_ons.append({
                    "startup_id": startup.id,
                    "name": startup.name,
                    "round_name": rnd.round_name,
                    "pre_money": round(rnd.pre_money, 2),
                    "raise_amount": round(rnd.raise_amount, 2),
                    "post_money": round(rnd.post_money, 2),
                    "step_up": round(step, 4),
                    "down_round": step < 1,
                    "ownership": round(pos.ownership(), 6),
                    "pro_rata": round(pos.pro_rata(), 2),
                    "reserve": round(pos.reserve, 2),
                    "decision": None if pos.follow_on is None else round(pos.follow_on, 2),
                })
            portfolio.append({
                "id": startup.id,
                "name": startup.name,
                "sector": startup.sector,
                "stage": startup.stage,
                "entry_label": period_label(pos.entry_period),
                "status": startup.status,
                "invested": round(pos.invested, 2),
                "reserve": round(pos.reserve, 2) if pos.active else 0.0,
                "ownership": round(pos.ownership(), 6) if pos.active else 0.0,
                "mark": round(pos.mark(), 2),
                "proceeds": round(pos.proceeds, 2),
                "multiple": round(pos.multiple(), 4),
                "rounds": [{
                    "name": s.name,
                    "period_label": period_label(s.period),
                    "post_money": round(s.post_money, 2),
                    "price": round(s.price, 6),
                } for s in startup.series],
            })

        history = [{
            "period": h["period"],
            "label": period_label(h["period"]),
            "paid_in": round(h["paid_in"], 2),
            "distributions": round(h["distributions"], 2),
            "net_distributions": round(h["net_distributions"], 2),
            "nav": round(h["nav"], 2),
            "cumulative_net_cash_flow": round(h["cumulative_net_cash_flow"], 2),
            "tvpi": round(h["tvpi"], 4),
            "dpi": round(h["dpi"], 4),
        } for h in fund.history]

        report = None
        if fund.is_over:
            raw = fund.final_report()
            report = {
                **{k: raw[k] for k in ("headline", "rating", "fund_returners", "deal_count",
                                       "losers")},
                **{k: round(raw[k], 2) for k in ("paid_in", "invested", "fees_paid",
                                                 "gross_proceeds", "carry_paid", "net_to_lps")},
                **{k: round(raw[k], 4) for k in ("gross_moic", "tvpi", "dpi")},
                "net_irr": None if raw["net_irr"] is None else round(raw["net_irr"], 4),
                "deals": [{
                    "name": d["name"],
                    "invested": round(d["invested"], 2),
                    "value": round(d["value"], 2),
                    "multiple": round(d["multiple"], 4),
                    "outcome": d["outcome"],
                    "share_of_value": round(d["share_of_value"], 4),
                    "returned_fund": d["returned_fund"],
                } for d in raw["deals"]],
            }

        return {
            "fund": status,
            "deals": deals,
            "follow_ons": follow_ons,
            "portfolio": portfolio,
            "history": history,
            "exits": [self._exit_state(r) for r in reversed(fund.exits[-RECENT_LOG:])],
            "log": [{"period_label": period_label(p), "text": text}
                    for p, text in reversed(fund.log[-RECENT_LOG:])],
            "report": report,
            "seed": session.seed,
        }

    @staticmethod
    def mechanics() -> List[Dict[str, str]]:
        return [{"key": key, "title": title, "body": body}
                for key, (title, body) in MECHANICS.items()]


# Global venture manager instance
venture_manager = VentureManager()
