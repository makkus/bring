# -*- coding: utf-8 -*-

"""Main module."""
import os
from collections import Mapping
from pathlib import Path
from typing import List, Union, Dict, Any

from bring.pkg_resolvers import PkgResolver
from frtls.exceptions import FrklException
from frtls.formats import auto_parse_string
from frtls.types.typistry import Typistry
from tings.exceptions import TingException
from tings.sources import FileWatchSource
from tings.ting import SimpleTing
from tings.ting.tings import Tings
from tings.tingistry import Tingistry


class BringPkgDetails(SimpleTing):
    def __init__(self, name, meta: Dict[str, Any]):

        super().__init__(name=name, meta=meta)

        self._bringistry: Bringistry = self._tingistry
        if not isinstance(self._bringistry, Bringistry):
            raise TingException(f"Invalid registry type: {type(self._tingistry)}")

    def provides(self) -> Dict[str, str]:

        return {"source": "dict", "versions": "list"}

    def requires(self) -> Dict[str, str]:

        return {"string_content": "string"}

    async def retrieve(self, *value_names: str, **requirements) -> Dict[str, Any]:

        parsed_dict = requirements.get("_parsed_dict", None)
        if parsed_dict is None:
            parsed_dict = auto_parse_string(requirements["string_content"])

        source = parsed_dict["source"]
        result = {}
        if "source" in value_names:
            result["source"] = source

        if "versions" in value_names:

            versions = await self._bringistry.get_pkg_versions(source)
            result["versions"] = versions

        return result


class Bringistry(Tingistry):
    def __init__(self, name: str, paths: List[Union[str, Path]] = None):

        preload_modules = [
            "bring",
            "bring.pkg_resolvers",
            "bring.pkg_resolvers.git_repo",
            "bring.pkg_resolvers.github_release",
        ]
        base_classes = [PkgResolver]

        self._typistry = Typistry(
            base_classes=base_classes, preload_modules=preload_modules
        )

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

        super().__init__(name=name, meta={"namespace": "bring"})

        self.register_ting_type("bring_pkg_metadata", "bring_pkg_details")
        self.register_ting_type(
            "bring_pkg", "ting_ting", ting_types=["file_details", "bring_pkg_metadata"]
        )
        self.register_ting_type("bring_pkgs", "tings", ting_type="bring_pkg")
        self.register_ting_type("bring_resolver", "ting_ting", ting_types=[""])

        if not paths:
            paths = [Path.cwd()]
        elif isinstance(paths, str):
            paths = [paths]

        self._paths = []
        for p in paths:
            if isinstance(p, str):
                self._paths.append(os.path.realpath(p))
            elif isinstance(p, Path):
                self._paths.append(p.resolve().as_posix())
            else:
                raise TypeError(f"Invalid input type for bringrepo path: {type(p)}")

        matchers = [{"type": "extension", "regex": ".bring$"}]
        self._bring_pkgs = self.create_ting(
            name="bring.bring_pkgs", type_name="bring_pkgs"
        )
        self._pkg_source = FileWatchSource(
            name="pkg_source",
            tings=self._bring_pkgs,
            base_paths=self._paths,
            matchers=matchers,
        )

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

    def sync(self):

        self._pkg_source.sync()

    @property
    def pkg_tings(self) -> Tings:
        return self._bring_pkgs

    async def watch(self):

        await self._pkg_source.watch()
