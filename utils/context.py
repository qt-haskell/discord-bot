from __future__ import annotations

import copy
import io
import logging
import re
from typing import TYPE_CHECKING, Any, Literal, Optional, Self, TypeVar

import discord
from discord.ext import commands

from .useful import suppress

if TYPE_CHECKING:
    from aiohttp import ClientSession

    from bot import RoboLia


__all__: tuple[str, ...] = ("RoboLiaContext", "_RLC")


log: logging.Logger = logging.getLogger(__name__)
_RLC = TypeVar("_RLC", bound="RoboLiaContext")


class RoboLiaContext(commands.Context["RoboLia"]):
    if TYPE_CHECKING:
        bot: RoboLia
        message: discord.Message
        guild: discord.Guild
        channel: discord.TextChannel

    @property
    def clean_prefix(self) -> str:
        repl: str = f"@{self.me.display_name}".replace("\\", r"\\")
        pattern: re.Pattern[str] = re.compile(rf" < @!?{self.me.id}>")
        assert self.prefix is not None, "typechecking grrr"
        return pattern.sub(repl, self.prefix)

    @property
    def reference(self) -> discord.Message | Literal[False] | None:
        message: Any | None = getattr(self.message, "reference", None)
        return isinstance(message, discord.Message) and message or None

    @property
    def referenced_user(self) -> discord.Member | discord.User | Literal[False]:
        return isinstance(self.reference, discord.Message) and self.reference.author

    @property
    def session(self) -> ClientSession:
        return self.bot.session

    async def send_help(self, command: Optional[commands.Command | str] = None) -> None:
        # Opinionated choice that the help should default to the current command
        command = command or self.command
        await super().send_help(command)

    async def safe_send(self, content: str = "", **kwargs: Any) -> Optional[discord.Message]:
        if kwargs.pop("file", None):
            raise ValueError("Files are incompatible with safe_send.")

        if len(content) <= 2000:
            return await self.send(content, **kwargs)

        fp = io.BytesIO(content.encode("utf-8"))
        return await self.send(file=discord.File(fp, filename="response.txt"), **kwargs)

    async def maybe_reply(
        self, content: Optional[str] = None, mention_author: bool = False, **kwargs: Any
    ) -> Optional[discord.Message]:
        with suppress(discord.HTTPException, capture=False):
            resolved_message: discord.Message | discord.DeletedReferencedMessage | None = (
                self.message.reference and self.message.reference.resolved
            )
            return await (resolved_message.reply if resolved_message else self.send)(  # type: ignore
                content=content, mention_author=mention_author, **kwargs
            )

    async def copy_with(self, *, author=None, channel=None, **kwargs) -> Self:
        msg: discord.Message = copy.copy(self.message)
        msg._update(kwargs)  # type: ignore

        if author is not None:
            msg.author = author
        if channel is not None:
            msg.channel = channel

        msg.content = kwargs["content"]

        return await self.bot.get_context(msg, cls=type(self))
