# -*- coding: utf-8 -*-
from typing import Any, Mapping, Optional

import arrow
from bring.pkg_index import BringIndexTing
from bring.pkg_index.pkg import PkgTing
from bring.pkg_index.pkgs import Pkgs
from bring.utils import BringTaskDesc
from frtls.tasks import ParallelTasksAsync, SingleTaskAsync, Task
from tings.makers import TingMaker
from tings.ting import TingMeta


class BringDynamicIndexTing(BringIndexTing):
    def __init__(self, name: str, meta: TingMeta, parent_key: str = "parent"):

        super().__init__(name=name, parent_key=parent_key, meta=meta)

        self._pkg_namespace = f"bring.indexes.{self.name}.pkgs"
        self._pkg_list: Pkgs = self._tingistry_obj.create_singleting(  # type: ignore
            name=self._pkg_namespace,
            ting_class="pkgs",
            subscription_namespace=self._pkg_namespace,
            bring_index=self,
        )
        self._maker_config: Optional[Mapping[str, Any]] = None
        self._maker: Optional[TingMaker] = None

        self._metadata_timestamp: Optional[str] = None

    async def init(self, config: Mapping[str, Any]) -> None:

        maker = await self.get_maker(config)
        await maker.sync()
        self._metadata_timestamp = str(arrow.Arrow.now())

    async def _get_metadata_timestamp(self) -> Optional[str]:

        return self._metadata_timestamp

    async def _get_pkgs(self) -> Mapping[str, PkgTing]:

        return self._pkg_list.pkgs

    async def _create_update_tasks(self) -> Optional[Task]:

        task_desc = BringTaskDesc(
            name=f"metadata update {self.name}",
            msg=f"updating metadata for index '{self.name}'",
        )
        tasks = ParallelTasksAsync(task_desc=task_desc)
        pkgs = await self.get_pkgs()
        for pkg_name, pkg in pkgs.items():
            td = BringTaskDesc(
                name=f"{pkg_name}",
                msg=f"updating metadata for pkg '{pkg_name}' (index: {self.name})",
            )
            t = SingleTaskAsync(pkg.update_metadata, task_desc=td, parent_task=tasks)
            tasks.add_task(t)

        return tasks

    async def get_maker(self, config) -> TingMaker:

        # TODO: revisit typing here
        if self._maker is not None:
            if config != self._maker_config:
                raise Exception("Maker config changed, this is not supported yet...")
            return self._maker  # type: ignore

        maker_name = f"bring.pkg_maker.{self.name}"
        self._maker_config = config
        self._maker = self._tingistry_obj.create_singleting(  # type: ignore
            name=maker_name,
            ting_class="text_file_ting_maker",
            prototing="bring.types.dynamic_pkg",
            ting_name_strategy="basename_no_ext",
            ting_target_namespace=self._pkg_namespace,
            file_matchers=[{"type": "extension", "regex": ".*\\.br.pkg"}],
        )

        indexes = config.get("indexes", [])
        for index in indexes:
            self._maker.add_base_paths(index)  # type: ignore

        return self._maker  # type: ignore
