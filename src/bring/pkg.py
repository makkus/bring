# -*- coding: utf-8 -*-
import copy
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Union

from anyio import create_task_group
from bring.artefact_handlers import ArtefactHandler
from bring.defaults import (
    BRING_ALLOWED_MARKER_NAME,
    BRING_METADATA_FOLDER_NAME,
    BRING_WORKSPACE_FOLDER,
    DEFAULT_ARTEFACT_METADATA,
)
from bring.pkg_resolvers import PkgResolver
from bring.transform.merge import MergeTransformer
from bring.utils import is_valid_bring_target, set_folder_bring_allowed
from frtls.dicts import dict_merge, get_seeded_dict
from frtls.exceptions import FrklException
from frtls.files import ensure_folder
from frtls.formats.output_formats import serialize
from frtls.types.typistry import TypistryPluginManager
from tings.exceptions import TingException
from tings.ting import SimpleTing


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

        self._bring_pkgs = meta["tingistry"]["obj"].get_ting("bring.pkgs")
        super().__init__(name=name, meta=meta)

    def provides(self) -> Dict[str, str]:

        return {
            "source": "dict",
            "metadata": "dict",
            "artefact": "dict",
            "file_sets": "dict",
            "aliases": "dict",
            "args": "args",
            "info": "dict",
            "labels": "dict",
        }

    def requires(self) -> Dict[str, str]:

        return {
            "source": "dict",
            "file_sets": "dict?",
            "aliases": "dict?",
            "info": "dict?",
            "labels": "dict?",
            "ting_make_timestamp": "string",
            "ting_make_metadata": "dict",
        }

    async def retrieve(self, *value_names: str, **requirements) -> Dict[str, Any]:

        result = {}
        source = requirements["source"]

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
            result["args"] = await self._calculate_args(source, metadata=metadata)

        if "aliases" in value_names:
            result["aliases"] = await self._get_aliases(metadata)

        if "artefact" in value_names:
            resolver_defaults = self._get_resolver(source).get_artefact_defaults(source)
            artefact = get_seeded_dict(
                DEFAULT_ARTEFACT_METADATA,
                resolver_defaults,
                source.get("artefact", None),
            )
            result["artefact"] = artefact

        if "file_sets" in value_names:
            file_sets = requirements.get("file_sets", {})
            result["file_sets"] = file_sets

        if "info" in value_names:
            result["info"] = requirements.get("info", {})

        if "labels" in value_names:
            result["labels"] = requirements.get("labels", {})

        return result

    async def _get_aliases(self, metadata):

        return metadata.get("aliases", {})

    async def get_aliases(self):

        metadata = await self.get_metadata()
        return self._get_aliases(metadata)

    async def _calculate_args(self, source_dict, metadata):

        defaults = metadata["defaults"]

        args = copy.copy(DEFAULT_ARG_DICT)
        if source_dict.get("args", None):
            args = dict_merge(args, source_dict["args"], copy_dct=False)

        result = {}

        for arg, default in defaults.items():
            args_dict = args.get(arg, {})
            args_dict["default"] = default
            # arg_obj = Arg.from_dict(name=arg, hive=None, default=default, **args_dict)
            result[arg] = args_dict

        arg = self.tingistry.arg_hive.create_record_arg(childs=result)

        return arg

    async def get_metadata(
        self, config: Optional[Mapping[str, Any]] = None
    ) -> Mapping[str, Any]:
        """Return metadata associated with this package."""

        vals = await self.get_values("source")
        return await self._get_metadata(vals["source"], config=config)

    async def _get_metadata(
        self, source_dict, config: Optional[Mapping[str, Any]] = None
    ):
        """Return metadata associated with this package, doesn't look-up 'source' dict itself."""

        resolver = self._get_resolver(source_dict)
        if resolver is None:
            r_type = source_dict.get("type", source_dict)
            raise TingException(
                ting=self,
                msg=f"Can't retrieve metadata for pkg '{self.name}'.",
                reason=f"No resolver registered for: {r_type}",
            )

        return await resolver.get_pkg_metadata(source_dict, override_config=config)

    def _get_resolver(self, source_dict: Dict) -> PkgResolver:

        pkg_type = source_dict.get("type", None)
        if pkg_type is None:
            raise KeyError(f"No 'type' key in package details: {dict(source_dict)}")

        pm: TypistryPluginManager = self.tingistry.get_plugin_manager("pkg_resolver")
        plugin: PkgResolver = pm.get_plugin_for(pkg_type)
        return plugin

    def _get_artefact_handler(self, artefact_details: Dict[str, Any]):

        art_type = artefact_details.get("type", None)
        if art_type is None:
            raise KeyError(
                f"No 'type' key in artefact details: {dict(artefact_details)}"
            )

        pm: TypistryPluginManager = self.tingistry.get_plugin_manager(
            "artefact_handler"
        )
        plugin: ArtefactHandler = pm.get_plugin_for(art_type)
        return plugin

    def _get_translated_value(self, var_map, value):

        if value not in var_map.keys():
            return value

        return var_map[value]

    async def get_valid_var_combinations(self):

        vals = await self.get_values("metadata", "source")
        metadata = vals["metadata"]
        source_details = vals["source"]

        return self._get_valid_var_combinations(
            source_details=source_details, metadata=metadata
        )

    async def _get_valid_var_combinations(self, source_details, metadata):

        versions = metadata["versions"]
        var_map = source_details.get("var_map", {})

        valid = []
        for version in versions:
            temp = {}
            for k, v in version.items():
                if k == "_meta":
                    continue

                v = self._get_translated_value(var_map, v)

                temp[k] = v
            valid.append(temp)

        return valid

    async def get_file_sets(self) -> Dict[str, Dict]:

        vals = await self.get_values("file_sets")
        return vals["file_sets"]

    async def update_metadata(self) -> Mapping[str, Any]:

        return await self.get_metadata({"metadata_max_age": 0})

    async def get_file_set(self, name: str) -> Dict:

        return self.get_file_sets().get(name, {})

    async def get_info(
        self,
        include_metadata: bool = False,
        retrieve_config: Optional[Mapping[str, Any]] = None,
    ):

        val_keys = ["info", "source", "labels", "file_sets", "artefact"]
        vals = await self.get_values(*val_keys)

        info = vals["info"]
        source_details = vals["source"]
        var_map = source_details.get("var_map", {})
        file_sets = vals["file_sets"]

        metadata: Dict[str, Any] = None
        if include_metadata:
            metadata = await self._get_metadata(
                source_dict=source_details, config=retrieve_config
            )

        result = {}

        result["info"] = info
        result["labels"] = vals["labels"]
        result["artefact"] = vals["artefact"]
        result["file_sets"] = file_sets

        if include_metadata:

            timestamp = metadata["metadata_check"]

            defaults = metadata["defaults"]
            aliases = metadata["aliases"]
            values = {}

            for version in metadata["versions"]:

                for k, v in version.items():
                    if k == "_meta":
                        continue

                    v = self._get_translated_value(var_map, v)

                    val = values.setdefault(k, [])
                    if v not in val:
                        val.append(v)

            var_combinations = await self._get_valid_var_combinations(
                source_details=source_details, metadata=metadata
            )

            metadata_result = {
                "defaults": defaults,
                "aliases": aliases,
                "allowed_values": values,
                "timestamp": timestamp,
                "version_list": var_combinations,
            }
            result["metadata"] = metadata_result

        return result

    async def get_artefact(self, vars: Dict[str, str]) -> Dict:

        vals = await self.get_values("metadata", "source")
        source_details = vals["source"]
        metadata = vals["metadata"]

        resolver = self._get_resolver(source_details)

        version = resolver.find_version(
            vars=vars,
            defaults=metadata["defaults"],
            aliases=metadata["aliases"],
            versions=metadata["versions"],
            source_details=source_details,
        )

        if version is None:

            var_combinations = await self._get_valid_var_combinations(
                source_details=source_details, metadata=metadata
            )
            comb_string = ""
            for vc in var_combinations:
                comb_string = comb_string + "  - " + str(vc) + "\n"

            raise FrklException(
                msg=f"Can't retrieve artefact for package '{self.name}'.",
                reason=f"Can't find version that matches provided variables: {vars}",
                solution=f"Choose a valid variable combinations:\n{comb_string}",
            )

        download_path = await resolver.get_artefact_path(
            version=version, source_details=source_details
        )

        return download_path

    async def provide_artefact_folder(self, vars: Dict[str, str]):

        vals = await self.get_values("artefact")
        artefact_details = vals["artefact"]

        art_path = await self.get_artefact(vars=vars)

        handler: ArtefactHandler = self._get_artefact_handler(artefact_details)

        folder = await handler.provide_artefact_folder(
            artefact_path=art_path, artefact_details=artefact_details
        )

        return folder

    def copy_file(self, source, target, force=False, method="move"):

        os.makedirs(os.path.dirname(target), exist_ok=True)
        # if force and os.path.exists(target):
        #     os.unlink(target)

        if method == "copy":
            shutil.copyfile(source, target, follow_symlinks=False)
            # TODO: file attributes
        elif method == "move":
            shutil.move(source, target)

    async def install(
        self,
        vars: Dict[str, str],
        profiles: Optional[Union[List[str], str]] = None,
        target: Optional[Union[str, Path]] = None,
        merge: bool = False,
        strategy="default",
        write_metadata=False,
    ) -> Dict[str, str]:

        if strategy not in ["force", "default"]:
            raise NotImplementedError()

        # TODO: read from profile
        profile_defaults = {}
        vars_final = get_seeded_dict(profile_defaults, vars)
        artefact_folder = await self.provide_artefact_folder(vars=vars_final)

        file_sets = await self.get_file_sets()

        results = {}

        async def transform_one_profile(
            profile_name, transform_profile, source_folder, p_config
        ):

            if not isinstance(p_config, Mapping):
                content = serialize(p_config, format("yaml"))
                raise FrklException(
                    msg=f"Can't process file_set '{profile_name}' for package '{self.name}'.",
                    reason=f"Config object is not a dictionary (instead: {type(p_config)}).\n\nContent of invalid config:\n{content}",
                )
            p_config["vars"] = vars

            result_path = transform_profile.transform(
                input_path=source_folder, config=p_config
            )

            results[profile_name] = result_path

        async with create_task_group() as tg:

            for profile_name in profiles:

                transform_profile = self.tingistry.get_ting(
                    f"bring.transform.{profile_name}"
                )
                if transform_profile is None:
                    raise FrklException(
                        msg=f"Can't process file set '{profile_name}' for package '{self.name}'.",
                        reason=f"No profile configured to handle a file set called '{profile_name}'.",
                    )
                p_config = file_sets.get(profile_name, {})

                await tg.spawn(
                    transform_one_profile,
                    profile_name,
                    transform_profile.transform_profile,
                    artefact_folder,
                    p_config,
                )

        if target is None and not merge:
            return results

        if target is None:
            target = tempfile.mkdtemp(
                prefix=f"{self.name}_install_", dir=BRING_WORKSPACE_FOLDER
            )

        if not is_valid_bring_target(target):
            raise FrklException(
                f"Can't install files from temp install folder(s) to target '{target}'",
                reason="Folder exists, is non-empty and was not created by bring.",
                solution=f"Either delete the folder or it's content, or create a marker file '.{BRING_ALLOWED_MARKER_NAME}' or '{BRING_METADATA_FOLDER_NAME}{os.path.sep}{BRING_ALLOWED_MARKER_NAME}' to indicate it is ok for bring to add/delete files in there. Back up the contents of that folder in case there is important data!",
            )

        if isinstance(target, Path):
            _target = target.resolve().as_posix()
        else:
            _target = os.path.expanduser(target)

        if len(results) == 1 and not os.path.exists(_target):
            target_base = os.path.dirname(_target)
            ensure_folder(target_base)
            source = list(results.values())[0]
            print("move: {}".format(source))
            shutil.move(source, _target)
            set_folder_bring_allowed(_target)
            return {"target": _target}
        else:
            merge = MergeTransformer()
            config = {"sources": results.values(), "vars": vars, "delete_sources": True}
            merge.transform(_target, transform_config=config)
            set_folder_bring_allowed(_target)
            return {"target": _target}
