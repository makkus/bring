# -*- coding: utf-8 -*-
import copy
import logging
from abc import abstractmethod
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Union,
)

from bring.mogrify import Transmogrificator, Transmogritory
from bring.pkg_types import PkgType
from bring.utils import BringTaskDesc, find_version, replace_var_aliases
from deepdiff import DeepHash
from frtls.args.arg import RecordArg
from frtls.dicts import get_seeded_dict
from frtls.exceptions import FrklException
from frtls.tasks import TaskDesc
from frtls.types.plugins import TypistryPluginManager
from tings.exceptions import TingException
from tings.ting import SimpleTing, TingMeta
from tings.tingistry import Tingistry


if TYPE_CHECKING:
    from bring.pkg_index.index import BringIndexTing

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
    def __init__(self, name, meta: TingMeta):

        self._tingistry_obj: Tingistry = meta.tingistry
        self._transmogritory: Transmogritory = self._tingistry_obj.get_ting(  # type: ignore
            "bring.transmogritory", raise_exception=True
        )

        self._pkg_args: Optional[RecordArg] = None

        super().__init__(name=name, meta=meta)
        self._index: Optional["BringIndexTing"] = None

    @property
    def bring_index(self) -> "BringIndexTing":

        if self._index is None:
            raise Exception(f"Index not (yet) set for PkgTing '{self.full_name}'.")
        return self._index

    @bring_index.setter
    def bring_index(self, index):
        if self._index:
            raise Exception(f"Index already set for PkgTing '{self.full_name}'.")
        self._index = index

    @property
    def pkg_id(self) -> str:

        return f"{self.bring_index.id}.{self.name}"

    def provides(self) -> Dict[str, str]:

        return {
            "source": "dict",
            "metadata": "dict",
            "aliases": "dict",
            "args": "args",
            "info": "dict",
            "labels": "dict",
            "tags": "list",
            "index_name": "string",
        }

    async def _get_aliases(self, metadata):

        return metadata.get("aliases", {})

    async def get_aliases(self):

        metadata = await self.get_metadata()
        return await self._get_aliases(metadata)

    async def get_pkg_args(self) -> RecordArg:

        if self._pkg_args is None:

            metadata = await self.get_value("metadata")
            self._pkg_args = await self._calculate_args(metadata)
        return self._pkg_args

    async def _calculate_args(self, metadata) -> RecordArg:

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

    async def get_versions(self) -> Iterable[Mapping[str, Any]]:

        md = await self.get_value("metadata")
        return md["versions"]

    async def get_info(
        self,
        include_metadata: bool = False,
        retrieve_config: Optional[Mapping[str, Any]] = None,
    ):

        val_keys = ["info", "source", "labels", "tags"]
        vals: Mapping[str, Any] = await self.get_values(  # type: ignore
            *val_keys, resolve=True
        )

        info = vals["info"]
        # source_details = vals["source"]

        result = {}

        result["info"] = info
        result["labels"] = vals["labels"]
        result["tags"] = vals["tags"]

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

    async def find_version_data(
        self,
        vars: Optional[Mapping[str, Any]] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Optional[Mapping[str, Any]]:
        """Find a matching version item for the provided vars dictionary.

        Returns:
            A tuple consisting of the version that was found (or None), and the 'exploded' vars that were used
        """

        if vars is None:
            vars = {}
        if metadata is None:
            metadata = {}

        version = find_version(vars=vars, metadata=metadata, var_aliases_replaced=True)
        return version

    async def create_transmogrificator(
        self,
        vars: Optional[Mapping[str, Any]] = None,
        extra_mogrifiers: Iterable[Union[str, Mapping[str, Any]]] = None,
        parent_task_desc: TaskDesc = None,
    ) -> Transmogrificator:

        vals: Mapping[str, Any] = await self.get_values(  # type: ignore
            "metadata", resolve=True
        )
        metadata = vals["metadata"]

        if vars is None:
            vars = {}

        _vars = await self.calculate_full_vars(_pkg_metadata=metadata, **vars)

        version = await self.find_version_data(vars=_vars, metadata=metadata)

        if not version:
            raise FrklException(
                msg=f"Can't process pkg '{self.name}'.",
                reason=f"Can't find version match for vars: {vars}",
            )
        mogrify_list: List[Union[str, Mapping[str, Any]]] = list(version["_mogrify"])
        if extra_mogrifiers:
            mogrify_list.extend(extra_mogrifiers)

        task_desc = BringTaskDesc(
            name=f"install pkg '{self.name}'", msg=f"installing pkg {self.name}"
        )

        mogrify_vars = metadata["pkg_vars"]["mogrify_vars"]

        tm = self._transmogritory.create_transmogrificator(
            mogrify_list,
            vars=vars,
            args=mogrify_vars,
            name=self.name,
            task_desc=task_desc,
            # target=target,
        )
        if parent_task_desc is not None:
            tm.task_desc.parent = parent_task_desc

        return tm

    async def create_id_dict(
        self, _include_hash: bool = True, **vars: Any
    ) -> Dict[str, Any]:

        full_vars = await self.calculate_full_vars(**vars)
        result: Dict[str, Any] = {}
        result["vars"] = full_vars
        result["pkg_name"] = self.name
        result["pkg_index"] = self.bring_index.id

        if _include_hash:
            hashes = DeepHash(result)
            h = hashes[result]
            result["hash"] = h

        return result

    async def create_version_hash(self, **vars: Any) -> str:

        full_vars = await self.calculate_full_vars(**vars)
        id_dict: Dict[str, Any] = {}
        id_dict["vars"] = full_vars
        id_dict["pkg_name"] = self.name
        id_dict["pkg_index"] = self.bring_index.id

        hashes = DeepHash(id_dict)
        return hashes[id_dict]

    async def get_defaults(self) -> Mapping[str, Any]:

        args: RecordArg = await self.get_value("args")
        return args.default

    async def merge_with_defaults(self, **vars: Any) -> MutableMapping[str, Any]:

        vals: Mapping[str, Any] = await self.get_values(  # type: ignore
            "metadata", "args", resolve=True
        )
        # _pkg_metadata: Mapping[str, Any] = vals["metadata"]
        args: RecordArg = vals["args"]

        pkg_defaults = args.default

        _vars = get_seeded_dict(pkg_defaults, vars, merge_strategy="update")

        filtered: Dict[str, Any] = {}
        for k, v in _vars.items():
            if k in args.arg_names:
                filtered[k] = v

        return filtered

    async def calculate_full_vars(self, **vars: Any) -> MutableMapping[str, Any]:

        filtered = await self.merge_with_defaults(**vars)

        vals: Mapping[str, Any] = await self.get_values(  # type: ignore
            "metadata", "args", resolve=True
        )
        _pkg_metadata: Mapping[str, Any] = vals["metadata"]
        args: RecordArg = vals["args"]

        _vars_replaced = replace_var_aliases(vars=filtered, metadata=_pkg_metadata)

        validated = args.validate(_vars_replaced, raise_exception=True)
        return validated

    # async def explain_full_vars(self, **vars: Any) -> Mapping[str, Mapping[str, Any]]:
    #
    #     args: RecordArg = await self.get_value("args")  # type: ignore
    #
    #     pkg_defaults = args.get_defaults()
    #
    #     index_vars: Dict[
    #         str, Any
    #     ] = await self.bring_index.get_default_vars()  # type: ignore
    #
    #     result = {}
    #
    #     for k, v in vars.items():
    #         if k not in args.arg_names:
    #             continue
    #
    #         result[k] = {"value": v, "source": "user"}
    #
    #     for k, v in index_vars.items():
    #
    #         if k in result.keys() or k not in args.arg_names:
    #             continue
    #         result[k] = {"value": v, "source": "index"}
    #
    #     for k, v in pkg_defaults.items():
    #         if k in result.keys():
    #             continue
    #         result[k] = {"value": v, "source": "pkg"}
    #
    #     return result

    # def create_processor(self, processor_type: str, target: Union[BringTarget, str]) -> PkgProcessor:
    #
    #     pm = self._tingistry_obj.typistry.get_plugin_manager(PkgProcessor)
    #
    #     pkg_proc_cls: Type = pm.get_plugin(processor_type, raise_exception=True)
    #
    #     pkg_proc: PkgProcessor = pkg_proc_cls(pkg=self, bring_target=target)
    #     return pkg_proc
    #
    # async def process(self, processor_type: str, **vars) -> Mapping[str, Any]:
    #
    #     pkg_proc = self.create_processor(processor_type=processor_type, **vars)
    #     result = await pkg_proc.process(**vars)
    #     return result

    # async def create_version_folder_transmogrificator(
    #     self,
    #     vars: Optional[Mapping[str, Any]] = None,
    #     # target: Union[str, Path, Mapping[str, Any]] = None,
    #     extra_mogrifiers: Optional[Iterable[Union[str, Mapping[str, Any]]]] = None,
    #     parent_task_desc: TaskDesc = None,
    # ) -> Transmogrificator:
    #
    #     tm = await self.create_transmogrificator(
    #         vars=vars,
    #         extra_mogrifiers=extra_mogrifiers,
    #         # target=target,
    #         parent_task_desc=parent_task_desc,
    #     )
    #
    #     return tm

    # async def create_version_folder(
    #     self,
    #     vars: Optional[Mapping[str, Any]] = None,
    #     target: Union[str, Path, Mapping[str, Any]] = None,
    #     extra_mogrifiers: Optional[Iterable[Union[str, Mapping[str, Any]]]] = None,
    #     parent_task_desc: TaskDesc = None,
    # ) -> Mapping[str, Any]:
    #     """Create a folder that contains the version specified via the provided 'vars'.
    #
    #     If no target is provided, the path to a randomly named temp folder will be returned.
    #     """
    #
    #     if target is None:
    #         path = None
    #         merge_strategy = None
    #     elif isinstance(target, str):
    #         path = target
    #         merge_strategy = {"type": "default"}
    #     elif isinstance(target, collections.Mapping):
    #         merge_strategy = dict(target)
    #         path = merge_strategy.pop("path")
    #
    #     ip = self.create_processor("install", target="local_folder")
    #     ip.set_input(path=path, merge_strategy=merge_strategy)
    #
    #     result = await ip.process()
    #
    #     return "RESULT"


class StaticPkgTing(PkgTing):
    def __init__(self, name, meta: TingMeta):

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

        if not self._index:
            raise FrklException(
                msg=f"Can't retrieve values for PkgTing '{self.full_name}'.",
                reason="Index not set yet.",
            )

        result: Dict[str, Any] = {}

        for vn in value_names:
            if vn == "index_name":
                result[vn] = self.bring_index.name
                continue
            if vn == "args":
                result[vn] = await self._calculate_args(requirements["metadata"])
            else:
                result[vn] = requirements[vn]

        return result


class DynamicPkgTing(PkgTing):
    def __init__(self, name, meta: TingMeta):

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
            source_dict, self.bring_index, override_config=config
        )
        if not cached and register_task:
            task_desc = BringTaskDesc(
                name=f"metadata retrieval {self.name}",
                msg=f"retrieving valid metadata for package '{self.name}'",
            )
            task_desc.task_started()

        metadata = await resolver.get_pkg_metadata(
            source_dict, self.bring_index, override_config=config
        )

        if not cached and register_task:
            task_desc.task_finished(msg="metadata retrieved")  # type: ignore

        return metadata

    def _get_resolver(self, source_dict: Dict) -> PkgType:

        pkg_type = source_dict.get("type", None)
        if pkg_type is None:
            raise KeyError(f"No 'type' key in package details: {dict(source_dict)}")

        pm: TypistryPluginManager = self._tingistry_obj.get_plugin_manager("pkg_type")

        resolver: PkgType = pm.get_plugin_for(pkg_type)
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

        if not self._index:
            raise FrklException(
                msg=f"Can't retrieve values for PkgTing '{self.full_name}'.",
                reason="Index not set yet.",
            )

        result: Dict[str, Any] = {}
        source = requirements["source"]

        resolver = self._get_resolver(source_dict=source)

        seed_data = await resolver.get_seed_data(source, bring_index=self.bring_index)
        if seed_data is None:
            seed_data = {}

        if "index_name" in value_names:
            result["index_name"] = self.bring_index.name

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
            tags = requirements.get("tags", [])
            result["tags"] = tags

        if "tags" in value_names:
            result["tags"] = requirements.get("tags", [])
            parent_tags: Iterable[str] = seed_data.get("tags", None)
            if parent_tags:
                result["tags"].extend(parent_tags)

        return result
