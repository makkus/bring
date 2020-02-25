# -*- coding: utf-8 -*-
from typing import TYPE_CHECKING, Any, Dict, Iterator

from anyio import create_task_group
from bring.pkg import PkgTing
from tings.ting import Ting
from tings.ting.tings import SubscripTings


if TYPE_CHECKING:
    from bring.context import BringContextTing
    from tings.tingistry import Tingistry


class Pkgs(SubscripTings):
    def __init__(
        self,
        name: str,
        subscription_namespace: str,
        bring_context: "BringContextTing",
        meta: Dict[str, Any] = None,
    ):

        self._pkgs = {}
        self._tingistry_obj: "Tingistry" = meta["tingistry"]
        self._bring_context = bring_context
        super().__init__(
            name=name,
            prototing="bring.types.pkg",
            subscription_namespace=subscription_namespace,
            meta=meta,
        )

    def _ting_added(self, ting: Ting):

        ting.bring_context = self._bring_context
        self._pkgs[ting.name] = ting

    def _ting_removed(self, ting: Ting):

        self._pkgs.pop(ting.name)

    def _ting_updated(self, ting: Ting, current_values: Dict[str, Any]):

        pass
        # print("TING UPDATED: {}".format(ting.name))

    def __iter__(self):

        return self._pkgs.values().__iter__()

    def __next__(self):

        return self._pkgs.values().__next__()

    @property
    def pkgs(self) -> Dict[str, PkgTing]:

        return self._pkgs

    async def get_info(
        self, include_metadata: bool = False, update: bool = False
    ) -> Dict[str, Dict[str, Any]]:

        result = {}

        async def get_info(pkg_name, pkg, inc_md, upd):
            config = None
            if update:
                config = {"max_metadata_age": 0}
            info = await pkg.get_info(
                include_metadata=inc_md, retrieve_config=config, update=upd
            )
            result[pkg_name] = info

        async with create_task_group() as tg:
            for pkg_name, pkg in self.pkgs.items():
                await tg.spawn(get_info, pkg_name, pkg, include_metadata, update)

        return result

    async def get_all_pkg_values(self) -> Dict[str, Dict]:

        result = {}

        async def get_value(pkg):
            vals = await pkg.get_values()
            result[pkg.name] = vals

        async with create_task_group() as tg:
            for pkg in self._bring_pkgs._childs.values():
                await tg.spawn(get_value, pkg)

        return result

    def get_pkg(self, pkg_name: str) -> PkgTing:

        pkg = self.pkgs.get(pkg_name, None)
        if pkg is None:
            raise Exception(f"No package with name '{pkg_name}' available.")

        return pkg

    async def get_pkg_values(self, pkg_name: str):

        pkg = self.get_pkg(pkg_name)
        pkg_vals = await pkg.get_values()
        return pkg_vals

    def get_pkg_names(self) -> Iterator[str]:
        return self.pkgs.keys()
