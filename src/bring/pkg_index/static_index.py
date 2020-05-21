# -*- coding: utf-8 -*-
import logging
from typing import Dict, Mapping, Optional

import arrow
from anyio import Lock
from arrow import Arrow
from bring.pkg_index.index import BringIndexTing, retrieve_index_content
from bring.pkg_index.pkg import PkgTing
from bring.utils import BringTaskDesc
from frtls.exceptions import FrklException
from frtls.tasks import SingleTaskAsync, Task
from tings.ting import TingMeta


log = logging.getLogger("bring")


class BringStaticIndexTing(BringIndexTing):
    def __init__(self, name: str, meta: TingMeta):
        self._uri: Optional[str] = None
        self._pkgs: Optional[Dict[str, PkgTing]] = None
        # self._config: Optional[Mapping[str, Any]] = None

        self._pkg_lock: Optional[Lock] = None
        self._metadata_timestamp: Optional[Arrow] = None
        self._timestamp_queried = False
        super().__init__(name=name, meta=meta)

    # def add_urls(self, *urls: str):
    #
    #     self._urls.extend(urls)
    #     self.invalidate()

    async def _get_metadata_timestamp(self) -> Optional[str]:

        if not self._timestamp_queried:
            await self._get_pkgs()
        if self._metadata_timestamp:
            return str(self._metadata_timestamp)
        else:
            return None

    async def _load_pkgs(self, update: bool = False) -> Dict[str, PkgTing]:

        pkgs: Dict[str, PkgTing] = {}

        timestamps = []
        all_timestamps = True

        async def add_index(index_url: str, _update: bool = False):

            nonlocal all_timestamps
            nonlocal timestamps

            data = await retrieve_index_content(index_url, _update)

            if "_bring_metadata_timestamp" not in data.keys():
                all_timestamps = False

            for pkg_name, pkg_data in data.items():

                if pkg_name.startswith("_bring_"):
                    if pkg_name == "_bring_metadata_timestamp":
                        try:

                            pkg_data = arrow.get(pkg_data)
                            timestamps.append(pkg_data)
                        except Exception as e:
                            log.debug(f"Can't parse date '{pkg_data}', ignoring: {e}")

                    continue

                if pkg_name in pkgs.keys():
                    raise FrklException(
                        msg=f"Can't add pkg '{pkg_name}'.",
                        reason=f"Package with that name already exists in index '{self.name}'.",
                    )

                ting: PkgTing = self._tingistry_obj.get_ting(  # type: ignore
                    f"{self.full_name}.pkgs.{pkg_name}"
                )
                if ting is None:
                    ting = self._tingistry_obj.create_ting(  # type: ignore
                        "bring.types.static_pkg",
                        f"{self.full_name}.pkgs.{pkg_name}",  # type: ignore
                    )
                    ting.bring_index = self

                ting.set_input(**pkg_data)
                # ting._set_result(data)
                pkgs[pkg_name] = ting

        if self._uri is None:
            raise Exception("Can't load packages: index uri not set. This is a bug.")

        await add_index(self._uri, _update=update)

        if timestamps and all_timestamps:
            oldest_timestamp = timestamps[0]
            if len(timestamps) > 1:
                for timestamp in timestamps[1:]:
                    if timestamp < oldest_timestamp:
                        oldest_timestamp = timestamp

            self._metadata_timestamp = oldest_timestamp
        else:
            self._metadata_timestamp = None

        self._timestamp_queried = True

        return pkgs

    async def _get_pkgs(self) -> Mapping[str, PkgTing]:

        if self._pkgs is None:
            self._pkgs = await self._load_pkgs()

        return self._pkgs

    async def _create_update_tasks(self) -> Optional[Task]:

        task_desc = BringTaskDesc(
            name=f"metadata update {self.name}",
            msg=f"updating metadata for index '{self.name}'",
        )

        async def update_index():
            self.invalidate()
            await self._load_pkgs(update=True)

        task = SingleTaskAsync(update_index, task_desc=task_desc, parent_task=None)

        return task

    async def init(self, uri: str) -> None:

        self._uri = uri
        self.invalidate()
