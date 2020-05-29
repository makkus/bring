# -*- coding: utf-8 -*-
from abc import ABCMeta
from typing import Any, Mapping, Optional

from frtls.async_helpers import wrap_async_task
from rich.console import Console, ConsoleOptions, RenderResult


class Explanation(metaclass=ABCMeta):
    def __init__(self, data: Any):

        self._data: Any = data
        self._explanation_data: Optional[Mapping[str, Any]] = None

    @property
    def data(self):

        return self._data

    async def _load(self) -> None:

        self._explanation_data = await self.create_explanation_data()

    @property
    def explanation_data(self) -> Mapping[str, Any]:

        if self._explanation_data is None:
            wrap_async_task(self._load)
        return self._explanation_data  # type: ignore

    # @abstractmethod
    async def create_explanation_data(self) -> Mapping[str, Any]:
        pass


class SimpleExplanation(Explanation):
    def __init__(self, data: Any, data_name: "str" = "data"):

        self._data_name: str = data_name
        super().__init__(data)

    async def create_explanation_data(self) -> Mapping[str, Any]:

        return {self._data_name: self._data}


class StepsExplanation(Explanation):
    def __init__(self, steps_map: Mapping[str, Any]):

        self._steps_map = steps_map

    def __console__(self, console: Console, options: ConsoleOptions) -> RenderResult:

        result = []

        result.append("\n[bold]Steps[/bold]:")

        result.append("")
        for v in self._steps_map.values():
            result.append(f"  - [italic]{v}[/italic]")

        return result
