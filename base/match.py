from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Literal, Optional

from pandas import DataFrame

__all__: tuple[str, ...] = ("BaseMatch",)


class BaseMatch(ABC):
    def __init__(self, mode: int = 0) -> None:
        self.mode: int = mode
        self.type: Literal["match"] = "match"

    @abstractmethod
    def match(self, target: str, options: Optional[List[str]] = None, **kwargs) -> DataFrame:
        raise NotImplementedError()
