# -*- coding: utf-8 -*-

"""Main module."""
from typing import Any, Dict, Iterator

from anyio import create_task_group
from frtls.files import ensure_folder
from tings.ting import Ting
from tings.ting.tings import SubscripTings
from tings.tingistry import Tingistries, Tingistry

from bring.defaults import BRINGISTRY_CONFIG, BRING_WORKSPACE_FOLDER
from bring.pkg import PkgTing


DEFAULT_TRANSFORM_PROFILES = {
    "executable": [
        {"type": "file_filter", "exclude": ["*~", "~*"]},
        {"type": "set_mode", "config": {"set_executable": True, "set_readable": True}},
    ]
}


class PkgTings(SubscripTings):
    def __init__(self, name: str, meta: Dict[str, Any] = None):

        self._pkgs = {}
        self._tingistry_obj: Tingistry = meta["tingistry"]["obj"]
        super().__init__(
            name=name,
            ting_type="bring.types.pkg",
            subscription_namespace="bring.pkgs",
            meta=meta,
        )

    def _ting_added(self, ting: Ting):

        self._pkgs[ting.name] = ting

    def _ting_removed(self, ting: Ting):

        self._pkgs.pop(ting.name)

    def _ting_updated(self, ting: Ting, current_values: Dict[str, Any]):

        pass
        # print("TING UPDATED: {}".format(ting.name))

    def get_pkgs(self) -> Dict[str, PkgTing]:

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

        pkg = self.childs.get(f"bring.pkgs.{pkg_name}", None)

        if pkg is None:
            raise Exception(f"No package with name '{pkg_name}' available.")

        return pkg

    async def get_pkg_values(self, pkg_name: str):

        pkg = self.get_pkg(pkg_name)
        pkg_vals = await pkg.get_values()
        return pkg_vals

    def get_pkg_names(self) -> Iterator[str]:

        return self.childs.keys()


class Bringistry(object):
    def __init__(self):

        ensure_folder(BRING_WORKSPACE_FOLDER)

        self._tingistry = Tingistries().add_tingistry(
            "bring",
            ting_types=BRINGISTRY_CONFIG["ting_types"],
            tings=BRINGISTRY_CONFIG["tings"],
            modules=BRINGISTRY_CONFIG["modules"],
            classes=BRINGISTRY_CONFIG["classes"],
        )

    @property
    def tingistry(self):

        return self._tingistry
