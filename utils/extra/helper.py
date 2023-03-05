from __future__ import annotations

import functools
from typing import Optional

import discord

__all__: tuple[str, ...] = (
    "bold",
    "underline",
    "linkify",
    "quote",
    "codeblock",
    "quoteblock",
    "cutoff",
    "hex_to_colour",
    "colour_to_hex",
)


def bold(text: str, italic: bool = False) -> str:
    return f"**{'*' if italic else ''}{text}{'*' if italic else ''}**"


def underline(text: str) -> str:
    return f"__{text}__"


def linkify(title: str, url: str) -> str:
    return f"[{title}]({url})"


def quote(text: str) -> str:
    return f"> {text}"


def codeblock(text: str, code: Optional[str] = None, triple: bool = False) -> str:
    return f"{'```' if triple else '`'}{code or ''} {text} {'```' if triple else '`'}"


quoteblock: functools.partial[str] = functools.partial(codeblock, triple=True)


def cutoff(text: str, length: int = 2000, suffix: str = "...") -> str:
    if len(text) <= length:
        return text
    return text[: length - len(suffix)] + suffix


def hex_to_colour(hex: str) -> discord.Colour:
    return discord.Colour(int(hex[1:], 16))


def colour_to_hex(colour: discord.Colour) -> str:
    return f"#{colour.value:0>6x}"
