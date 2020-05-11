# -*- coding: utf-8 -*-
from typing import TYPE_CHECKING, Any, Dict, List, Mapping

from anyio import create_task_group
from bring.pkg_index.pkg import PkgTing
from tings.ting import Ting, TingMeta
from tings.ting.tings import SubscripTings


if TYPE_CHECKING:
    from bring.pkg_index import BringIndexTing
    from tings.tingistry import Tingistry


class Pkgs(SubscripTings):
    def __init__(
        self,
        name: str,
        meta: TingMeta,
        subscription_namespace: str,
        bring_index: "BringIndexTing",
    ):

        self._pkgs: Dict[str, PkgTing] = {}
        self._tingistry_obj: "Tingistry" = meta.tingistry
        self._bring_index = bring_index
        super().__init__(
            name=name,
            prototing="bring.types.dynamic_pkg",
            subscription_namespace=subscription_namespace,
            meta=meta,
        )

    def _ting_added(self, ting: Ting) -> None:

        if not isinstance(ting, PkgTing):
            raise TypeError(f"Invalid type '{type(ting)}', 'PkgTing' required.")
        ting.bring_index = self._bring_index
        self._pkgs[ting.name] = ting

    def _ting_removed(self, ting: Ting) -> None:

        self._pkgs.pop(ting.name)

    def _ting_updated(self, ting: Ting, current_values: Mapping[str, Any]):

        pass
        # print("TING UPDATED: {}".format(ting.name))

    def __iter__(self):

        return self._pkgs.values().__iter__()

    def __next__(self):

        return self._pkgs.values().__next__()  # type: ignore

    @property
    def pkgs(self) -> Mapping[str, PkgTing]:

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

    async def get_all_pkg_values(self, *value_names) -> Dict[str, Dict]:

        result = {}

        async def get_value(pkg, vn):
            vals = await pkg.get_values(*vn)
            result[pkg.name] = vals

        async with create_task_group() as tg:
            for pkg in self.pkgs.values():
                await tg.spawn(get_value, pkg, value_names)
                # break

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

    def get_pkg_names(self) -> List[str]:
        return list(self.pkgs.keys())
