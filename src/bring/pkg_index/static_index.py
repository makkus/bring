# -*- coding: utf-8 -*-
import logging
from typing import Any, Dict, Mapping, Optional

import arrow
from bring.pkg_index.config import IndexConfig
from bring.pkg_index.index import BringIndexTing
from bring.pkg_index.pkg import PkgTing
from bring.pkg_index.utils import retrieve_index_file_content
from frkl.common.exceptions import FrklException
from frkl.tasks.task import SingleTaskAsync, Task
from frkl.tasks.task_desc import TaskDesc
from tings.ting import TingMeta


log = logging.getLogger("bring")


class BringIndexFile(object):
    def __init__(self, index_file: str):

        self._index_file: str = index_file

        self._pkg_data: Optional[Mapping[str, Mapping[str, Any]]] = None
        self._metadata: Optional[Mapping[str, Any]] = None

    async def get_metadata(self, update_index_file: bool = False) -> Mapping[str, Any]:

        if self._metadata is None:
            await self.get_pkg_data(update_index_file=update_index_file)
        return self._metadata  # type: ignore

    async def update(self):

        self._pkg_data = None
        self._metadata = None

        await self.get_pkg_data(update_index_file=True)

    async def get_pkg_data(
        self, update_index_file: bool = False
    ) -> Mapping[str, Mapping[str, Any]]:

        if self._pkg_data is not None:
            return self._pkg_data

        pkgs: Dict[str, Mapping[str, Any]] = {}

        data: Mapping[str, Any] = await retrieve_index_file_content(
            self._index_file, update=update_index_file
        )

        index_metadata: Dict[str, Any] = {}

        for pkg_name, pkg_data in data.items():

            if pkg_name.startswith("_bring_"):

                if pkg_name == "_bring_metadata_timestamp":
                    try:
                        pkg_data = arrow.get(pkg_data)
                        index_metadata[pkg_name] = pkg_data
                    except Exception as e:
                        log.debug(f"Can't parse date '{pkg_data}', ignoring: {e}")
                else:
                    index_metadata[pkg_name] = pkg_data

                continue

            pkgs[pkg_name] = pkg_data

        self._pkg_data = pkgs
        self._metadata = index_metadata
        return self._pkg_data

    async def create_ting(self, index: BringIndexTing, pkg_name: str) -> PkgTing:

        pkgs = await self.get_pkg_data()
        pkg_data = pkgs.get(pkg_name, None)

        if pkg_data is None:
            raise FrklException(
                msg=f"Can't create ting '{pkg_name}'.",
                reason="No package with that name available.",
            )

        ting: PkgTing = index.tingistry.get_ting(  # type: ignore
            f"{index.full_name}.pkgs.{pkg_name}"
        )
        if ting is None:
            ting = index.tingistry.create_ting(  # type: ignore
                "bring.types.static_pkg",
                f"{index.full_name}.pkgs.{pkg_name}",  # type: ignore
            )
            # ting.bring_index = index

        ting.set_input(**pkg_data)
        # ting._set_result(data)
        return ting

    async def create_tings(self, index: BringIndexTing) -> Mapping[str, PkgTing]:

        pkgs = await self.get_pkg_data()

        result: Dict[str, PkgTing] = {}
        for pkg_name in pkgs.keys():
            result[pkg_name] = await self.create_ting(index=index, pkg_name=pkg_name)

        return result


class BringStaticIndexTing(BringIndexTing):
    def __init__(self, name: str, meta: TingMeta):
        self._uri: Optional[str] = None
        self._index_file: Optional[BringIndexFile] = None
        self._pkgs: Optional[Mapping[str, PkgTing]] = None

        super().__init__(name=name, meta=meta)

    def _invalidate(self) -> None:

        self._pkgs = None
        self._index_file = None

    async def _get_metadata_timestamp(self) -> Optional[str]:

        index_file = await self.get_index_file()
        metadata = await index_file.get_metadata()
        ts = metadata.get("_bring_metadata_timestamp", None)
        if ts:
            ts = str(ts)
        return ts

    async def get_index_file(self, update: bool = False) -> BringIndexFile:
        if self._index_file is None or update:
            if self._uri is None:
                raise Exception(
                    "Can't load packages: index uri not set. This is a bug."
                )

            if self._index_file is None:
                self._index_file = BringIndexFile(index_file=self._uri)
            if update:
                await self._index_file.update()
        return self._index_file

    async def _get_pkgs(self) -> Mapping[str, PkgTing]:

        if self._pkgs is None:
            index_file = await self.get_index_file()
            self._pkgs = await index_file.create_tings(self)
        return self._pkgs

    async def _create_update_tasks(self) -> Optional[Task]:

        task_desc = TaskDesc(
            name=f"metadata update {self.name}",
            msg=f"updating metadata for index '{self.name}'",
        )

        async def update_index():
            self.invalidate()
            await self.get_index_file(update=True)

        task = SingleTaskAsync(update_index, task_desc=task_desc, parent_task=None)

        return task

    async def init(self, config: IndexConfig) -> None:

        self._uri = config.index_file
        self.invalidate()

    async def get_uri(self) -> str:

        if self._uri is None:
            raise FrklException(
                "Can't retrieve uri for index.", reason="Index not initialized yet."
            )
        return self._uri
