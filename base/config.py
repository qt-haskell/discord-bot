from __future__ import annotations

import logging
import sys
from collections import deque
from typing import AbstractSet, Any, Generator, Iterator, Optional, Self, Type

import coloredlogs
import discord
from pydantic import BaseSettings
from pydantic.fields import ModelField

__all__: tuple[str, ...] = ("Settings", "setup_logging", "Gateway")

log: logging.Logger = logging.getLogger(__name__)
GeneratorType: Type[Generator[int, None, None]] = type(i for i in [1])


class Settings(BaseSettings):
    TOKEN: str
    DEBUG_HOOK: int
    DEBUG_GUILD: int

    OWNER_IDS: list[int]
    TRANSCRIPTS: list[int]

    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int

    DD_API_KEY: Optional[str]

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int

    LOG_LEVEL: str = "INFO"

    @property
    def guild(self) -> discord.abc.Snowflake:
        return discord.Object(id=self.DEBUG_GUILD)

    @property
    def owners(self) -> Iterator[discord.abc.Snowflake]:
        for owner_id in self.OWNER_IDS:
            yield discord.Object(id=owner_id)

    @property
    def transcripts(self) -> Iterator[int]:
        for transcript in self.TRANSCRIPTS:
            yield transcript

    @property
    def hook(self) -> int:
        return self.DEBUG_HOOK

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def redis(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    class Config(BaseSettings.Config):
        env_file: str = ".env"
        env_file_encoding: str = "utf-8"
        allow_mutation: bool = False

        @staticmethod
        def _sequence_like(value: Any) -> bool:
            return isinstance(value, (list, tuple, set, frozenset, GeneratorType, deque))

        @classmethod
        def prepare_field(cls, field: ModelField) -> None:
            env_names: list[str] | AbstractSet[str]  # bite me
            field_info_from_config: dict[str, Any] = cls.get_field_info(field.name)
            env: Any | None = field_info_from_config.get("env") or field.field_info.extra.get("env")
            if env is None:
                if field.has_alias:
                    log.warning(
                        "No env name set for field %s, using alias %s",
                        field.name,
                        field.alias,
                    )
                env_names = {cls.env_prefix + field.name}
            elif isinstance(env, str):
                env_names = {env}
            elif isinstance(env, (set, frozenset)):
                env_names = env
            elif cls._sequence_like(env):
                env_names = list(env)
            else:
                raise TypeError(f"Invalid field env type {type(env)} for field {field.name}")

            if not cls.case_sensitive:
                env_names = env_names.__class__(n.lower() for n in env_names)
            field.field_info.extra["env_names"] = env_names


class Gateway(discord.gateway.DiscordWebSocket):  # type: ignore
    # discord.py doesn't support mobile gateway
    async def identify(self) -> None:
        payload: dict[str, Any] = {
            "op": self.IDENTIFY,
            "d": {
                "token": self.token,
                "properties": {
                    "$os": sys.platform,
                    "$browser": "Discord Android",
                    "$device": "Discord Android",
                    "$referrer": "",
                    "$referring_domain": "",
                },
                "compress": True,
                "large_threshold": 250,
                "v": 10,
            },
        }

        if self.shard_id is not None and self.shard_count is not None:
            payload["d"]["shard"] = [self.shard_id, self.shard_count]

        state: Any = self._connection
        if state._activity is not None or state._status is not None:
            payload["d"]["presence"] = {
                "status": state._status,
                "game": state._activity,
                "since": 0,
                "afk": False,
            }

        if state._intents is not None:
            payload["d"]["intents"] = state._intents.value

        await self.call_hooks("before_identify", self.shard_id, initial=self._initial_identify)
        await self.send_as_json(payload)
        log.info("Shard ID %s has sent the IDENTIFY payload.", self.shard_id)


def setup_logging(level: int | str) -> None:
    """Call this before doing anything else"""
    coloredlogs.install(
        level=level,
        fmt="[%(asctime)s][%(name)s][%(levelname)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        field_styles={
            "asctime": {"color": "cyan"},
            "hostname": {"color": "magenta"},
            "levelname": {"bold": True, "color": "black"},
            "name": {"color": "blue"},
            "programname": {"color": "cyan"},
            "username": {"color": "yellow"},
        },
        level_styles={
            "debug": {"color": "magenta"},
            "info": {"color": "green"},
            "warning": {"color": "yellow"},
            "error": {"color": "red"},
            "critical": {"color": "red"},
        },
    )


class ReadOnlyProperty(property):
    def __set__(self, instance: Any, value: Any) -> None:
        raise AttributeError("Cannot set read-only property.")


class ConstantMeta(type):
    def __new__(cls, name, bases, attrs) -> Self:
        for attr_name, attr_value in attrs.items():
            if not callable(attr_value):
                if attr_name.startswith('__'):
                    continue
                if not attr_name.isupper() and not isinstance(attr_value, property):
                    log.warning(f"{name} attribute {attr_name} should be uppercase.")
                if isinstance(attr_value, property):
                    attrs[attr_name] = ReadOnlyProperty(attr_value.fget)
        return super().__new__(cls, name, bases, attrs)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("Cannot set attributes on a constant class.")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("Cannot delete attributes on a constant class.")


class Constants(metaclass=ConstantMeta):
    EMBED_COLOUR: int = 0xFFCCB4
    OWO: int = 408785106942164992
    BOT: int = 1059817715583430667
    ANIGAME: int = 571027211407196161

    @property
    def hidden(self) -> discord.PartialEmoji:
        return discord.PartialEmoji.from_str("🔒")

    @property
    def events(self) -> discord.PartialEmoji:
        return discord.PartialEmoji.from_str("🤖")

    @property
    def useful(self) -> discord.PartialEmoji:
        return discord.PartialEmoji.from_str("📚")

    @property
    def helper(self) -> discord.PartialEmoji:
        return discord.PartialEmoji.from_str("🔧")

    @property
    def invite(self) -> str:
        return discord.utils.oauth_url(
            client_id=self.BOT,
            permissions=discord.Permissions(permissions=0x60E55FEE0),
            # View Channels
            # Manage Emojis and Stickers
            # Manage Webhooks
            # Send Messages
            # Send Messages in Threads
            # Embed Links
            # Attach Files
            # Add Reactions
            # Use External Emojis
            # Use External Stickers
            # Manage Messages
            # Read Message History
            # Use Application Commands
            scopes=("bot", "applications.commands"),
        )
