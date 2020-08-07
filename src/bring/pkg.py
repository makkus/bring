# -*- coding: utf-8 -*-
import copy
import logging
from abc import abstractmethod
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Union

from bring.mogrify import Transmogrificator, Transmogritory
from bring.pkg_types import (
    PkgMetadata,
    PkgType,
    PkgVersion,
    get_pkg_type_plugin_factory,
)
from bring.utils import find_version, replace_var_aliases
from frkl.args.arg import RecordArg
from frkl.common.dicts import get_seeded_dict
from frkl.common.exceptions import FrklException
from frkl.common.formats.serialize import to_value_string
from frkl.common.strings import generate_valid_identifier
from frkl.tasks.task_desc import TaskDesc
from frkl.types.plugins import PluginFactory
from tings.exceptions import TingException
from tings.ting import SimpleTing, TingMeta
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


class PKG_INPUT_TYPE(Enum):

    pkg_name = 0
    pkg_desc = 1
    pkg_desc_file = 2


class PkgTing(SimpleTing):
    def __init__(self, name, meta: TingMeta):

        self._tingistry_obj: Tingistry = meta.tingistry
        self._transmogritory: Transmogritory = self._tingistry_obj.get_ting(  # type: ignore
            "bring.transmogritory", raise_exception=True
        )

        self._pkg_args: Optional[RecordArg] = None

        super().__init__(name=name, meta=meta)
        # self._index: Optional["BringIndexTing"] = None

    # @property
    # def bring_index(self) -> "BringIndexTing":
    #
    #     if self._index is None:
    #         raise Exception(f"Index not (yet) set for PkgTing '{self.full_name}'.")
    #     return self._index
    #
    # @bring_index.setter
    # def bring_index(self, index):
    #     if self._index:
    #         raise Exception(f"Index already set for PkgTing '{self.full_name}'.")
    #     self._index = index

    # @property
    # def pkg_id(self) -> str:
    #
    #     return f"{self.bring_index.id}.{self.name}"

    def provides(self) -> Dict[str, str]:

        return {
            "source": "dict",
            "metadata": "dict",
            "aliases": "dict",
            "args": "args",
            "info": "dict",
            "labels": "dict",
            "tags": "list",
            # "index_name": "string",
        }

    # async def _get_aliases(self, metadata: PkgMetadata):
    #
    #     return metadata.get("aliases", {})

    async def get_aliases(self):

        metadata = await self.get_value("metadata")  # type: ignore
        return metadata.aliases

    async def get_pkg_args(self) -> RecordArg:

        if self._pkg_args is None:

            metadata = await self.get_value("metadata")
            self._pkg_args = await self._calculate_args(metadata)
        return self._pkg_args

    async def _calculate_args(self, metadata: PkgMetadata) -> RecordArg:

        pkg_args = metadata.vars["args"]
        arg = self._tingistry_obj.arg_hive.create_record_arg(childs=pkg_args)

        return arg

    @abstractmethod
    async def get_metadata(
        self, config: Optional[Mapping[str, Any]] = None, register_task: bool = False
    ) -> PkgMetadata:
        """Return metadata associated with this package."""

        pass

    # async def _get_valid_var_combinations(
    #     self, versions=Iterable[PkgVersion]
    # ) -> Iterable[Mapping[str, Any]]:
    #     """Return a list of valid var combinations that uniquely identify a version item.
    #
    #
    #     Aliases are not considered here, those need to be translated before lookup.
    #     """
    #
    #     result = []
    #     for version in versions:
    #         temp = copy.copy(version.vars)
    #         temp.pop("_meta", None)
    #         temp.pop("_mogrify", None)
    #
    #         result.append(temp)
    #
    #     return result

    async def update_metadata(self) -> PkgMetadata:

        return await self.get_metadata({"metadata_max_age": 0})

    async def get_versions(self) -> Iterable[PkgVersion]:

        md: PkgMetadata = await self.get_value("metadata", raise_exception=True)
        return md.versions

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
        result["source"] = vals["source"]
        result["info"] = info
        result["labels"] = vals["labels"]
        result["tags"] = vals["tags"]

        if include_metadata:

            metadata: PkgMetadata = await self.get_metadata(
                config=retrieve_config, register_task=True
            )

            # timestamp = metadata["metadata_check"]
            #
            # pkg_vars = metadata["pkg_vars"]
            # aliases = metadata["aliases"]
            #
            # var_combinations = await self._get_valid_var_combinations(metadata.versions)
            #
            # metadata_result = {
            #     "pkg_args": pkg_vars["args"],
            #     "aliases": aliases,
            #     "timestamp": timestamp,
            #     "version_list": var_combinations,
            # }
            result["metadata"] = metadata.to_dict()

        return result

    # async def find_version_data(
    #     self, metadata: PkgMetadata, vars: Optional[Mapping[str, Any]] = None,
    # ) -> Optional[PkgVersion]:
    #     """Find a matching version item for the provided vars dictionary.
    #
    #     Returns:
    #         A tuple consisting of the version that was found (or None), and the 'exploded' vars that were used
    #     """
    #
    #     if vars is None:
    #         vars = {}
    #
    #     version = find_version(vars=vars, metadata=metadata, var_aliases_replaced=True)
    #     return version

    # async def get_version_folder(
    #     self,
    #     input_vars: Mapping[str, Any] = None,
    #     target_folder: Optional[str] = None,
    #     no_cache: bool = False,
    # ) -> Mapping[str, Any]:
    #     """Retrieve the path to a (possibly cached) folder that represents the package with the specified variables.
    #
    #     If you supply the 'target_folder' argument, a copy of the folder will be created at that location (which is not allowed to exist yet). If you do not, make sure you only do read operations on it; don't change any files in that folder, as that may corrupt results for subequent users of this cached folder.
    #
    #     Returns:
    #         Mapping: a dict with 'path' and 'version_hash' keys
    #     """
    #
    #     if input_vars is None:
    #         input_vars = {}
    #
    #     version_hash = await self.create_version_hash()
    #     version_dir = os.path.join(BRING_PKG_VERSION_CACHE, self.pkg_id, version_hash)
    #
    #     # use cached dir
    #     if no_cache or not os.path.isdir(version_dir):
    #
    #         transmogrificator: Transmogrificator = await self.create_transmogrificator(
    #             vars=input_vars
    #         )
    #
    #         result = await transmogrificator.run_async()
    #         folder = result.result_value["folder_path"]
    #         # folder = result.explanation_data["result"]["folder_path"]
    #
    #         if os.path.exists(version_dir):
    #             shutil.rmtree(version_dir)
    #         else:
    #             ensure_folder(os.path.dirname(version_dir))
    #
    #         shutil.move(folder, version_dir)
    #
    #     if not target_folder:
    #         return {"path": version_dir, "version_hash": version_hash}
    #
    #     target_folder = os.path.expanduser(target_folder)
    #     if os.path.exists(target_folder):
    #         raise FrklException(
    #             msg=f"Can't create version folder for pkg '{self.pkg_id}'.",
    #             reason=f"Target folder already exists: {target_folder}",
    #         )
    #     ensure_folder(os.path.dirname(target_folder))
    #
    #     shutil.copytree(version_dir, target_folder)
    #
    #     return {"path": target_folder, "version_hash": version_hash}

    async def create_transmogrificator(
        self,
        vars: Optional[Mapping[str, Any]] = None,
        extra_mogrifiers: Iterable[Union[str, Mapping[str, Any]]] = None,
    ) -> Transmogrificator:

        if vars is None:
            vars = {}

        vals: Mapping[str, Any] = await self.get_values(  # type: ignore
            "metadata", "args", resolve=True
        )
        metadata: PkgMetadata = vals["metadata"]
        args: RecordArg = vals["args"]

        _vars = get_seeded_dict(args.default, vars, merge_strategy="update")
        filtered: Dict[str, Any] = {}
        for k, v in _vars.items():
            if k in args.arg_names:
                filtered[k] = v

        _vars_replaced = replace_var_aliases(vars=filtered, metadata=metadata)

        _vars = args.validate(_vars_replaced, raise_exception=True)

        version: Optional[PkgVersion] = find_version(vars=_vars, metadata=metadata)

        if not version:
            if not vars:
                reason = "No version match for no/empty variable input."
            elif len(vars) == 1:
                reason = f"Can't find version match for var: {vars}"
            else:
                vars_string = to_value_string(_vars, reindent=2)
                reason = (
                    f"Can't find version match for vars combination:\n\n{vars_string}"
                )
            raise FrklException(msg=f"Can't process pkg '{self.name}'.", reason=reason)

        mogrify_list: List[Union[str, Mapping[str, Any]]] = list(version.steps)
        if extra_mogrifiers:
            mogrify_list.extend(extra_mogrifiers)

        pipeline_id = generate_valid_identifier(prefix="pipe_", length_without_prefix=6)

        task_desc = TaskDesc(
            name=f"prepare package '{self.name}'",
            msg=f"gathering file(s) for package '{self.name}'",
        )

        mogrify_vars = metadata.vars["mogrify_vars"]

        tm = await self._transmogritory.create_transmogrificator(
            mogrify_list,
            vars=vars,
            args=mogrify_vars,
            name=self.name,
            task_desc=task_desc,
            pipeline_id=pipeline_id,
        )

        return tm

    # async def create_id_dict(
    #     self, _include_hash: bool = True, **vars: Any
    # ) -> Dict[str, Any]:
    #
    #     full_vars = await self.calculate_full_vars(**vars)
    #     result: Dict[str, Any] = {}
    #     result["vars"] = full_vars
    #     result["pkg_name"] = self.name
    #     result["pkg_index"] = self.bring_index.id
    #
    #     if _include_hash:
    #         hashes = DeepHash(result)
    #         h = hashes[result]
    #         result["hash"] = h
    #
    #     return result

    # async def create_version_hash(self, **vars: Any) -> str:
    #
    #     full_vars = await self.calculate_full_vars(**vars)
    #     id_dict: Dict[str, Any] = {}
    #     id_dict["vars"] = full_vars
    #     id_dict["pkg_name"] = self.name
    #     id_dict["pkg_index"] = self.bring_index.id
    #
    #     hashes = DeepHash(id_dict)
    #     return hashes[id_dict]

    async def get_pkg_defaults(self) -> Mapping[str, Any]:

        args: RecordArg = await self.get_value("args", raise_exception=True)
        return args.default

    # async def calculate_defaults(self):
    #
    #     index_defaults = await self.bring_index.get_index_defaults()
    #     pkg_defaults = await self.get_pkg_defaults()
    #
    #     return get_seeded_dict(pkg_defaults, index_defaults, merge_strategy="update")

    # async def merge_with_defaults(self, **vars: Any) -> MutableMapping[str, Any]:
    #
    #     vals: Mapping[str, Any] = await self.get_values(  # type: ignore
    #         "metadata", "args", resolve=True
    #     )
    #     # _pkg_metadata: Mapping[str, Any] = vals["metadata"]
    #     args: RecordArg = vals["args"]
    #
    #     pkg_defaults = args.default
    #
    #     _vars = get_seeded_dict(pkg_defaults, vars, merge_strategy="update")
    #
    #     filtered: Dict[str, Any] = {}
    #     for k, v in _vars.items():
    #         if k in args.arg_names:
    #             filtered[k] = v
    #
    #     return filtered

    async def calculate_full_vars(self, **vars: Any) -> MutableMapping[str, Any]:

        vals: Mapping[str, Any] = await self.get_values(  # type: ignore
            "metadata", "args", resolve=True
        )
        _pkg_metadata: PkgMetadata = vals["metadata"]
        args: RecordArg = vals["args"]

        pkg_defaults = args.default
        _vars = get_seeded_dict(pkg_defaults, vars, merge_strategy="update")
        filtered: Dict[str, Any] = {}
        for k, v in _vars.items():
            if k in args.arg_names:
                filtered[k] = v

        _vars_replaced = replace_var_aliases(vars=filtered, metadata=_pkg_metadata)

        validated = args.validate(_vars_replaced, raise_exception=True)
        return validated


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
    ) -> PkgMetadata:

        val: PkgMetadata = await self.get_value(  # type: ignore
            "metadata"
        )
        return val

    async def retrieve(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        # if not self._index:
        #     raise FrklException(
        #         msg=f"Can't retrieve values for PkgTing '{self.full_name}'.",
        #         reason="Index not set yet.",
        #     )

        result: Dict[str, Any] = {}

        if "args" in value_names or "metadata" in value_names:
            rq = copy.deepcopy(requirements["metadata"])
            md: Optional[PkgMetadata] = PkgMetadata.from_dict(rq)
        else:
            md = None

        for vn in value_names:
            # if vn == "index_name":
            #     result[vn] = self.bring_index.name
            if vn == "args":
                result[vn] = await self._calculate_args(md)  # type: ignore
            elif vn == "metadata":
                result[vn] = md
            else:
                result[vn] = requirements[vn]

        return result


class DynamicPkgTing(PkgTing):
    def __init__(self, name, meta: TingMeta):

        super().__init__(name=name, meta=meta)

    async def get_metadata(
        self, config: Optional[Mapping[str, Any]] = None, register_task: bool = False
    ) -> PkgMetadata:
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
    ) -> PkgMetadata:
        """Return metadata associated with this package, doesn't look-up 'source' dict itself."""

        resolver = self._get_resolver(source_dict)

        cached = await resolver.get_cached_metadata(
            source_details=source_dict, override_config=config
        )
        if not cached and register_task:
            task_desc = TaskDesc(
                name=f"metadata retrieval {self.name}",
                msg=f"retrieving valid metadata for package '{self.name}'",
            )
            task_desc.task_started()

        metadata: PkgMetadata = await resolver.get_pkg_metadata(
            source_dict, override_config=config
        )

        if not cached and register_task:
            task_desc.task_finished(msg="metadata retrieved")  # type: ignore

        return metadata

    def _get_resolver(self, source_dict: Dict) -> PkgType:

        pkg_type = source_dict.get("type", None)
        if pkg_type is None:
            raise KeyError(f"No 'type' key in package details: {dict(source_dict)}")

        pf: PluginFactory = get_pkg_type_plugin_factory(self._tingistry_obj.arg_hive)
        # pm: PluginManager = self._tingistry_obj.get_plugin_manager("pkg_type")

        resolver: PkgType = pf.get_singleton(pkg_type, raise_exception=False)
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

        # if not self._index:
        #     raise FrklException(
        #         msg=f"Can't retrieve values for PkgTing '{self.full_name}'.",
        #         reason="Index not set yet.",
        #     )

        result: Dict[str, Any] = {}
        source = requirements["source"]

        resolver = self._get_resolver(source_dict=source)

        seed_data = await resolver.get_seed_data(source)
        if seed_data is None:
            seed_data = {}

        # if "index_name" in value_names:
        #     result["index_name"] = self.bring_index.name

        if "source" in value_names:
            result["source"] = source

        metadata: Optional[PkgMetadata] = None
        if (
            "metadata" in value_names
            or "args" in value_names
            or "aliases" in value_names
            or "metadata_valid" in value_names
        ):
            metadata = await self._get_metadata(source)
            result["metadata"] = metadata

        if "args" in value_names:
            result["args"] = await self._calculate_args(metadata=metadata)  # type: ignore

        if "aliases" in value_names:
            result["aliases"] = metadata.aliases  # type: ignore

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

        # if "tags" in value_names:
        #     tags = requirements.get("tags", [])
        #     result["tags"] = tags

        if "tags" in value_names:
            result["tags"] = requirements.get("tags", [])
            parent_tags: Iterable[str] = seed_data.get("tags", None)
            if parent_tags:
                result["tags"].extend(parent_tags)

        return result
