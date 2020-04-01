# -*- coding: utf-8 -*-
import copy
import logging
from abc import abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Mapping, Optional, Union

from bring.mogrify import Transmogrificator, Transmogritory
from bring.pkg_resolvers import PkgResolver
from bring.utils import BringTaskDesc, find_version, replace_var_aliases
from frtls.dicts import get_seeded_dict
from frtls.exceptions import FrklException
from frtls.tasks import TaskDesc
from frtls.types.typistry import TypistryPluginManager
from tings.exceptions import TingException
from tings.ting import SimpleTing
from tings.tingistry import Tingistry


if TYPE_CHECKING:
    from bring.bring import Bring
    from bring.context import BringContextTing  # noqa


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
        self._bring: Bring = self._tingistry_obj.get_ting("bring.mgmt")  # type: ignore
        # self._bring_pkgs = meta["tingistry"]["obj"].get_ting("bring.pkgs")
        super().__init__(name=name, meta=meta)
        self._context: Optional["BringContextTing"] = None

    @property
    def bring_context(self) -> "BringContextTing":

        if self._context is None:
            raise Exception(f"Context not (yet) set for PkgTing '{self.full_name}'.")
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

    @abstractmethod
    async def get_metadata(
        self, config: Optional[Mapping[str, Any]] = None, register_task: bool = False
    ) -> Mapping[str, Any]:
        """Return metadata associated with this package."""

        pass

    # def _get_translated_value(self, var_map, value):
    #
    #     if value not in var_map.keys():
    #         return value
    #
    #     return var_map[value]

    # async def get_valid_var_combinations(self):
    #
    #     vals = await self.get_values("metadata")
    #     metadata = vals["metadata"]
    #
    #     return self._get_valid_var_combinations(metadata=metadata)

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
        vals: Mapping[str, Any] = await self.get_values(  # type: ignore
            *val_keys, resolve=True
        )

        info = vals["info"]
        # source_details = vals["source"]

        result = {}

        result["info"] = info
        result["labels"] = vals["labels"]

        if include_metadata:

            metadata: Mapping[str, Any] = await self.get_metadata(
                config=retrieve_config, register_task=True
            )

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
        self,
        vars: Mapping[str, Any],
        metadata: Mapping[str, Any],
        extra_mogrifiers: Iterable[Union[str, Mapping[str, Any]]] = None,
        target: Union[str, Path, Mapping[str, Any]] = None,
        parent_task_desc: TaskDesc = None,
    ) -> Transmogrificator:

        _vars = replace_var_aliases(vars=vars, metadata=metadata)

        version = find_version(vars=_vars, metadata=metadata, var_aliases_replaced=True)

        if not version:
            raise FrklException(
                msg=f"Can't process pkg '{self.name}'.",
                reason=f"Can't find version match for vars: {_vars}",
            )
        mogrify_list: List[Union[str, Mapping[str, Any]]] = list(version["_mogrify"])

        if extra_mogrifiers:
            mogrify_list.extend(extra_mogrifiers)
        # import pp
        # pp(metadata['pkg_vars'].keys())

        if self._bring is None:
            raise Exception("'bring' attribute not set yet, this is a bug")
        transmogritory: Transmogritory = self._bring._transmogritory

        task_desc = BringTaskDesc(
            name=f"install pkg '{self.name}'", msg=f"installing pkg {self.name}"
        )

        tm = transmogritory.create_transmogrificator(
            mogrify_list,
            vars=_vars,
            args=metadata["pkg_vars"]["mogrify_vars"],
            name=self.name,
            task_desc=task_desc,
            target=target,
        )
        if parent_task_desc is not None:
            tm.task_desc.parent = parent_task_desc

        return tm

    async def create_version_folder(
        self,
        vars: Optional[Mapping[str, Any]] = None,
        target: Union[str, Path, Mapping[str, Any]] = None,
        delete_result: bool = True,
        parent_task_desc: TaskDesc = None,
    ) -> str:
        """Create a folder that contains the version specified via the provided 'vars'.

        If a target is provided, the result folder will be deleted unless 'delete_result' is set to False. If no target
        is provided, the path to a randomly named temp folder will be returned.
        """
        if vars is None:
            vars = {}
        vals: Mapping[str, Any] = await self.get_values(  # type: ignore
            "source", "metadata", resolve=True
        )
        metadata = vals["metadata"]

        extra_modifiers = None
        # if target is not None:
        #     extra_modifiers = [{"type": "merge_into", "target": target}]

        if not target:
            context_defaults = await self.bring_context.get_value("defaults")
            target = context_defaults.get("target", None)

        tm = self.create_transmogrificator(
            vars=vars,
            metadata=metadata,
            extra_mogrifiers=extra_modifiers,
            target=target,
            parent_task_desc=parent_task_desc,
        )

        # run_watcher = TerminalRunWatch(sort_task_names=False)
        vals = await tm.transmogrify()
        log.debug(f"finsished transmogrification: {vals}")

        if not tm._is_root_transmogrifier and tm.target_path is None:
            raise Exception("Root transmogrifier result is None, this is a bug")

        return tm.target_path  # type: ignore

    # def copy_file(self, source, target, force=False, method="move"):
    #
    #     os.makedirs(os.path.dirname(target), exist_ok=True)
    #     # if force and os.path.exists(target):
    #     #     os.unlink(target)
    #
    #     if method == "copy":
    #         shutil.copyfile(source, target, follow_symlinks=False)
    #         # TODO: file attributes
    #     elif method == "move":
    #         shutil.move(source, target)


