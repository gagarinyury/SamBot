"""
User settings and states data models.
Extracted from bot.py for better modularity.
"""

from typing import Dict, Optional
from dataclasses import dataclass
from aiogram.fsm.state import State, StatesGroup


class SummaryStates(StatesGroup):
    """FSM states for bot operations."""
    waiting_for_url = State()


@dataclass
class UserSettings:
    """User preferences and settings."""
    user_id: int
    language: str = "ru"  # ru, en, fr
    summary_type: str = "detailed"  # brief, detailed
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        return {
            'user_id': self.user_id,
            'language': self.language,
            'summary_type': self.summary_type,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'UserSettings':
        """Create from dictionary."""
        return cls(**data)


# Default user settings
DEFAULT_USER_SETTINGS = {
    "language": "ru",
    "summary_type": "detailed"
}