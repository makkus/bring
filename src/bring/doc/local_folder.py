# -*- coding: utf-8 -*-
from typing import Any, Mapping, Optional

from bring.merge_strategy import LocalFolder
from frtls.async_helpers import wrap_async_task
from frtls.doc.explanation import Explanation
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

            result.append(f"  [bold italic]{rel_path}[/bold italic]:")
            for k, v in sorted(data.items()):
                if k == "hash":
                    continue
                elif k == "vars":
                    result.append(f"     {k}:")
                    for vk, vv in v.items():
                        result.append(f"       {vk}: [italic]{vv}[/italic]")
                else:
                    result.append(f"     {k}: [italic]{v}[/italic]")
            result.append("")

        return result
