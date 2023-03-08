from __future__ import annotations

from typing import TYPE_CHECKING, Type

from discord.ext import commands
from .statistics import Statistics

if TYPE_CHECKING:
    from bot import RoboLia

__all__: tuple[str, ...] = ("Events",)


exts: tuple[Type[commands.Cog]] = (Statistics,)


class Events(*exts):
    def __init__(self, bot: RoboLia) -> None:
        self.bot: RoboLia = bot


async def setup(bot: RoboLia) -> None:
    await bot.add_cog(Events(bot))
