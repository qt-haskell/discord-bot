from __future__ import annotations

from typing import TYPE_CHECKING, Any

from discord.ext import commands

if TYPE_CHECKING:
    from bot import RoboLia


__all__: tuple[str, ...] = ("BaseEventCog",)


class BaseEventCog(commands.Cog):
    __slots__: tuple[str, ...] = ("bot",)

    def __init__(self, bot: RoboLia) -> None:
        self.bot: RoboLia = bot
