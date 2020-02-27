# -*- coding: utf-8 -*-
import logging
import shutil
from typing import Any, Iterable, Mapping

from anyio import create_task_group
from bring.mogrify import Mogrifier, Transmogrificator
from bring.mogrify.merge import MergeMogrifier
from frtls.tasks import RunWatch, Tasks


log = logging.getLogger("bring")


class ParallelPkgsAsync(Tasks):
    def __init__(self, **kwargs):

        super().__init__(**kwargs)

    async def run_async(self, *watchers: "RunWatch") -> None:

        async with create_task_group() as tg:
            for child in self._children.values():
                await tg.spawn(child.run_async, *watchers)


class ParallelPkgMergeMogrifier(Mogrifier):

    _plugin_name: str = "parallel_pkg_merge"

    def requires(self) -> Mapping[str, str]:

        return {"transmogrificators": "list", "watchers": "list", "merge": "any"}

    def get_msg(self) -> str:

        return "merging multiple pkgs"

    def provides(self) -> Mapping[str, str]:

        return {"folder_path": "string"}

    async def cleanup(self, result: Mapping[str, Any], *value_names, **requirements):

        shutil.rmtree(result["folder_path"])

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        tms: Iterable[Transmogrificator] = requirements["transmogrificators"]
        watchers: Iterable[RunWatch] = requirements["watchers"]
        merge: MergeMogrifier = requirements["merge"]

        tasks = ParallelPkgsAsync()
        for tm in tms:
            tasks.add_task(tm)

        await tasks.run_async(*watchers)

        folders = []
        for tm in tasks._children.values():
            folder = tm._last_item.current_state["folder_path"]
            folders.append(folder)

        merge.input.set_values(**{"folder_paths": folders})

        vals = await merge.get_values()
        return vals
