from __future__ import annotations

from asyncio import AbstractEventLoop, CancelledError, get_event_loop, run
from logging import Logger, getLogger
from os import environ
from typing import TYPE_CHECKING

from aiohttp import ClientSession

from base import Settings, setup_logging
from bot import RoboLia
from utils import suppress

if TYPE_CHECKING:
    from asyncpg import Pool, Record
    from redis.asyncio import Redis

log: Logger = getLogger(__name__)

environ['JISHAKU_NO_UNDERSCORE'] = 'true'
environ['JISHAKU_NO_DM_TRACEBACK'] = 'true'
environ['JISHAKU_RETAIN'] = 'true'

settings: Settings = Settings()  # type: ignore


async def setup() -> tuple[RoboLia, Pool[Record], ClientSession]:
    setup_logging(settings.LOG_LEVEL)

    loop: AbstractEventLoop = get_event_loop()
    session: ClientSession = ClientSession()

    try:
        pool: Pool[Record] = await RoboLia.setup_pool(dsn=settings.dsn)  # type: ignore
        redis: Redis = await RoboLia.setup_redis(url=settings.redis)  # type: ignore

        log.info("PostgreSQL and Redis successfully connected.")
    except Exception as exc:
        raise exc

    try:
        bot: RoboLia = RoboLia(loop=loop, session=session, pool=pool, redis=redis)
        log.info("Successfully created a bot instance.")
    except Exception as exc:
        raise exc

    return bot, pool, session


async def main() -> None:
    bot, pool, session = await setup()

    async with bot, pool, session:
        try:
            await bot.start(settings.TOKEN)
        except Exception as exc:
            log.exception("Failed to start the bot.", exc_info=exc)


if __name__ == "__main__":
    with suppress(KeyboardInterrupt, CancelledError, capture=False):
        run(main())
