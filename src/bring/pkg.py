# -*- coding: utf-8 -*-
import copy
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Union

from bring.mogrify import Transmogrificator, Transmogritory
from bring.pkg_resolvers import PkgResolver
from bring.utils import find_version
from frtls.dicts import get_seeded_dict
from frtls.exceptions import FrklException
from frtls.tasks import TaskDesc
from frtls.types.typistry import TypistryPluginManager
from tings.exceptions import TingException
from tings.ting import SimpleTing
from tings.tingistry import Tingistry


log = logging.getLogger("bring")

DEFAULT_ARG_DICT = {
    "os": {"doc": {"short_help": "The target os for this package."}, "type": "string"},
    "arch": {
        "doc": {"short_help": "The target architecture for this package."},
        "type": "string",
    },
    "version": {"doc": {"short_help": "The version of the package."}, "type": "string"},
}


class PkgTing(SimpleTing):
    def __init__(self, name, meta: Dict[str, Any]):

        self._tingistry_obj: Tingistry = meta["tingistry"]
        # self._bring_pkgs = meta["tingistry"]["obj"].get_ting("bring.pkgs")
        super().__init__(name=name, meta=meta)
        self._context: Optional["BringContextTing"] = None

    @property
    def bring_context(self):

        return self._context

    @bring_context.setter
    def bring_context(self, context):
        if self._context:
            raise Exception(f"Context already set for PkgTing '{self.full_name}'.")
        self._context = context

    def provides(self) -> Dict[str, str]:

        return {
            "source": "dict",
            "metadata": "dict",
            "aliases": "dict",
            "args": "args",
            "info": "dict",
            "labels": "dict",
            "tags": "list",
        }

    def requires(self) -> Dict[str, str]:

        return {
            "source": "dict",
            "aliases": "dict?",
            "info": "dict?",
            "labels": "dict?",
            "tags": "list?",
            "ting_make_timestamp": "string",
            "ting_make_metadata": "dict",
        }

    async def retrieve(self, *value_names: str, **requirements) -> Dict[str, Any]:

        if not self.bring_context:
            raise FrklException(
                msg=f"Can't retrieve values for PkgTing '{self.full_name}'.",
                reason="Context not set yet.",
            )

        result = {}
        source = requirements["source"]

        resolver = self._get_resolver(source_dict=source)

        seed_data = await resolver.get_seed_data(
            source, bring_context=self.bring_context
        )
        if seed_data is None:
            seed_data = {}

        if "source" in value_names:
            result["source"] = source

        metadata = None
        if (
            "metadata" in value_names
            or "args" in value_names
            or "aliases" in value_names
            or "metadata_valid" in value_names
        ):
            metadata = await self._get_metadata(source)
            result["metadata"] = metadata

        if "args" in value_names:
            result["args"] = await self._calculate_args(metadata=metadata)

        if "aliases" in value_names:
            result["aliases"] = await self._get_aliases(metadata)

        if "info" in value_names:
            info = requirements.get("info", {})
            result["info"] = get_seeded_dict(
                seed_data.get("info", None), info, merge_strategy="merge"
            )

        if "labels" in value_names:
            labels = requirements.get("labels", {})
            result["labels"] = get_seeded_dict(
                seed_data.get("labels", None), labels, merge_strategy="update"
            )

        if "tags" in value_names:
            result["tags"]: Iterable[str] = requirements.get("tags", [])
            parent_tags: Iterable[str] = seed_data.get("tags", None)
            if parent_tags:
                result["tags"].extend(parent_tags)

        return result

    async def _get_aliases(self, metadata):

        return metadata.get("aliases", {})

    async def get_aliases(self):

        metadata = await self.get_metadata()
        return self._get_aliases(metadata)

    async def _calculate_args(self, metadata):

        # print(metadata.keys())
        # print(metadata["pkg_args"])

        pkg_args = metadata["pkg_vars"]["args"]
        arg = self._tingistry_obj.arg_hive.create_record_arg(childs=pkg_args)

        return arg

    async def get_metadata(
        self, config: Optional[Mapping[str, Any]] = None
    ) -> Mapping[str, Any]:
        """Return metadata associated with this package."""

        vals = await self.get_values("source")
        return await self._get_metadata(vals["source"], config=config)

    async def _get_metadata(
        self, source_dict, config: Optional[Mapping[str, Any]] = None
    ) -> Mapping[str, Any]:
        """Return metadata associated with this package, doesn't look-up 'source' dict itself."""

        resolver = self._get_resolver(source_dict)

        return await resolver.get_pkg_metadata(
            source_dict, self.bring_context, self.full_name, override_config=config
        )

    def _get_resolver(self, source_dict: Dict) -> PkgResolver:

        pkg_type = source_dict.get("type", None)
        if pkg_type is None:
            raise KeyError(f"No 'type' key in package details: {dict(source_dict)}")

        pm: TypistryPluginManager = self._tingistry_obj.get_plugin_manager(
            "pkg_resolver"
        )

        resolver: PkgResolver = pm.get_plugin_for(pkg_type)
        if resolver is None:
            r_type = source_dict.get("type", source_dict)
            raise TingException(
                ting=self,
                msg=f"Can't retrieve metadata for pkg '{self.name}'.",
                reason=f"No resolver registered for: {r_type}",
            )

        return resolver

    def _get_translated_value(self, var_map, value):

        if value not in var_map.keys():
            return value

        return var_map[value]

    async def get_valid_var_combinations(self):

        vals = await self.get_values("metadata")
        metadata = vals["metadata"]

        return self._get_valid_var_combinations(metadata=metadata)

    async def _get_valid_var_combinations(
        self, metadata
    ) -> Iterable[Mapping[str, Any]]:
        """Return a list of valid var combinations that uniquely identify a version item.


        Aliases are not considered here, those need to be translated before lookup.
        """

        versions = metadata["versions"]

        result = []
        for version in versions:
            temp = copy.copy(version)
            temp.pop("_meta", None)
            temp.pop("_mogrify", None)

            result.append(temp)

        return result

    async def update_metadata(self) -> Mapping[str, Any]:

        return await self.get_metadata({"metadata_max_age": 0})

    async def get_info(
        self,
        include_metadata: bool = False,
        retrieve_config: Optional[Mapping[str, Any]] = None,
    ):

        val_keys = ["info", "source", "labels"]
        vals = await self.get_values(*val_keys)

        info = vals["info"]
        source_details = vals["source"]

        metadata: Dict[str, Any] = None
        if include_metadata:
            metadata = await self._get_metadata(
                source_dict=source_details, config=retrieve_config
            )

        result = {}

        result["info"] = info
        result["labels"] = vals["labels"]

        if include_metadata:

            timestamp = metadata["metadata_check"]

            pkg_vars = metadata["pkg_vars"]
            aliases = metadata["aliases"]

            var_combinations = await self._get_valid_var_combinations(metadata=metadata)

            metadata_result = {
                "pkg_args": pkg_vars["args"],
                "aliases": aliases,
                "timestamp": timestamp,
                "version_list": var_combinations,
            }
            result["metadata"] = metadata_result

        return result

    def create_transmogrificator(
        self, vars: Dict[str, Any], metadata: Mapping[str, Any]
    ) -> Transmogrificator:

        version = find_version(vars=vars, metadata=metadata)

        if not version:
            raise FrklException(
                msg=f"Can't process pkg '{self.name}'.",
                reason=f"Can't find version match for vars: {vars}",
            )
        mogrify_list = version["_mogrify"]

        # import pp
        # pp(metadata['pkg_vars'].keys())

        transmogritory: Transmogritory = self._tingistry_obj._transmogritory

        task_desc = TaskDesc(name=f"{self.name}", msg=f"installing pkg {self.name}")

        tm = transmogritory.create_transmogrificator(
            mogrify_list,
            vars=vars,
            args=metadata["pkg_vars"]["mogrify_vars"],
            name=self.name,
            task_desc=task_desc,
        )

        return tm

    async def create_version_folder(
        self,
        vars: Dict[str, Any],
        target: Union[str, Path] = None,
        delete_result: bool = True,
    ) -> str:
        """Create a folder that contains the version specified via the provided 'vars'.

        If a target is provided, the result folder will be deleted unless 'delete_result' is set to False. If no target
        is provided, the path to a randomly named temp folder will be returned.
        """

        vals = await self.get_values("source", "metadata")
        metadata = vals["metadata"]

        tm = self.create_transmogrificator(vars=vars, metadata=metadata)

        # run_watcher = TerminalRunWatch(sort_task_names=False)
        vals = await tm.transmogrify()
        log.debug(f"finsished transmogrification: {vals}")

        if target is not None:
            tm.set_target(target, delete_pipeline_folder=delete_result)
            return target
        else:
            return tm.result_path

    def copy_file(self, source, target, force=False, method="move"):

        os.makedirs(os.path.dirname(target), exist_ok=True)
        # if force and os.path.exists(target):
        #     os.unlink(target)

        if method == "copy":
            shutil.copyfile(source, target, follow_symlinks=False)
            # TODO: file attributes
        elif method == "move":
            shutil.move(source, target)
