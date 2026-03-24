from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Note:
    content: str
    category: str
    tags: list[str]
    summary: str
    user_id: int
    id: Optional[int] = None
    created_at: Optional[datetime] = None

    def tags_str(self) -> str:
        return ", ".join(self.tags) if self.tags else ""
