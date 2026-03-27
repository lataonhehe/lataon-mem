from dataclasses import dataclass
from typing import Optional
from enum import Enum


class UserMode(Enum):
    IDLE = "idle"
    AWAITING_REPLY = "awaiting_reply"  # vừa hỏi Socratic, chờ trả lời


@dataclass
class UserState:
    mode: UserMode = UserMode.IDLE
    last_note_id: Optional[int] = None
    last_note_content: Optional[str] = None
    last_category: Optional[str] = None


_states: dict[int, UserState] = {}


def get_state(user_id: int) -> UserState:
    if user_id not in _states:
        _states[user_id] = UserState()
    return _states[user_id]


def set_mode(user_id: int, mode: UserMode):
    get_state(user_id).mode = mode


def set_last_note(user_id: int, note_id: int, content: str, category: str):
    s = get_state(user_id)
    s.last_note_id = note_id
    s.last_note_content = content
    s.last_category = category


def reset(user_id: int):
    _states[user_id] = UserState()
