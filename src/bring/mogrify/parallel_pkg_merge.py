# -*- coding: utf-8 -*-
import logging
from typing import Any, List, Mapping, Optional

from anyio import create_task_group
from bring.mogrify import Mogrifier, Transmogrificator
from frtls.tasks import Tasks


log = logging.getLogger("bring")


class ParallelPkgMergeMogrifier(Mogrifier, Tasks):

    _plugin_name: str = "parallel_pkg_merge"

    def __init__(self, name: str, meta: Optional[Mapping[str, Any]], **kwargs):

        self._mogrificators: List[Transmogrificator] = []
        self._merge_task: Optional[Mogrifier] = None

        Tasks.__init__(self, **kwargs)
        Mogrifier.__init__(self, name=name, meta=meta, **kwargs)

    def add_mogrificators(self, *mogrificators: Transmogrificator):

        if self._started:
            raise Exception("Can't add child mogrifiers: already started")

        for m in mogrificators:
            self.add_task(m)

    def set_merge_task(self, merge_task: Mogrifier):

        self._merge_task = merge_task
        self._merge_task.parent_task = self
        self._merge_task.working_dir = self.working_dir

    def requires(self) -> Mapping[str, str]:

        return {"pipeline_id": "string", "merge": "any"}

    def get_msg(self) -> str:

        return "merging multiple pkgs"

    def provides(self) -> Mapping[str, str]:

        return {"folder_path": "string"}

    async def execute(self) -> Any:

        return await self.get_values()

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        if self._merge_task is None:
            raise Exception("Can't execute parallel package merge. Merge task not set.")

        async with create_task_group() as tg:
            for tm in self._children.values():
                await tg.spawn(tm.transmogrify)  # type: ignore

        folders = []
        for tm in self._children.values():
            folder = tm._last_item.current_state["folder_path"]  # type: ignore
            folders.append(folder)

        self._merge_task.input.set_values(**{"folder_paths": folders})
        vals = await self._merge_task.run_async()
        return vals
