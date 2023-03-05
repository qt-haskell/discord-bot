from __future__ import annotations

import asyncio
import logging
import time
from contextlib import AbstractContextManager
from datetime import timedelta
from inspect import isawaitable
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Final,
    Generic,
    Iterable,
    Literal,
    Optional,
    Self,
    Sequence,
    Type,
    TypeGuard,
    TypeVar,
    overload,
)

import discord

if TYPE_CHECKING:
    from bot import RoboLia


_T = TypeVar("_T")

__all__: tuple[str, ...] = (
    "humanize_seconds",
    "format_list",
    "humanize_timedelta",
    "AppInfoCache",
    "suppress",
    "async_all",
)


log: logging.Logger = logging.getLogger(__name__)


PERIODS: Final[Sequence[tuple[str, str, int]]] = (
    ("year", "years", 60 * 60 * 24 * 365),
    ("month", "months", 60 * 60 * 24 * 30),
    ("day", "days", 60 * 60 * 24),
    ("hour", "hours", 60 * 60),
    ("minute", "minutes", 60),
    ("second", "seconds", 1),
)


def format_list(to_format: Sequence[str], /, *, comma: str = ",") -> str:
    length = len(to_format)

    if length == 0:
        raise ValueError("Must provide at least one item")

    if length == 2:
        return " and ".join(to_format)
    if length > 2:
        *most, last = to_format
        h = f"{comma} ".join(most)
        return f"{h}{comma} and {last}"
    return next(iter(to_format))


def humanize_seconds(seconds: float) -> str:
    seconds = int(seconds)
    strings = []
    for period_name, plural_period_name, period_seconds in PERIODS:
        if seconds >= period_seconds:
            period_value, seconds = divmod(seconds, period_seconds)
            if period_value == 0:
                continue
            unit = plural_period_name if period_value > 1 else period_name
            strings.append(f"{period_value} {unit}")

    return format_list(strings, comma="")


def humanize_timedelta(delta: timedelta) -> str:
    return humanize_seconds(delta.total_seconds())


class AppInfoCache:
    def __init__(self, bot: RoboLia) -> None:
        self.bot: RoboLia = bot
        self._cached_info: Optional[discord.AppInfo] = None
        self._lock: asyncio.Lock = asyncio.Lock()
        self._invalidate_task: Optional[asyncio.Task] = None

    async def get(self) -> discord.AppInfo:
        async with self._lock:
            if self._cached_info is None:
                self._cached_info = await self.bot.application_info()
                if self._invalidate_task is not None:
                    self._invalidate_task.cancel()

                self._invalidate_task = asyncio.create_task(self.defere(300))

            return self._cached_info

    async def defere(self, time: float) -> None:
        await asyncio.sleep(time)
        async with self._lock:
            self._cached_info = None


class suppress(AbstractContextManager[None]):
    """
    Note:
    -----
    This should NOT use `return` within the context of `suppress`.
    Instead, use the `Single Return Law Pattern` to return from the context.

    Reasoning behind this is that static linters will not be able to understand
    that the following context is reachable.
    """

    def __init__(
        self, *exceptions: Type[BaseException], log: Optional[str] = None, capture: bool = True, **kwargs: Any
    ) -> None:
        self._exceptions: tuple[Type[BaseException], ...] = exceptions
        self._log: str = log or "An exception was suppressed: %s"
        self._capture: bool = capture
        self._kwargs: dict[str, Any] = kwargs

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]] = None,
        exc_value: Optional[BaseException] = None,
        traceback: Optional[TracebackType] = None,
    ) -> Optional[bool]:
        if captured := exc_type is not None and issubclass(exc_type, self._exceptions):
            if self._capture:
                log.info(self._log % self._kwargs)

        log.debug("Suppressing exception: %s", exc_type)
        return captured


async def async_all(
    gen: Iterable[_T | Awaitable[_T]],
    *,
    check: Callable[[_T | Awaitable[_T]], TypeGuard[Awaitable[_T]]] = isawaitable,
) -> bool:
    """Returns True if all elements in the iterable are truthy."""
    for elem in gen:
        if check(elem):
            elem = await elem
        if not elem:
            return False
    return True
