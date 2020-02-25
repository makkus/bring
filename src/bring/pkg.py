# -*- coding: utf-8 -*-
import copy
import logging
import os
import shutil
from typing import Any, Dict, Iterable, Mapping, Optional

from bring.interfaces.tui.task_progress import TerminalRunWatch
from bring.mogrify import Transmogritory
from bring.pkg_resolvers import PkgResolver
from bring.utils import find_version
from frtls.dicts import get_seeded_dict
from frtls.exceptions import FrklException
from frtls.tasks import Tasks
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

        pkg_args = metadata["pkg_args"]
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
            source_dict, self.bring_context, override_config=config
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

            pkg_args = metadata["pkg_args"]
            aliases = metadata["aliases"]

            var_combinations = await self._get_valid_var_combinations(metadata=metadata)

            metadata_result = {
                "pkg_args": pkg_args,
                "aliases": aliases,
                "timestamp": timestamp,
                "version_list": var_combinations,
            }
            result["metadata"] = metadata_result

        return result

    async def create_version_folder(self, vars: Dict[str, Any]) -> Tasks:

        vals = await self.get_values("source", "metadata")
        metadata = vals["metadata"]

        version = find_version(vars=vars, metadata=metadata)

        mogrify_list = version["_mogrify"]

        # import pp
        # pp(metadata)

        transmogritory: Transmogritory = self._tingistry_obj._transmogritory

        tm = transmogritory.create_transmogrificator(mogrify_list, pkg=self)

        # last_mogrifier = tm._last_item

        run_watcher = TerminalRunWatch(sort_task_names=False)
        vals = await tm.transmogrify(run_watcher)
        # print(last_mogrifier)
        # vals = await last_mogrifier.get_values()
        # import pp
        # pp(vals)

        return vals

        # path, tasks = await resolver.create_pkg_version_folder(
        #     vars=vars, source_details=source, metadata=metadata
        # )
        #
        # return path, tasks

    # async def get_artefact(self, vars: Dict[str, str]) -> Dict:
    #
    #     vals = await self.get_values("metadata", "source")
    #     source_details = vals["source"]
    #     metadata = vals["metadata"]
    #
    #     resolver = self._get_resolver(source_details)
    #
    #     version = resolver.find_version(
    #         vars=vars,
    #         pkg_args=metadata["args"],
    #         aliases=metadata["aliases"],
    #         versions=metadata["versions"],
    #         var_map=source_details.get("var_map", {}),
    #     )
    #
    #     if version is None:
    #
    #         # TODO: translate aliases
    #         var_combinations = await self._get_valid_var_combinations(
    #             metadata=metadata
    #         )
    #         comb_string = ""
    #         for vc in var_combinations:
    #             comb_string = comb_string + "  - " + str(vc) + "\n"
    #
    #         raise FrklException(
    #             msg=f"Can't retrieve artefact for package '{self.name}'.",
    #             reason=f"Can't find version that matches provided variables: {vars}",
    #             solution=f"Choose a valid variable combinations:\n{comb_string}",
    #         )
    #
    #     download_path = await resolver.create_version_folder(
    #         vars=vars, source_details=source_details
    #     )
    #
    #     return download_path

    # async def provide_artefact_folder(self, vars: Dict[str, str]):
    #
    #     vals = await self.get_values("source")
    #     source = vals["source"]
    #
    #     resolver_defaults = self._get_resolver(source).get_artefact_defaults(source)
    #
    #     artefact_details = get_seeded_dict(
    #         DEFAULT_ARTEFACT_METADATA, resolver_defaults, source.get("artefact", None)
    #     )
    #
    #     art_path = await self.get_artefact(vars=vars)
    #
    #     handler: ArtefactHandler = self._get_artefact_handler(artefact_details)
    #
    #     folder = await handler.provide_artefact_folder(
    #         artefact_path=art_path, artefact_details=artefact_details
    #     )
    #
    #     return folder

    def copy_file(self, source, target, force=False, method="move"):

        os.makedirs(os.path.dirname(target), exist_ok=True)
        # if force and os.path.exists(target):
        #     os.unlink(target)

        if method == "copy":
            shutil.copyfile(source, target, follow_symlinks=False)
            # TODO: file attributes
        elif method == "move":
            shutil.move(source, target)

    # async def install(
    #     self,
    #     vars: Dict[str, str],
    #     profiles: Optional[Union[List[str], str]] = None,
    #     target: Optional[Union[str, Path]] = None,
    #     merge: bool = False,
    #     strategy="default",
    #     write_metadata=False,
    # ) -> Dict[str, str]:
    #
    #     if strategy not in ["force", "default"]:
    #         raise NotImplementedError()
    #
    #     # TODO: read from profile
    #     profile_defaults = {}
    #     vars_final = get_seeded_dict(profile_defaults, vars)
    #     artefact_folder = await self.provide_artefact_folder(vars=vars_final)
    #
    #     results = {}
    #
    #     async def transform_one_profile(
    #         profile_name, transform_profile, source_folder, p_config
    #     ):
    #
    #         if not isinstance(p_config, Mapping):
    #             content = serialize(p_config, format("yaml"))
    #             raise FrklException(
    #                 msg=f"Can't process profile '{profile_name}' for package '{self.name}'.",
    #                 reason=f"Config object is not a dictionary (instead: {type(p_config)}).\n\nContent of invalid config:\n{content}",
    #             )
    #         p_config["vars"] = vars
    #
    #         result_path = transform_profile.transform(
    #             input_path=source_folder, config=p_config
    #         )
    #
    #         results[profile_name] = result_path
    #
    #     async with create_task_group() as tg:
    #
    #         for profile_name in profiles:
    #
    #             transform_profile = self._tingistry_obj.get_ting(
    #                 f"bring.transform.{profile_name}"
    #             )
    #             if transform_profile is None:
    #                 raise FrklException(
    #                     msg=f"Can't process file set '{profile_name}' for package '{self.name}'.",
    #                     reason=f"No profile configured to handle a file set called '{profile_name}'.",
    #                 )
    #             p_config = {}
    #
    #             await tg.spawn(
    #                 transform_one_profile,
    #                 profile_name,
    #                 transform_profile.transform_profile,
    #                 artefact_folder,
    #                 p_config,
    #             )
    #
    #     if target is None and not merge:
    #         return results
    #
    #     if target is None:
    #         target = tempfile.mkdtemp(
    #             prefix=f"{self.name}_install_", dir=BRING_WORKSPACE_FOLDER
    #         )
    #
    #     if not is_valid_bring_target(target):
    #         raise FrklException(
    #             f"Can't install files from temp install folder(s) to target '{target}'",
    #             reason="Folder exists, is non-empty and was not created by bring.",
    #             solution=f"Either delete the folder or it's content, or create a marker file '.{BRING_ALLOWED_MARKER_NAME}' or '{BRING_METADATA_FOLDER_NAME}{os.path.sep}{BRING_ALLOWED_MARKER_NAME}' to indicate it is ok for bring to add/delete files in there. Back up the contents of that folder in case there is important data!",
    #         )
    #
    #     if isinstance(target, Path):
    #         _target = target.resolve().as_posix()
    #     else:
    #         _target = os.path.expanduser(target)
    #
    #     if len(results) == 1 and not os.path.exists(_target):
    #         target_base = os.path.dirname(_target)
    #         ensure_folder(target_base)
    #         source = list(results.values())[0]
    #         log.info(f"moving: {source} \u2192 {target}")
    #         shutil.move(source, _target)
    #         if write_metadata:
    #             set_folder_bring_allowed(_target)
    #         return {"target": _target}
    #     else:
    #         merge = MergeTransformer()
    #         config = {"sources": results.values(), "vars": vars, "delete_sources": True}
    #         merge.transform(_target, transform_config=config)
    #         if write_metadata:
    #             set_folder_bring_allowed(_target)
    #         return {"target": _target}
