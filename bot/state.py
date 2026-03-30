from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum

SOCRATIC_MAX_TURNS = 3


class UserMode(Enum):
    IDLE = "idle"
    SOCRATIC = "socratic"
    DEEP_DIVE = "deep_dive"
    QUIZ = "quiz"
    CONFLICT = "conflict"


@dataclass
class UserState:
    mode: UserMode = UserMode.IDLE
    socratic_enabled: bool = True   # user có thể tắt Socratic

    # ghi chú vừa lưu
    last_note_id: Optional[int] = None
    last_note_content: Optional[str] = None
    last_category: Optional[str] = None

    # Socratic
    socratic_turns: int = 0
    socratic_history: list = field(default_factory=list)

    # Deep dive
    deep_topic: Optional[str] = None
    deep_history: list = field(default_factory=list)
    deep_turns: int = 0

    # Quiz
    quiz_note: Optional[Any] = None

    # Nháp khi conflict
    pending_note_text: Optional[str] = None
    prev_mode: Optional[UserMode] = None


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
    s = get_state(user_id)
    enabled = s.socratic_enabled   # giữ lại preference
    _states[user_id] = UserState(socratic_enabled=enabled)