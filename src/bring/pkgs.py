# -*- coding: utf-8 -*-
from typing import Any, Dict, Iterator

from anyio import create_task_group
from bring.pkg import PkgTing
from tings.ting import Ting
from tings.ting.tings import SubscripTings
from tings.tingistry import Tingistry


class Pkgs(SubscripTings):
    def __init__(
        self, name: str, subscription_namespace: str, meta: Dict[str, Any] = None
    ):

        self._pkgs = {}
        self._tingistry_obj: Tingistry = meta["tingistry"]["obj"]
        super().__init__(
            name=name,
            ting_type="bring.types.pkg",
            subscription_namespace=subscription_namespace,
            meta=meta,
        )

    def _ting_added(self, ting: Ting):

        self._pkgs[ting.name] = ting

    def _ting_removed(self, ting: Ting):

        self._pkgs.pop(ting.name)

    def _ting_updated(self, ting: Ting, current_values: Dict[str, Any]):

        pass
        # print("TING UPDATED: {}".format(ting.name))

    @property
    def pkgs(self) -> Dict[str, PkgTing]:

        return self._pkgs

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

        pkg = self.childs.get(f"{self._subscription_namespace}.{pkg_name}", None)
        if pkg is None:
            raise Exception(f"No package with name '{pkg_name}' available.")

        return pkg

    async def get_pkg_values(self, pkg_name: str):

        pkg = self.get_pkg(pkg_name)
        pkg_vals = await pkg.get_values()
        return pkg_vals

    def get_pkg_names(self) -> Iterator[str]:

        return self.childs.keys()
