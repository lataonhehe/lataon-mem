from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class UserMode(Enum):
    IDLE = "idle"
    DEEP_DIVE = "deep_dive"  # đang trong luồng hỏi đáp Socratic


@dataclass
class UserState:
    mode: UserMode = UserMode.IDLE
    last_note_id: Optional[int] = None
    last_note_content: Optional[str] = None
    deep_dive_turns: int = 0


_states: dict[int, UserState] = {}


def get_state(user_id: int) -> UserState:
    if user_id not in _states:
        _states[user_id] = UserState()
    return _states[user_id]


def set_mode(user_id: int, mode: UserMode):
    get_state(user_id).mode = mode


def set_last_note(user_id: int, note_id: int, content: str):
    s = get_state(user_id)
    s.last_note_id = note_id
    s.last_note_content = content


def reset(user_id: int):
    _states[user_id] = UserState()
