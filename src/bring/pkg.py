# -*- coding: utf-8 -*-
import copy
import logging
import os
import shutil
from typing import Dict, Any, Union, List

from anyio import create_task_group

from bring.artefact_handlers import ArtefactHandler
from bring.defaults import DEFAULT_ARTEFACT_METADATA
from bring.transform import MergeTransformer
from frtls.dicts import get_seeded_dict, dict_merge
from frtls.exceptions import FrklException
from frtls.files import ensure_folder
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


class Pkg(SimpleTing):
    def __init__(self, name, meta: Dict[str, Any]):

        super().__init__(name=name, meta=meta)

    def provides(self) -> Dict[str, str]:

        return {
            "source": "dict",
            "metadata": "dict",
            "artefact": "dict",
            "profiles_config": "dict",
            "aliases": "dict",
            "args": "args",
            "info": "dict",
            "labels": "dict",
        }

    def requires(self) -> Dict[str, str]:

        return {
            "source": "dict",
            "artefact": "dict?",
            "profiles": "dict?",
            "aliases": "dict?",
            "info": "dict",
            "labels": "dict",
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
        ):
            metadata = await self._get_metadata(source)
            result["metadata"] = metadata

        if "args" in value_names:
            result["args"] = await self._calculate_args(source, metadata=metadata)

        if "aliases" in value_names:
            result["aliases"] = await self._get_aliases(metadata)

        if "artefact" in value_names:
            artefact = get_seeded_dict(
                dict_obj=requirements["artefact"], seed_dict=DEFAULT_ARTEFACT_METADATA
            )
            result["artefact"] = artefact

        if "profiles_config" in value_names:
            profile_config = requirements["profiles"]
            result["profiles_config"] = profile_config

        if "info" in value_names:
            result["info"] = requirements["info"]

        if "labels" in value_names:
            result["labels"] = requirements["labels"]

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

        arg = self.tingistry._arg_hive.create_record_arg(childs=result)

        return arg

    async def get_metadata(self):
        """Return metadata associated with this package."""

        vals = await self.get_values("source")
        return self._get_metadata(vals["source"])

    async def _get_metadata(self, source_dict):
        """Return metadata associated with this package, doesn't look-up 'source' dict itself."""

        print(self.tingistry)
        return await self.tingistry.get_pkg_metadata(source_dict)

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

    async def get_profiles_config(self):

        vals = await self.get_values("profiles_config")
        return vals["profiles_config"]

    async def get_profile_config(self, profile_name):

        return self.get_profiles_config().get(profile_name, {})

    async def get_info(self, include_metadata=False):

        val_keys = ["info", "source", "labels"]
        if include_metadata:
            val_keys.append("metadata")

        vals = await self.get_values(*val_keys)

        info = vals["info"]
        source_details = vals["source"]
        var_map = source_details.get("var_map", {})

        result = {}

        result["info"] = info
        result["labels"] = vals["labels"]

        if include_metadata:

            metadata = vals["metadata"]
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

        resolver = self.tingistry.get_resolver(source_details)

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

        handler: ArtefactHandler = self.tingistry.get_artefact_handler(
            artefact_details, artefact=art_path
        )

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
        profiles: Union[List[str], str] = None,
        target=None,
        strategy="default",
        write_metadata=False,
    ) -> Dict[str, str]:

        if strategy not in ["force", "default"]:
            raise NotImplementedError()

        # TODO: read from profile
        profile_defaults = {}
        vars_final = get_seeded_dict(dict_obj=vars, seed_dict=profile_defaults)
        artefact_folder = await self.provide_artefact_folder(vars=vars_final)

        profiles_config = await self.get_profiles_config()

        results = {}

        async def transform_one_profile(
            profile_name, transform_profile, source_folder, p_config
        ):

            p_config["vars"] = vars
            result_path = transform_profile.transform(
                input_path=source_folder, config=p_config
            )

            results[profile_name] = result_path

        async with create_task_group() as tg:

            for profile_name in profiles:

                transform_profile = self.tingistry.get_transform_profile(profile_name)
                p_config = profiles_config.get(profile_name, {})

                await tg.spawn(
                    transform_one_profile,
                    profile_name,
                    transform_profile,
                    artefact_folder,
                    p_config,
                )

        if target is None:
            return results

        if len(results) == 1 and not os.path.exists(target):
            target_base = os.path.dirname(target)
            ensure_folder(target_base)
            source = list(results.values())[0]
            shutil.move(source, target)
            return {"target": target}
        else:
            merge = MergeTransformer()
            config = {
                "sources": [results["executables"]],
                "vars": vars,
                "delete_sources": True,
            }
            merge.transform(target, transform_config=config)
            return {"target": target}
