"""
Bug #12: a save slot name became a filename with no validation.

`get_save_path` interpolated the slot straight into a path, and the web API took it
from the request body. Slot "../../../../tmp/pwned" resolved to /tmp/pwned.json.
Reachable from the network, because run_web.py binds 0.0.0.0.
"""

import pytest

from utils.save_manager import (
    SAVE_DIR,
    InvalidSlotName,
    get_save_path,
    validate_slot,
)

TRAVERSAL = [
    "../../../../tmp/pwned",
    "../autosave",
    "sub/dir",
    "/etc/passwd",
    "..",
    ".",
    "back\\slash",
    "",
    "-leading-dash",
    "with space",
    "semi;colon",
    "null\x00byte",
    "x" * 65,
]


@pytest.mark.parametrize("slot", TRAVERSAL)
def test_unsafe_slot_names_are_rejected(slot):
    with pytest.raises(InvalidSlotName):
        validate_slot(slot)


@pytest.mark.parametrize("slot", TRAVERSAL)
def test_get_save_path_refuses_unsafe_slots(slot):
    with pytest.raises(InvalidSlotName):
        get_save_path(slot)


@pytest.mark.parametrize("slot", ["autosave", "websave", "my-save", "my_save_2", "a", "A1"])
def test_ordinary_slot_names_still_work(slot):
    path = get_save_path(slot)
    assert path.parent == SAVE_DIR
    assert path.name == f"{slot}.json"


@pytest.mark.parametrize("slot", TRAVERSAL)
def test_every_accepted_path_stays_inside_the_save_directory(slot):
    """The property that actually matters, stated directly."""
    try:
        path = get_save_path(slot)
    except InvalidSlotName:
        return  # rejected outright, which is the point
    assert SAVE_DIR.resolve() in path.resolve().parents


def test_load_endpoint_reports_bad_slot_instead_of_crashing():
    from web.game_manager import game_manager

    game_id, session, error = game_manager.load_game_from_file("../../../../etc/passwd")

    assert game_id is None
    assert session is None
    assert "Invalid save slot" in error
