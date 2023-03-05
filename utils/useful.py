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
    "Cascade",
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


class Cascade(Generic[_T]):
    def __init__(
        self,
        max_wait: float,
        max_quantity: int,
        async_callback: Callable[[Sequence[_T]], Awaitable],
        *,
        max_wait_finalize: int = 3,
    ) -> None:
        asyncio.get_running_loop()
        self.queue: asyncio.Queue[_T] = asyncio.Queue()
        self.max_wait: float = max_wait
        self.max_wait_finalize: int = max_wait_finalize
        self.max_quantity: int = max_quantity
        self.callback: Callable[[Sequence[_T]], Awaitable] = async_callback
        self.task: Optional[asyncio.Task] = None
        self._alive: bool = False

    def start(self) -> None:
        if self.task is not None:
            raise RuntimeError("Can't start a Cascade that's already running.")

        self._alive = True
        self.task = asyncio.create_task(self._loop())

    @overload
    def stop(self, wait: Literal[True]) -> Awaitable:
        ...

    @overload
    def stop(self, wait: Literal[False]) -> None:
        ...

    @overload
    def stop(self, wait: bool = False) -> Optional[Awaitable]:
        ...

    def stop(self, wait: bool = False) -> Coroutine[Any, Any, None] | None:  # type: ignore
        self._alive = False
        if wait:
            return self.queue.join()

    def put(self, item: _T) -> None:
        if not self._alive:
            raise RuntimeError("Can't put items into a Cascade that's not running.")
        self.queue.put_nowait(item)

    async def _loop(self) -> None:
        try:
            while self._alive:
                queue_items: Sequence[_T] = []
                iter_start: float = time.monotonic()

                while (this_max_wait := (time.monotonic() - iter_start)) < self.max_wait:
                    try:
                        n = await asyncio.wait_for(self.queue.get(), this_max_wait)
                    except asyncio.TimeoutError:
                        continue
                    else:
                        queue_items.append(n)
                    if len(queue_items) >= self.max_quantity:
                        break

                    if not queue_items:
                        continue

                num_items: int = len(queue_items)

                asyncio.create_task(self.callback(queue_items))  # type: ignore

                for _ in range(num_items):
                    self.queue.task_done()

        except asyncio.CancelledError:
            log.debug("Recieved cascade cancellation.")
        finally:
            f: asyncio.Task[None] = asyncio.create_task(self._finalize(), name="robolia.cascade.finalizer")
            try:
                await asyncio.wait_for(f, timeout=self.max_wait_finalize)
            except asyncio.TimeoutError:
                log.info("Max wait during cascade finalization occurred.")

    async def _finalize(self) -> None:
        self._alive = False
        remaining_items: Sequence[_T] = []

        while not self.queue.empty():
            try:
                ev = self.queue.get_nowait()
            except asyncio.QueueEmpty:
                # I should never hit this, asyncio queues know their size reliably
                break

            remaining_items.append(ev)

        if not remaining_items:
            return

        num_remaining: int = len(remaining_items)
        pending_futures = []

        for chunk in (remaining_items[p : p + self.max_quantity] for p in range(0, num_remaining, self.max_quantity)):
            fut = asyncio.create_task(self.callback(chunk), name="robolia.cascade.finalizing_task")  # type: ignore
            pending_futures.append(fut)

        gathered = asyncio.create_task(
            asyncio.gather(*pending_futures),
            name="robolia.cascade.finalizing_task",
        )

        try:
            await asyncio.wait_for(gathered, timeout=self.max_wait_finalize)  # type: ignore
        except asyncio.TimeoutError:
            for task in pending_futures:
                task.cancel()

        for _ in range(num_remaining):
            self.queue.task_done()


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
