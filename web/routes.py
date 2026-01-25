"""
API route handlers for the Capital Markets Game web UI
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

from web.schemas import (
    NewGameRequest, ActionRequest, AdvanceRequest,
    SaveGameRequest, LoadGameRequest,
    PlaceOrderRequest, CancelOrderRequest,
    BuyOptionRequest, OptionActionRequest,
    NewGameResponse, StateResponse, ActionResponse, AdvanceResponse,
    SavesListResponse, SaveGameResponse, LoadGameResponse, SaveInfo,
    PlaceOrderResponse, CancelOrderResponse,
    BuyOptionResponse, OptionActionResponse, OptionChainResponse
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


@router.post("/order", response_model=PlaceOrderResponse)
async def place_order(request: PlaceOrderRequest):
    """Place a limit order, stop loss, or take profit order"""
    session = game_manager.get_session(request.game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")

    success, message, order = game_manager.place_order(
        session,
        request.order_type,
        request.action,
        request.company,
        request.shares,
        request.limit_price
    )

    state = game_manager.get_game_state(session)
    return PlaceOrderResponse(
        success=success,
        message=message,
        order=order if success else None,
        state=state
    )


@router.post("/order/cancel", response_model=CancelOrderResponse)
async def cancel_order(request: CancelOrderRequest):
    """Cancel a pending order"""
    session = game_manager.get_session(request.game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")

    success, message = game_manager.cancel_order(session, request.order_id)

    state = game_manager.get_game_state(session)
    return CancelOrderResponse(
        success=success,
        message=message,
        state=state
    )


# =============================================================================
# Options Trading Endpoints
# =============================================================================

@router.get("/options/chain", response_model=OptionChainResponse)
async def get_option_chain(game_id: str, company: str):
    """Get available options (calls and puts) for a company"""
    session = game_manager.get_session(game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")

    chain = game_manager.get_option_chain(session, company)
    if "error" in chain:
        raise HTTPException(status_code=400, detail=chain["error"])

    return OptionChainResponse(**chain)


@router.post("/options/buy", response_model=BuyOptionResponse)
async def buy_option(request: BuyOptionRequest):
    """Buy a call or put option"""
    session = game_manager.get_session(request.game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")

    success, message, option = game_manager.buy_option(
        session,
        request.company,
        request.option_type,
        request.strike_price,
        request.contracts
    )

    state = game_manager.get_game_state(session)
    return BuyOptionResponse(
        success=success,
        message=message,
        option=option if success else None,
        state=state
    )


@router.post("/options/exercise", response_model=OptionActionResponse)
async def exercise_option(request: OptionActionRequest):
    """Exercise an option"""
    session = game_manager.get_session(request.game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")

    success, message = game_manager.exercise_option(session, request.option_id)

    state = game_manager.get_game_state(session)
    return OptionActionResponse(
        success=success,
        message=message,
        state=state
    )


@router.post("/options/sell", response_model=OptionActionResponse)
async def sell_option(request: OptionActionRequest):
    """Sell an option back to market"""
    session = game_manager.get_session(request.game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")

    success, message = game_manager.sell_option(session, request.option_id)

    state = game_manager.get_game_state(session)
    return OptionActionResponse(
        success=success,
        message=message,
        state=state
    )
