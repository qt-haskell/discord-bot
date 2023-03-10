from __future__ import annotations

import attr
from abc import ABC, abstractmethod
from collections import defaultdict
from contextlib import asynccontextmanager
from logging import Logger, getLogger
from types import TracebackType
from typing import TYPE_CHECKING, Any, AsyncGenerator, Optional, Sequence, Type

from asyncpg import Pool, Record
from asyncpg.pool import PoolConnectionProxy
from asyncpg.transaction import Transaction

__all__: tuple[str, ...] = ("PostgreSQLManager",)


log: Logger = getLogger(__name__)


class ConnectionStrategy(ABC):
    @abstractmethod
    async def acquire_connection(self) -> PoolConnectionProxy[Record]:
        pass

    @abstractmethod
    async def release_connection(self) -> None:
        pass


class DefaultConnectionStrategy(ConnectionStrategy):
    __slots__: tuple[str, ...] = ("pool", "timeout", "_connection", "_transaction")

    def __init__(self, pool: Pool, timeout: float = 10.0) -> None:
        self.pool: Pool[Any] = pool
        self.timeout: float = timeout

        self._connection: PoolConnectionProxy[Record]
        self._transaction: Transaction

    async def acquire_connection(self) -> PoolConnectionProxy[Record]:
        return await self.__aenter__()

    async def release_connection(self) -> None:
        await self.__aexit__(None, None, None)

    async def __aenter__(self) -> PoolConnectionProxy[Record]:
        self._connection = await self.pool.acquire(timeout=self.timeout)
        self._transaction = self._connection.transaction()
        await self._transaction.start()
        return self._connection

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        if exc_val and self._transaction is not None:
            log.warning("Rolling back transaction due to exception", exc_info=True)
            await self._transaction.rollback()

        if self._transaction is not None and not exc_val:
            await self._transaction.commit()

        if self._connection is not None:
            await self.pool.release(self._connection)


class BaseManager:
    __slots__: tuple[str, ...] = ("strategy", "logger")

    def __init__(self, strategy: ConnectionStrategy) -> None:
        self.strategy: ConnectionStrategy = strategy

    @asynccontextmanager
    async def acquire_connection(self) -> AsyncGenerator[PoolConnectionProxy[Record], None]:
        connection: PoolConnectionProxy[Record] = await self.strategy.acquire_connection()
        try:
            yield connection
        finally:
            await self.strategy.release_connection()

    async def execute(
        self,
        query: str,
        *args: Any,
        timeout: Optional[float] = 10.0,
        **kwargs: Any,
    ) -> None:
        async with self.acquire_connection() as connection:
            await connection.execute(query, *args, timeout=timeout, **kwargs)

    async def fetch(
        self,
        query: str,
        *args: Any,
        timeout: Optional[float] = 10.0,
        **kwargs: Any,
    ) -> list[Record]:
        async with self.acquire_connection() as connection:
            return await connection.fetch(query, *args, timeout=timeout, **kwargs)

    async def fetchone(
        self,
        query: str,
        *args: Any,
        timeout: Optional[float] = 10.0,
        **kwargs: Any,
    ) -> Optional[Record]:
        async with self.acquire_connection() as connection:
            return await connection.fetchrow(query, *args, timeout=timeout, **kwargs)

    async def executemany(
        self,
        query: str,
        args: Sequence[Any],
        timeout: Optional[float] = 10.0,
        **kwargs: Any,
    ) -> None:
        async with self.acquire_connection() as connection:
            await connection.executemany(query, args, timeout=timeout, **kwargs)

    async def reaveal_table(self, table: str) -> dict[str, dict[str, str]]:
        tables: dict[str, dict[str, str]] = defaultdict(dict)

        async with self.acquire_connection() as connection:
            async for record in connection.cursor(
                """
                SELECT * FROM information_schema.columns
                WHERE $1::TEXT IS NULL OR table_name = $1::TEXT
                ORDER BY
                table_schema = 'pg_catalog',
                table_schema = 'information_schema',
                table_catalog,
                table_schema,
                table_name,
                ordinal_position;
                """,
                table,
            ):
                table_name: str = f"{record['table_schema']}.{record['table_name']}"
                tables[table_name][record["column_name"]] = str(record["data_type"]).upper() + (
                    " NOT NULL" if record["is_nullable"] == "NO" else ""
                )

            return tables


class PostgreSQLManager(BaseManager):
    """A manager for PostgreSQL databases.

    Example
    -------
    >>> async with PostgreSQLManager(pool) as manager:
    ...     await manager.execute("INSERT INTO table (column) VALUES ($1)", 1)

    Parameters
    ----------
    pool : `Pool`
        The pool to use for connections.
    timeout : `float`
        The timeout to use for acquiring connections.
    logger : `Optional[logging.Logger]`
        The logger to use for logging.
    """

    __slots__: tuple[str, ...] = ("pool", "timeout")

    def __init__(
        self,
        pool: Pool[Any],
        timeout: float = 10.0,
    ) -> None:
        super().__init__(
            DefaultConnectionStrategy(pool, timeout=timeout),
        )


@attr.s(auto_attribs=True, kw_only=True, slots=True, weakref_slot=False)
class Counter:
    """A custom counter for the bot."""
    current_count: str = attr.ib(default="0")

    def inc(self, string) -> str:
        return (
            string
            and [
                [string[:-1] + chr(ord(string[-1:]) + 1), self.inc(string[:-1]) + "0"][string[-1:] > "y"],
                string[:-1] + "a",
            ][string[-1:] == "9"]
        ) or "0"

    async def increment(self, pool: Pool[Any]) -> None:
        self.current_count = self.inc(self.current_count)
        await self.save(pool)

    @classmethod
    async def get_state(cls, pool: Pool[Any]) -> Counter:
        async with pool.acquire() as connection:
            record: Any | None = await connection.fetchrow(
                "SELECT current_count FROM counter ORDER BY counter_id DESC LIMIT 1"
            )
            if record is None:
                return cls()
            return cls(current_count=record["current_count"])

    async def save(self, pool: Pool[Any]) -> None:
        async with pool.acquire() as connection:
            await connection.execute("INSERT INTO counter (current_count) VALUES ($1)", self.current_count)
