# -*- coding: utf-8 -*-

"""Main module."""
from collections import Mapping
from pathlib import Path
from typing import Dict, Any, Union, Iterator

from anyio import create_task_group

from bring.artefact_handlers import ArtefactHandler
from bring.defaults import BRINGISTRY_CONFIG, BRING_WORKSPACE_FOLDER
from bring.pkg import PkgTing
from bring.pkg_resolvers import PkgResolver
from bring.transform import TransformProfile
from frtls.exceptions import FrklException
from frtls.files import ensure_folder
from tings.ting import Ting
from tings.ting.tings import SubscripTings
from tings.tingistry import Tingistries, Tingistry

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
            base_classes=[PkgResolver, ArtefactHandler],
            preload_modules=BRINGISTRY_CONFIG["preload_modules"],
        )

    @property
    def tingistry(self):

        return self._tingistry

    def get_transform_profile(self, name) -> TransformProfile:

        profile = self._tingistry.get_ting(f"bring.transform.profiles.{name}")

        if profile is None:
            profile = self._tingistry.create_ting(
                ting_type=f"bring.transform.profiles.{name}",
                ting_name=f"bring.transform.profiles.{name}",
            )

        return profile

    # async def get_pkg_metadata(self, pkg_details):
    #
    #     if not isinstance(pkg_details, Mapping):
    #         raise TypeError(
    #             f"Invalid type '{type(pkg_details)}' for pkg_details (needs to be Mapping): {pkg_details}"
    #         )
    #
    #     pkg_type = pkg_details.get("type", None)
    #     if pkg_type is None:
    #         raise KeyError(f"No 'type' key in package details: {dict(pkg_details)}")
    #
    #     resolver: PkgResolver = self._resolvers.get(pkg_type, None)
    #
    #     if resolver is None:
    #         raise FrklException(
    #             msg="Can't resolve pkg.'.",
    #             reason=f"No resolver registered for type: {pkg_type}",
    #             solution=f"Register a resolver, or select one of the existing ones: {', '.join(self._resolvers.keys())}",
    #         )
    #
    #     metadata = await resolver.get_pkg_metadata(source_details=pkg_details)
    #     return metadata
    #
    # async def sync(self):
    #
    #     await self._bring_maker.sync()
    #
    # def get_resolver(self, resolver: Union[str, Dict]):
    #
    #     if isinstance(resolver, Mapping):
    #         resolver_type = resolver.get("type", None)
    #         if resolver_type is None:
    #             raise ValueError(
    #                 f"Can't get resolver, no 'type' key in source details mapping: {resolver}"
    #             )
    #
    #         resolver = resolver_type
    #
    #     if resolver == "auto":
    #         raise ValueError("Can't auto determine resolver.")
    #
    #     res_obj = self._resolver_sources.get(resolver, None)
    #     if res_obj is None:
    #         raise FrklException(
    #             msg=f"Can't get resolver '{resolver}'",
    #             reason="No such resolver name registered.",
    #             solution=f"Register resolver, or choose one of the available ones: {', '.join(self._resolver_sources.keys())}",
    #         )
    #
    #     return res_obj

    def get_artefact_handler(self, handler: Union[str, Dict], artefact=None):

        if isinstance(handler, Mapping):
            handler = handler.get("type", None)
            if handler is None:
                raise ValueError(
                    f"Can't get artefact handler, no 'type' key in metadata: {handler}"
                )

        if handler == "auto":

            if not artefact:
                raise ValueError(
                    f"Can't get artefact handler. Type is 'auto', but not artefact object provided."
                )

            if isinstance(artefact, Path):
                artefact = artefact.as_posix()

            if isinstance(artefact, str):

                # formats = shutil.get_archive_formats().keys()
                match = False
                for ext in [".zip", "tar.bz2", "tar.gz", "tar.xz", "tar"]:
                    if artefact.endswith(ext):
                        match = ext
                        break

                if match:
                    handler = "archive"

            if handler is None or handler == "auto":
                handler = "file"

        res_obj = self._artefact_handlers.get(handler, None)
        if res_obj is None:
            raise FrklException(
                msg=f"Can't get artefact handler '{handler}'",
                reason="No such handler registered.",
                solution=f"Register handler, or choose one of the available ones: {', '.join(self._artefact_handlers.keys())}",
            )

        return res_obj

    async def prepare_artefact(self, pkg_name: str, artefact_path: str):

        pkg_vals = await self.get_pkg_values(pkg_name=pkg_name)
        artefact_details = pkg_vals["artefact"]

        handler: ArtefactHandler = self._artefact_types.get(artefact_details["type"])

        folder = await handler.provide_artefact_folder(
            artefact_path=artefact_path, artefact_details=artefact_details
        )

        return folder
