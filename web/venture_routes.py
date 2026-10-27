"""
API route handlers for venture fund mode
"""

from fastapi import APIRouter, HTTPException

from web.venture_manager import VentureSession, venture_manager
from web.venture_schemas import (
    AdvanceFundRequest, AdvanceFundResponse, CommitRequest, FollowOnRequest,
    MechanicsResponse, NewFundRequest, NewFundResponse, VentureActionResponse,
    VentureStateResponse,
)

router = APIRouter(prefix="/api/venture", tags=["venture"])


def _session(game_id: str) -> VentureSession:
    session = venture_manager.get_session(game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Fund not found")
    return session


@router.post("/new", response_model=NewFundResponse)
async def new_fund(request: NewFundRequest):
    """Open a new fund"""
    game_id, session = venture_manager.create_game(seed=request.seed)
    return NewFundResponse(game_id=game_id, state=venture_manager.get_state(session))


@router.get("/state", response_model=VentureStateResponse)
async def get_state(game_id: str):
    """Get the current state of a fund"""
    session = _session(game_id)
    return VentureStateResponse(state=venture_manager.get_state(session))


@router.post("/commit", response_model=VentureActionResponse)
async def commit(request: CommitRequest):
    """Back a startup in this period's deal flow (a cheque of 0 withdraws)"""
    session = _session(request.game_id)
    success, message, _ = venture_manager.act(
        session, ["commit", request.deal_id, request.check, request.reserve])
    return VentureActionResponse(success=success, message=message,
                                 state=venture_manager.get_state(session))


@router.post("/follow-on", response_model=VentureActionResponse)
async def follow_on(request: FollowOnRequest):
    """Answer a portfolio company's round: an amount up to pro-rata, or 0 to pass"""
    session = _session(request.game_id)
    success, message, _ = venture_manager.act(
        session, ["follow_on", request.startup_id, request.amount])
    return VentureActionResponse(success=success, message=message,
                                 state=venture_manager.get_state(session))


@router.post("/advance", response_model=AdvanceFundResponse)
async def advance(request: AdvanceFundRequest):
    """Close this half-year's rounds and play out the next one"""
    session = _session(request.game_id)
    _, _, events = venture_manager.act(session, ["advance"])
    return AdvanceFundResponse(events=events, state=venture_manager.get_state(session))


@router.get("/mechanics", response_model=MechanicsResponse)
async def mechanics():
    """Short explanations of each venture mechanic"""
    return MechanicsResponse(mechanics=venture_manager.mechanics())
