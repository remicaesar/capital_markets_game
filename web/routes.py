"""
API route handlers for the Capital Markets Game web UI
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

from web.schemas import (
    NewGameRequest, ActionRequest, AdvanceRequest,
    SaveGameRequest, LoadGameRequest,
    NewGameResponse, StateResponse, ActionResponse, AdvanceResponse,
    SavesListResponse, SaveGameResponse, LoadGameResponse, SaveInfo
)
from web.game_manager import game_manager

router = APIRouter(prefix="/api/game", tags=["game"])


@router.post("/new", response_model=NewGameResponse)
async def new_game(request: NewGameRequest):
    """Start a new game"""
    game_id, session = game_manager.create_game(seed=request.seed)
    state = game_manager.get_game_state(session)
    return NewGameResponse(game_id=game_id, state=state)


@router.get("/state", response_model=StateResponse)
async def get_state(game_id: str):
    """Get current game state"""
    session = game_manager.get_session(game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")

    state = game_manager.get_game_state(session)
    return StateResponse(state=state)


@router.post("/action", response_model=ActionResponse)
async def execute_action(request: ActionRequest):
    """Execute a trading action (buy, sell, short, cover)"""
    session = game_manager.get_session(request.game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")

    success, message = game_manager.execute_action(
        session,
        request.action.lower(),
        request.company,
        request.shares
    )

    state = game_manager.get_game_state(session)
    return ActionResponse(success=success, message=message, state=state)


@router.post("/advance", response_model=AdvanceResponse)
async def advance_turn(request: AdvanceRequest):
    """Advance to the next turn"""
    session = game_manager.get_session(request.game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")

    news, game_over, final_stats = game_manager.advance_turn(session)
    state = game_manager.get_game_state(session)

    return AdvanceResponse(
        news=news,
        state=state,
        game_over=game_over,
        final_stats=final_stats
    )


@router.get("/saves", response_model=SavesListResponse)
async def list_saves():
    """List all available save files"""
    saves = game_manager.get_saves_list()
    save_infos = [
        SaveInfo(
            slot=s["slot"],
            turn=s.get("turn", 0),
            seed=s.get("seed"),
            timestamp=s.get("timestamp", "")
        )
        for s in saves
    ]
    return SavesListResponse(saves=save_infos)


@router.post("/save", response_model=SaveGameResponse)
async def save_game(request: SaveGameRequest):
    """Save the current game"""
    session = game_manager.get_session(request.game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")

    path = game_manager.save_game_to_file(session, request.slot)
    return SaveGameResponse(
        success=True,
        message=f"Game saved to slot '{request.slot}'",
        path=path
    )


@router.post("/load", response_model=LoadGameResponse)
async def load_game(request: LoadGameRequest):
    """Load a saved game"""
    game_id, session, error = game_manager.load_game_from_file(request.slot)

    if error:
        return LoadGameResponse(success=False, message=error)

    state = game_manager.get_game_state(session)
    return LoadGameResponse(
        success=True,
        message=f"Game loaded from slot '{request.slot}'",
        game_id=game_id,
        state=state
    )
