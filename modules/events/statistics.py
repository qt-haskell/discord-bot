from __future__ import annotations

from logging import getLogger, Logger
from typing import TYPE_CHECKING, ClassVar

import discord
from discord.ext import commands

from .base import BaseEventCog

if TYPE_CHECKING:
    from discord import Member

__all__: tuple[str, ...] = ("Statistics",)


log: Logger = getLogger(__name__)


class Statistics(BaseEventCog):

    __presence_map: ClassVar[dict[discord.Status, str]] = {
        discord.Status.online: "Online",
        discord.Status.idle: "Idle",
        discord.Status.dnd: "DND"
    }

    @commands.Cog.listener("on_presence_update")
    async def store_presence_updates(self, before: Member, after: Member) -> None:
        if before.status == after.status:
            return
        
        if await self.bot.redis.get(f"presence:{after.id}") is not None:
            # Since discord.py sends us this event for every guild the member is in.
            # Tbqh, I'm not sure why discord.py does this, but it does.
            return
        
        log.debug(f"Presence update for {after.name} from {before.status} -> {after.status}")
        await self.bot.redis.setex(f"presence:{after.id}", 5, self.__presence_map.get(after.status, "Offline"))
        
        await self.bot.safe_connection.execute(
            "SELECT insert_into_presence_history($1, $2)", after.id, self.__presence_map.get(after.status, "Offline")
        )
