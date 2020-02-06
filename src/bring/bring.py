# -*- coding: utf-8 -*-

"""Main module."""
from collections import Mapping
from typing import Dict, Any

from bring.pkg_resolvers import PkgResolver
from frtls.exceptions import FrklException
from frtls.types.typistry import Typistry
from tings.sources import SeedSource
from tings.ting import SimpleTing
from tings.ting.tings import Tings
from tings.tingistry import Tingistry


class BringPkgDetails(SimpleTing):
    def __init__(self, name, meta: Dict[str, Any]):

        super().__init__(name=name, meta=meta)

    def provides(self) -> Dict[str, str]:

        return {"source": "dict", "versions": "list"}

    def requires(self) -> Dict[str, str]:

        return {"dict": "dict"}

    async def retrieve(self, *value_names: str, **requirements) -> Dict[str, Any]:

        parsed_dict = requirements["dict"]
        source = parsed_dict["source"]
        result = {}
        if "source" in value_names:
            result["source"] = source

        if "versions" in value_names:

            versions = await self._tingistry.get_pkg_versions(source)
            result["versions"] = versions

        return result


BRINGISTRY_CONFIG = {
    "name": "bringistry",
    "tingistry_class": "bringistry",
    "ting_types": [
        {"name": "bring.bring_pkg_metadata", "ting_class": "bring_pkg_details"},
        {
            "name": "bring.bring_pkgs",
            "ting_class": "tings",
            "ting_init": {
                "ting_type": "bring.bring_pkg_metadata",
                "child_name_strategy": "basename_no_ext",
            },
        },
        {
            "name": "bring.bring_input",
            "ting_class": "ting_ting",
            "ting_init": {"ting_types": ["text_file", "dict"]},
        },
        {
            "name": "bring.bring_file_watcher",
            "ting_class": "file_watch_source",
            "ting_init": {"matchers": [{"type": "extension", "regex": ".bring$"}]},
        },
        {
            "name": "bring.bring_file_source",
            "ting_class": "ting_watch_source",
            "ting_init": {
                "source_ting_type": "bring.bring_file_watcher",
                "seed_ting_type": "bring.bring_input",
            },
        },
        {"name": "bring.bring_dict_source", "ting_class": "dict_source"},
    ],
    "preload_modules": [
        "bring",
        "bring.pkg_resolvers",
        "bring.pkg_resolvers.git_repo",
        "bring.pkg_resolvers.github_release",
    ],
    "tingistry_init": {"paths": []},
}


class Bringistry(Tingistry):
    def __init__(self, name: str, meta: Dict[str, Any] = None):

        super().__init__(
            name,
            *BRINGISTRY_CONFIG["ting_types"],
            preload_modules=BRINGISTRY_CONFIG["preload_modules"],
            meta=meta,
        )

        base_classes = [PkgResolver]
        self._typistry = Typistry(base_classes=base_classes)

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

        self._bring_pkgs: Tings = self.create_ting(
            name="bring.bring_pkgs", type_name="bring.bring_pkgs"
        )
        self._pkg_source = None

    def set_source(self, source_type: str, **source_init):

        self._pkg_source = self.create_ting(
            name="bring.pkg_source", type_name=source_type
        )
        self._pkg_source.set_tings(self._bring_pkgs)

    @property
    def source(self) -> SeedSource:

        return self._pkg_source

    async def get_pkg_versions(self, pkg_details):

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

        versions = await resolver.get_versions(source_details=pkg_details)
        return versions

    async def sync(self):

        await self._pkg_source.sync()

    async def get_pkgs(self) -> Tings:

        result = {}
        for pkg in self._bring_pkgs._childs.values():
            vals = await pkg.get_values()
            result[pkg.name] = vals

        return result

    async def watch(self):

        await self._pkg_source.watch()
