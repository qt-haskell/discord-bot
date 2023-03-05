from __future__ import annotations

from typing import Callable
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
    """Base class for exceptions that are meant to be shown to the user.
    
    Meant to be used with the `:class:UserFeedbackExceptionFactory`.

    Notes
    -----
    Formatters can be found in `utils/extra/helper.py` and are used to format the
    message before it is shown to the user.

    - `bold` - **bold**
    - `underline` - __underline__
    - `quote` - > quote
    - `codeblock` - `codeblock`

    EmojiStrategies
    ---------------
    The emoji strategy is used to determine what emoji should be shown before the

    - `ErrorUserFeedbackEmoji` - ❌
    - `WarningUserFeedbackEmoji` - ⚠️
    - `InfoUserFeedbackEmoji` - 📨
    - `DefaultUserFeedbackEmoji` - 🔍

    These are linked to the `ExceptionLevel` enum.

    +----------------+-----------------+
    | ExceptionLevel | EmojiStrategy   |
    +================+=================+
    | ERROR          | 1               |
    +----------------+-----------------+
    | WARNING        | 2               |
    +----------------+-----------------+
    | INFO           | 3               |
    +----------------+-----------------+
    | DEFAULT        | Any other value |
    +----------------+-----------------+
    """
    def __init__(
        self,
        message: str,
        emoji_strategy: UserFeedbackEmojiStrategy,
        formatters: tuple[Callable[[str], str], ...] = (),
    ) -> None:
        self.message: str = message
        self.emoji_strategy: UserFeedbackEmojiStrategy = emoji_strategy
        self.formatters: tuple[Callable[[str], str], ...] = formatters
        super().__init__(message)

    def __str__(self) -> str:
        formatted_message: str = self.message
        for formatter in self.formatters:
            formatted_message = formatter(formatted_message)
        return f"{self.emoji_strategy.get_emoji()} | {formatted_message}"


class UserFeedbackEmojiStrategy(ABC):
    @abstractmethod
    def get_emoji(self) -> str:
        pass


class DefaultUserFeedbackEmoji(UserFeedbackEmojiStrategy):
    def get_emoji(self) -> str:
        return "🔍"


class ErrorUserFeedbackEmoji(UserFeedbackEmojiStrategy):
    def get_emoji(self) -> str:
        return "❌"


class WarningUserFeedbackEmoji(UserFeedbackEmojiStrategy):
    def get_emoji(self) -> str:
        return "⚠️"


class InfoUserFeedbackEmoji(UserFeedbackEmojiStrategy):
    def get_emoji(self) -> str:
        return "📨"


class UserFeedbackExceptionFactory:
    EMOJI_STRATEGIES = {
        ExceptionLevel.ERROR: ErrorUserFeedbackEmoji(),
        ExceptionLevel.WARNING: WarningUserFeedbackEmoji(),
        ExceptionLevel.INFO: InfoUserFeedbackEmoji(),
    }

    @staticmethod
    def create(
        message: str,
        level: ExceptionLevel = ExceptionLevel.ERROR,
        formatters: tuple[Callable[[str], str], ...] = (),
    ) -> UserFeedbackException:
        return UserFeedbackException(
            message,
            UserFeedbackExceptionFactory.EMOJI_STRATEGIES.get(level, DefaultUserFeedbackEmoji()),
            formatters,
        )
