# -*- coding: utf-8 -*-
import json
import os
import zlib
from typing import Any, Dict, List, Mapping, Optional

from anyio import Lock, aopen
from bring.context import BringContextTing
from bring.defaults import BRING_CONTEXT_FILES_CACHE
from bring.pkg import PkgTing
from frtls.downloads import download_cached_binary_file_async
from frtls.exceptions import FrklException
from frtls.tasks import Task


class BringStaticContextTing(BringContextTing):
    def __init__(
        self,
        name: str,
        parent_key: str = "parent",
        meta: Optional[Mapping[str, Any]] = None,
    ):
        self._urls: List[str] = []
        self._pkgs: Optional[Dict[str, PkgTing]] = None
        self._config: Optional[Mapping[str, Any]] = None

        self._pkg_lock: Optional[Lock] = None
        super().__init__(name=name, parent_key=parent_key, meta=meta)

    def add_urls(self, *urls: str):

        self._urls.extend(urls)
        self.invalidate()

    async def _load_pkgs(self) -> Dict[str, PkgTing]:

        pkgs: Dict[str, PkgTing] = {}

        async def add_index(index_url: str):

            update = False

            if os.path.exists(index_url):
                async with await aopen(index_url, "rb") as f:
                    content = await f.read()
            else:

                content = await download_cached_binary_file_async(
                    url=index_url,
                    update=update,
                    cache_base=BRING_CONTEXT_FILES_CACHE,
                    return_content=True,
                )

            json_string = zlib.decompress(content, 16 + zlib.MAX_WBITS)  # type: ignore

            data = json.loads(json_string)

            for pkg_name, pkg_data in data.items():

                if pkg_name in pkgs.keys():
                    raise FrklException(
                        msg=f"Can't add pkg '{pkg_name}'.",
                        reason=f"Package with that name already exists in context '{self.name}'.",
                    )

                ting: PkgTing = self._tingistry_obj.get_ting(  # type: ignore
                    f"{self.full_name}.pkgs.{pkg_name}"
                )
                if ting is None:
                    ting = self._tingistry_obj.create_ting(  # type: ignore
                        "bring.types.static_pkg",
                        f"{self.full_name}.pkgs.{pkg_name}",  # type: ignore
                    )
                    ting.bring_context = self

                ting.input.set_values(**pkg_data)
                # ting._set_result(data)
                pkgs[pkg_name] = ting

        # async with create_task_group() as tg:
        for url in self._urls:
            # await tg.spawn(add_index, url)
            await add_index(url)

        return pkgs

    async def _get_pkgs(self) -> Mapping[str, PkgTing]:

        if self._pkgs is None:
            self._pkgs = await self._load_pkgs()

        return self._pkgs

    async def _create_update_tasks(self) -> Optional[Task]:

        return None

    async def init(self, config: Mapping[str, Any]) -> None:

        self._config = config
        self.add_urls(*config["indexes"])
