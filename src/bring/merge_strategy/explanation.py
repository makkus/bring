# -*- coding: utf-8 -*-
import copy
from typing import Any, Mapping, Optional

from bring.merge_strategy import LocalFolder
from frtls.async_helpers import wrap_async_task
from frtls.doc.explanation import Explanation, to_value_string
from rich.console import Console, ConsoleOptions, RenderResult


class LocalFolderExplanation(Explanation):
    def __init__(self, local_folder: LocalFolder):

        self._local_folder: LocalFolder = local_folder
        self._managed_files: Optional[Mapping[str, Any]] = None

    async def _init(self):

        await self.get_managed_files()

    async def get_managed_files(self) -> Mapping[str, Any]:

        if self._managed_files is None:
            self._managed_files = await self._local_folder.get_managed_files()
        return self._managed_files

    async def create_explanation_data(self) -> Mapping[str, Any]:
        raise NotImplementedError()

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:

        if self._managed_files is None:
            wrap_async_task(self._init)

        result = []
        result.append(
            f"[bold]Path[/bold]: [italic]{self._local_folder.get_full_path()}[/italic]"
        )

        result.append("\n[bold]Managed files:[/bold]")
        result.append("")
        for rel_path, data in sorted(self._managed_files.items()):  # type: ignore

            data = copy.copy(data)
            data.pop("hash", None)
            result.append(f"  [bold italic]{rel_path}[/bold italic]:")

            value_string = to_value_string(data, reindent=4)
            result.append(value_string)
            result.append("")

        return result
