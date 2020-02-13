# -*- coding: utf-8 -*-

"""Main module."""
from collections import Mapping
from pathlib import Path
from typing import Dict, Any, Sequence, Union

from bring.artefact_handlers import ArtefactHandler
from bring.defaults import BRINGISTRY_CONFIG, BRING_WORKSPACE_FOLDER
from bring.file_sets import FileSetFilter
from bring.pkg import BringPkgDetails
from bring.pkg_resolvers import PkgResolver
from bring.system_info import get_current_system_info
from bring.transform import TransformProfile
from frtls.exceptions import FrklException
from frtls.files import ensure_folder
from frtls.types.typistry import Typistry
from tings.sources import SeedSource
from tings.tingistry import Tingistry

DEFAULT_TRANSFORM_PROFILES = {
    "executable": [
        {"type": "file_filter", "exclude": ["*~", "~*"]},
        {"type": "set_mode", "config": {"set_executable": True, "set_readable": True}},
    ]
}


class Bringistry(Tingistry):
    def __init__(self, name: str, meta: Dict[str, Any] = None):

        ensure_folder(BRING_WORKSPACE_FOLDER)

        super().__init__(
            name,
            *BRINGISTRY_CONFIG["ting_types"],
            preload_modules=BRINGISTRY_CONFIG["preload_modules"],
            meta=meta,
        )

        base_classes = [PkgResolver, ArtefactHandler, FileSetFilter]
        self._typistry = Typistry(base_classes=base_classes)

        self._default_vars = get_current_system_info()

        self._resolvers = {}
        self._resolver_sources = {}
        for k, v in self._typistry.get_subclass_map(PkgResolver).items():

            resolver = v()
            r_name = resolver.get_resolver_name()
            if r_name in self._resolvers.keys():
                raise FrklException(
                    msg=f"Can't register resolver of class '{v}'",
                    reason=f"Duplicate resolver name: {r_name}",
                )
            self._resolvers[r_name] = resolver
            for r_type in resolver.get_supported_source_types():
                self._resolver_sources[r_type] = resolver

        self._artefact_handlers = {}
        self._artefact_types = {}

        for k, v in self._typistry.get_subclass_map(ArtefactHandler).items():

            handler = v()
            h_name = handler.get_handler_name()

            if h_name.endswith("-handler"):
                h_name = h_name[0:-8]

            if h_name in self._artefact_handlers.keys():
                raise FrklException(
                    msg=f"Can't register artefact handler of class '{v}'",
                    reason=f"Duplicate handler name: {h_name}",
                )
            self._artefact_handlers[h_name] = handler
            for h_type in handler.get_supported_artefact_types():
                self._artefact_types[h_type] = handler

        self._file_set_filters = {}

        for k, v in self._typistry.get_subclass_map(FileSetFilter).items():

            if k.endswith("_file_set_filter"):
                k = k[0:-16]
            self._file_set_filters[k] = v

        # self._bring_pkgs: SeedTings = self.create_ting(
        #     name="bring.bring_pkgs", type_name="bring.bring_pkgs"
        # )
        # self._pkg_source = None

    def set_source(self, source_type: str, **source_init):

        self._pkg_source = self.create_ting(
            name="bring.pkg_source", type_name=source_type
        )
        self._pkg_source.set_tings(self._bring_pkgs)

    @property
    def source(self) -> SeedSource:

        return self._pkg_source

    def get_transform_profile(self, name) -> TransformProfile:

        profile = self.get_ting(f"bring.transform.profiles.{name}")

        if profile is None:
            profile = self.create_ting(
                f"bring.transform.profiles.{name}",
                type_name=f"bring.transform.profiles.{name}",
            )

        return profile

    async def get_pkg_metadata(self, pkg_details):

        if not isinstance(pkg_details, Mapping):
            raise TypeError(
                f"Invalid type '{type(pkg_details)}' for pkg_details (needs to be Mapping): {pkg_details}"
            )

        pkg_type = pkg_details.get("type", None)
        if pkg_type is None:
            raise KeyError(f"No 'type' key in package details: {dict(pkg_details)}")

        resolver: PkgResolver = self._resolvers.get(pkg_type, None)

        if resolver is None:
            raise FrklException(
                msg="Can't resolve pkg.'.",
                reason=f"No resolver registered for type: {pkg_type}",
                solution=f"Register a resolver, or select one of the existing ones: {', '.join(self._resolvers.keys())}",
            )

        metadata = await resolver.get_pkg_metadata(source_details=pkg_details)
        return metadata

    # async def get_pkg_filters(self, filters_conf: Dict) -> Dict[str, FileSetFilter]:
    #
    #     if not filters_conf:
    #         filters_conf = {}
    #
    #     result = {}
    #     for fileset_name, conf in filters_conf.items():
    #
    #         if isinstance(conf, str):
    #             conf = [conf]
    #
    #         if not isinstance(conf, Sequence):
    #             raise TypeError(
    #                 f"Invalid configuration type '{type(conf)}' for filter config (must be str or List): {conf}"
    #             )
    #
    #         # filter_name = "default"
    #         filter_set = DefaultFileSetFilter(patterns=conf)
    #         result[fileset_name] = filter_set
    #
    #     result["all"] = DEFAULT_FILTER
    #     result["ALL"] = DEFAULT_ALL_FILTER
    #
    #     return result

    async def sync(self):

        await self._pkg_source.sync()

    def get_pkg_names(self) -> Sequence[str]:

        return self._bring_pkgs.childs.keys()

    def get_pkgs(self):

        return self._bring_pkgs.childs

    async def get_pkg_values_list(self) -> Dict[str, Dict]:

        result = {}
        for pkg in self._bring_pkgs._childs.values():
            vals = await pkg.get_values()
            result[pkg.name] = vals

        return result

    def get_pkg(self, pkg_name: str) -> BringPkgDetails:

        pkg = self._bring_pkgs.childs.get(pkg_name, None)

        if pkg is None:
            raise Exception(f"No package with name '{pkg_name}' available.")

        return pkg

    async def get_pkg_values(self, pkg_name: str):

        pkg = self.get_pkg(pkg_name)
        pkg_vals = await pkg.get_values()
        return pkg_vals

    def get_resolver(self, resolver: Union[str, Dict]):

        if isinstance(resolver, Mapping):
            resolver_type = resolver.get("type", None)
            if resolver_type is None:
                raise ValueError(
                    f"Can't get resolver, no 'type' key in source details mapping: {resolver}"
                )

            resolver = resolver_type

        if resolver == "auto":
            raise ValueError("Can't auto determine resolver.")

        res_obj = self._resolver_sources.get(resolver, None)
        if res_obj is None:
            raise FrklException(
                msg=f"Can't get resolver '{resolver}'",
                reason="No such resolver name registered.",
                solution=f"Register resolver, or choose one of the available ones: {', '.join(self._resolver_sources.keys())}",
            )

        return res_obj

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

    @property
    def default_vars(self):

        return self._default_vars

    async def prepare_artefact(self, pkg_name: str, artefact_path: str):

        pkg_vals = await self.get_pkg_values(pkg_name=pkg_name)
        artefact_details = pkg_vals["artefact"]

        handler: ArtefactHandler = self._artefact_types.get(artefact_details["type"])

        folder = await handler.provide_artefact_folder(
            artefact_path=artefact_path, artefact_details=artefact_details
        )

        return folder

    async def watch(self):

        await self._pkg_source.watch()
