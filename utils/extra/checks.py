from __future__ import annotations

from discord.ext import commands

from utils import RoboLiaContext

__all__: tuple[str, ...] = (
    "creator_in_guild",
    "is_guild_owner",
)


def creator_in_guild():
    async def predicate(ctx: RoboLiaContext) -> bool:
        if ctx.guild:
            return await ctx.bot.is_owner(ctx.author)
        return False

    return commands.check(predicate)


def is_guild_owner():
    async def predicate(ctx: RoboLiaContext) -> bool:
        return ctx.author == ctx.guild.owner

    return commands.check(predicate)
