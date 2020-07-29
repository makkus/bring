# -*- coding: utf-8 -*-
from typing import Mapping, Optional

import arrow
from bring.pkg_index.config import IndexConfig
from bring.pkg_index.index import BringIndexTing
from bring.pkg_index.pkg import PkgTing
from bring.pkg_index.pkgs import Pkgs
from bring.utils import BringTaskDesc
from bring.utils.git import ensure_repo_cloned
from frkl.common.exceptions import FrklException
from frkl.common.strings import is_git_repo_url
from frkl.tasks.task import SingleTaskAsync, Task
from frkl.tasks.tasks import ParallelTasksAsync
from tings.makers import TingMaker
from tings.ting import TingMeta


class BringDynamicIndexTing(BringIndexTing):
    def __init__(self, name: str, meta: TingMeta):

        super().__init__(name=name, meta=meta)

        self._pkg_namespace = f"bring.indexes.{self.name}.pkgs"
        self._pkg_list: Pkgs = self._tingistry_obj.create_singleting(  # type: ignore
            name=self._pkg_namespace,
            ting_class="pkgs",
            subscription_namespace=self._pkg_namespace,
            bring_index=self,
        )
        self._maker_path: Optional[str] = None
        self._maker: Optional[TingMaker] = None

        self._metadata_timestamp: Optional[str] = None
        self._uri: Optional[str] = None

    async def init(self, config: IndexConfig) -> None:

        config_dict = config.index_type_config
        git_url = config_dict.get("git_url", None)
        path = config_dict.get("path", None)

        if path is None and git_url is None:
            raise FrklException(
                f"Can't create folder index with config: {config_dict}",
                reason="Neither 'path' nor 'git_url' value provided.",
            )

        if path and git_url:
            raise FrklException(
                f"Can't create folder index with config: {config_dict}",
                reason="Both 'path' and 'git_url' value provided.",
                solution="Only provide one of those keys.",
            )

        if git_url:
            self._uri = git_url
            if is_git_repo_url(git_url):
                _local_path = await ensure_repo_cloned(url=git_url, update=False)
            else:
                _local_path = git_url
        else:
            self._uri = path
            _local_path = path

        maker = await self.get_maker(_local_path)
        await maker.sync()
        self._metadata_timestamp = str(arrow.Arrow.now())

    async def get_uri(self) -> str:

        if self._uri is None:
            raise FrklException(
                "Can't retrieve uri for index.", reason="Index not initialized yet."
            )

        return self._uri

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
            tasks.add_tasklet(t)

        return tasks

    async def get_maker(self, uri: str) -> TingMaker:

        # TODO: revisit typing here
        if self._maker is not None:
            if uri != self._maker_path:
                raise Exception("Maker uri changed, this is not supported yet...")
            return self._maker  # type: ignore

        maker_name = f"bring.pkg_maker.{self.name}"
        self._maker_path = uri
        self._maker = self._tingistry_obj.create_singleting(  # type: ignore
            name=maker_name,
            ting_class="text_file_ting_maker",
            prototing="bring.types.dynamic_pkg",
            ting_name_strategy="basename_no_ext",
            ting_target_namespace=self._pkg_namespace,
            file_matchers=[{"type": "extension", "regex": ".*\\.br.pkg"}],
        )

        self._maker.add_base_paths(uri)  # type: ignore

        return self._maker  # type: ignore
