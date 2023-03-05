from __future__ import annotations

import asyncio
import functools
import itertools
import os
import pathlib
import re
from asyncio import AbstractEventLoop, to_thread
from collections import defaultdict
from logging import Logger, getLogger
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    DefaultDict,
    Iterable,
    Iterator,
    Mapping,
    ParamSpec,
    Self,
    Type,
    TypeVar,
)

import aiohttp
import asyncpg
import discord
from discord.ext import commands
from redis.asyncio import Redis

from base import Gateway, PostgreSQLManager
from utils import _RLC, RoboLiaContext

if TYPE_CHECKING:
    from datetime import datetime

    from aiohttp import ClientSession
    from asyncpg import Connection, Pool, Record


_RLT = TypeVar("_RLT", bound="RoboLia")
_T = TypeVar("_T")
_P = ParamSpec("_P")


class RoboLia(commands.Bot):
    if TYPE_CHECKING:
        user: discord.ClientUser
        cogs: Mapping[str, commands.Cog]

        # Lies I tell my linter
        timestamp: datetime

    def __init__(
        self,
        *,
        loop: AbstractEventLoop,
        session: ClientSession,
        pool: Pool,
        redis: Redis,
    ) -> None:
        intents: discord.Intents = discord.Intents(
            guilds=True,
            members=True,
            messages=True,
            message_content=True,
            presences=True,
        )

        super().__init__(
            command_prefix=self.get_prefix,  # type: ignore
            case_insensitive=True,
            intents=intents,
            strip_after_prefix=True,
            chung_guilds_at_startup=False,
            max_messages=2000,
            owner_ids=[
                852419718819348510,  # Lia Marie (https://github.com/qt-haskell)
                546691865374752778,  # Utkarsh   (https://github.com/utkarshgupta2504)
            ],
            description=("This is R. Lia, a personal-use Discord bot " "that also happens to be open-source! 😸"),
        )

        self.loop: AbstractEventLoop = loop
        self.session: ClientSession = session
        self.pool: Pool[Record] = pool
        self.redis: Redis = redis

        self.cached_prefixes: DefaultDict[int, list[re.Pattern[str]]] = defaultdict(list)

    @discord.utils.cached_property
    def logger(self) -> Logger:
        return getLogger("robolia")

    @classmethod
    @discord.utils.copy_doc(asyncpg.create_pool)
    def setup_pool(cls: Type[Self], *, dsn: str, **kwargs: Any) -> Pool[Record]:
        def serializer(obj: Any) -> str:
            return discord.utils._to_json(obj)

        def deserializer(s: str) -> Any:
            return discord.utils._from_json(s)

        prep_init: Any | None = kwargs.pop("init", None)

        async def init(conn: Connection[Any]) -> None:
            await conn.set_type_codec(
                typename="json",
                encoder=serializer,
                decoder=deserializer,
                schema="pg_catalog",
                format="text",
            )
            if prep_init is not None:
                await prep_init(conn)

        pool: Pool[asyncpg.Record] = asyncpg.create_pool(dsn, init=init, **kwargs)
        return pool

    @classmethod
    async def setup_redis(cls: Type[Self], *, url: str, **kwargs: Any) -> Redis:
        try:
            return await Redis.from_url(url, **kwargs)
        except Exception as exc:
            raise

    async def get_prefix(self, message: discord.Message) -> list[str] | str:
        return commands.when_mentioned_or(*("pls", "pls "))(self, message)

    async def get_context(self, message: discord.Message, *, cls: Type[_RLC] = RoboLiaContext) -> RoboLiaContext:
        return await super().get_context(message, cls=cls or commands.Context[_RLT])

    async def process_commands(self, message: discord.Message, /) -> None:
        try:
            await asyncio.wait_for(self.wait_until_ready(), timeout=5.0)
        except asyncio.TimeoutError:
            return

        ctx: RoboLiaContext = await self.get_context(message, cls=RoboLiaContext)
        if ctx.command is None:
            return

        if ctx.guild:
            if TYPE_CHECKING:
                # These are lies, but correct enough
                assert isinstance(ctx.channel, (discord.TextChannel, discord.Thread))
                assert isinstance(ctx.me, discord.Member)

            if not ctx.channel.permissions_for(ctx.me).send_messages:
                if await self.is_owner(ctx.author):
                    await ctx.send("I do not have permission to send messages in this channel.")

                return

        await self.invoke(ctx)

    async def close(self) -> None:
        self.logger.info("Closing RoboLia...")
        await asyncio.sleep(1)

        # Do not remove, allows graceful disconnects
        to_close = [self.session, self.pool, self.redis]
        await asyncio.gather(*[x.close() for x in to_close if x is not None])

        await super().close()

    async def wrap(self, func: Callable[_P, _T], *args: _P.args, **kwargs: _P.kwargs) -> _T:
        return await to_thread(func, *args, **kwargs)

    def chunk(self, iterable: Iterable[_T], size: int) -> Iterator[list[_T]]:
        it: Iterator[_T] = iter(iterable)
        while chunk := list(itertools.islice(it, size)):
            yield chunk

    def get_extensions(self) -> Iterator[str]:
        extensions: list[str] = [file for file in os.listdir("modules") if not file.startswith(("__", "_"))]
        for extension in extensions:
            yield f"modules.{extension[:-3] if extension.endswith('.py') else extension}"

    def get_schemas(self) -> Iterator[pathlib.Path]:
        root: pathlib.Path = pathlib.Path("schemas")
        for schema in itertools.chain((root / "prerequisites").glob("*.sql"), (root / "additional").glob("*.sql")):
            yield schema

    async def setup_hook(self) -> None:
        for extension in self.get_extensions():
            try:
                await self.load_extension(extension)
            except Exception as exc:
                self.logger.exception(f"Failed to load extension {extension!r}", exc_info=exc)

        for schema in self.get_schemas():
            try:
                await self.pool.execute(schema.read_text())
            except Exception as exc:
                self.logger.exception(f"Failed to load schema {schema!r}", exc_info=exc)

    async def on_ready(self) -> None:
        self.logger.info("Connected to Discord.")

        if getattr(self, "timestamp", None) is None:
            self.timestamp = discord.utils.utcnow()

    def exec(self, func: Callable[..., _T], *args, **kwargs) -> Awaitable[_T]:
        return self.loop.run_in_executor(None, functools.partial(func, *args, **kwargs))

    async def connect(self, *, reconnect: bool = True) -> None:
        backoff = discord.client.ExponentialBackoff()  # type: ignore
        ws_params: dict[str, Any] = {"initial": True, "shard_id": self.shard_id}
        while not self.is_closed():
            try:
                coro: Any = Gateway.from_client(self, **ws_params)
                self.ws = await asyncio.wait_for(coro, timeout=60.0)
                ws_params["initial"] = False
                while True:
                    await self.ws.poll_event()
            except discord.client.ReconnectWebSocket as e:
                self.logger.info("Got a request to %s the websocket.", e.op)
                self.dispatch("disconnect")
                ws_params.update(
                    sequence=self.ws.sequence,
                    resume=e.resume,
                    session=self.ws.session_id,
                )
                continue
            except (
                OSError,
                discord.HTTPException,
                discord.GatewayNotFound,
                discord.ConnectionClosed,
                aiohttp.ClientError,
                asyncio.TimeoutError,
            ) as exc:
                self.dispatch("disconnect")
                if not reconnect:
                    await self.close()
                    if isinstance(exc, discord.ConnectionClosed) and exc.code == 1000:
                        return
                    raise

                if self.is_closed():
                    return

                if isinstance(exc, OSError) and exc.errno in (54, 10054):
                    ws_params.update(
                        sequence=self.ws.sequence,
                        initial=False,
                        resume=True,
                        session=self.ws.session_id,
                    )
                    continue

                if isinstance(exc, discord.ConnectionClosed):
                    if exc.code == 4014:
                        raise discord.PrivilegedIntentsRequired(exc.shard_id) from None
                    if exc.code != 1000:
                        await self.close()
                        raise

                retry: float = backoff.delay()
                self.logger.exception("Attempting a reconnect in %.2fs.", retry)
                await asyncio.sleep(retry)
                ws_params.update(sequence=self.ws.sequence, resume=True, session=self.ws.session_id)

    async def connection(self, *, timeout: float = 10.0) -> PostgreSQLManager:
        return PostgreSQLManager(self.pool, timeout=timeout)