class StaticPkgTing(PkgTing):
    def __init__(self, name, meta: Dict[str, Any]):

        super().__init__(name=name, meta=meta)

    def requires(self) -> Dict[str, str]:

        return {
            "source": "dict",
            "aliases": "dict?",
            "info": "dict?",
            "labels": "dict?",
            "tags": "list?",
            "metadata": "dict",
        }

    async def get_metadata(
        self, config: Optional[Mapping[str, Any]] = None, register_task: bool = False
    ) -> Mapping[str, Any]:

        vals: Mapping[str, Any] = await self.get_values(  # type: ignore
            "metadata", resolve=True
        )
        return vals["metadata"]

    async def retrieve(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        if not self._context:
            raise FrklException(
                msg=f"Can't retrieve values for PkgTing '{self.full_name}'.",
                reason="Context not set yet.",
            )

        result: Dict[str, Any] = {}

        for vn in value_names:
            if vn == "args":
                result[vn] = await self._calculate_args(requirements["metadata"])
            else:
                result[vn] = requirements[vn]

        return result


class DynamicPkgTing(PkgTing):
    def __init__(self, name, meta: Dict[str, Any]):

        super().__init__(name=name, meta=meta)

    async def get_metadata(
        self, config: Optional[Mapping[str, Any]] = None, register_task: bool = False
    ) -> Mapping[str, Any]:
        """Return metadata associated with this package."""

        vals: Mapping[str, Any] = await self.get_values(  # type: ignore
            "source", resolve=True
        )
        return await self._get_metadata(
            vals["source"], config=config, register_task=False
        )

    async def _get_metadata(
        self,
        source_dict,
        config: Optional[Mapping[str, Any]] = None,
        register_task: bool = False,
    ) -> Mapping[str, Any]:
        """Return metadata associated with this package, doesn't look-up 'source' dict itself."""

        resolver = self._get_resolver(source_dict)

        cached = await resolver.metadata_is_valid(
            source_dict, self.bring_context, override_config=config
        )
        if not cached and register_task:
            task_desc = BringTaskDesc(
                name=f"metadata retrieval {self.name}",
                msg=f"retrieving valid metadata for package '{self.name}'",
            )
            task_desc.task_started()

        metadata = await resolver.get_pkg_metadata(
            source_dict, self.bring_context, override_config=config
        )

        if not cached and register_task:
            task_desc.task_finished(msg="metadata retrieved")  # type: ignore

        return metadata

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

    def requires(self) -> Dict[str, str]:

        return {
            "source": "dict",
            "aliases": "dict?",
            "info": "dict?",
            "labels": "dict?",
            "tags": "list?",
            "ting_make_timestamp": "string?",
            "ting_make_metadata": "dict?",
        }

    async def retrieve(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        if not self._context:
            raise FrklException(
                msg=f"Can't retrieve values for PkgTing '{self.full_name}'.",
                reason="Context not set yet.",
            )

        result: Dict[str, Any] = {}
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
            result["tags"] = requirements.get("tags", [])
            parent_tags: Iterable[str] = seed_data.get("tags", None)
            if parent_tags:
                result["tags"].extend(parent_tags)

        return result
