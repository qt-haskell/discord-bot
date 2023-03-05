from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

__all__: tuple[str, ...] = (
    "UserFeedbackException",
    "UserFeedbackExceptionFactory",
)


class ExceptionLevel(Enum):
    ERROR = 1
    WARNING = 2
    INFO = 3


class UserFeedbackException(Exception):
    def __init__(self, message: str, emoji_strategy: UserFeedbackEmojiStrategy) -> None:
        self.message: str = message
        self.emoji_strategy = emoji_strategy
        super().__init__(message)

    def __str__(self) -> str:
        return f"{self.emoji_strategy.get_emoji()} | {self.message}"


class UserFeedbackEmojiStrategy(ABC):
    @abstractmethod
    def get_emoji(self) -> str:
        pass


class DefaultUserFeedbackEmoji(UserFeedbackEmojiStrategy):
    def get_emoji(self) -> str:
        return "🔶"


class ErrorUserFeedbackEmoji(UserFeedbackEmojiStrategy):
    def get_emoji(self) -> str:
        return "❌"


class WarningUserFeedbackEmoji(UserFeedbackEmojiStrategy):
    def get_emoji(self) -> str:
        return "⚠️"


class InfoUserFeedbackEmoji(UserFeedbackEmojiStrategy):
    def get_emoji(self) -> str:
        return "🔮"


class UserFeedbackExceptionFactory:
    EMOJI_STRATEGIES = {
        ExceptionLevel.ERROR: ErrorUserFeedbackEmoji(),
        ExceptionLevel.WARNING: WarningUserFeedbackEmoji(),
        ExceptionLevel.INFO: InfoUserFeedbackEmoji(),
    }

    @staticmethod
    def create(message: str, level: ExceptionLevel = ExceptionLevel.ERROR) -> UserFeedbackException:
        return UserFeedbackException(
            message, UserFeedbackExceptionFactory.EMOJI_STRATEGIES.get(level, DefaultUserFeedbackEmoji())
        )
