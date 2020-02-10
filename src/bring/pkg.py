# -*- coding: utf-8 -*-
import copy
import logging
import os
import shutil
from typing import Dict, Any, Union, List

from bring.artefact_handlers import ArtefactHandler
from bring.defaults import DEFAULT_ARTEFACT_METADATA
from bring.file_sets import FileSetFilter
from bring.file_sets.default import DEFAULT_FILTER
from frtls.args.arg import Arg, Args
from frtls.dicts import get_seed_dict, dict_merge
from frtls.exceptions import FrklException
from frtls.files import ensure_folder
from tings.ting import SimpleTing

log = logging.getLogger("bring")

DEFAULT_ARG_DICT = {
    "os": {"doc": {"short_help": "The target os for this package."}},
    "arch": {"doc": {"short_help": "The target architecture for this package."}},
    "version": {"doc": {"short_help": "The version of the package."}},
}


class BringPkgDetails(SimpleTing):
    def __init__(self, name, meta: Dict[str, Any]):

        super().__init__(name=name, meta=meta)

    def provides(self) -> Dict[str, str]:

        return {
            "source": "dict",
            "metadata": "dict",
            "artefact": "dict",
            "filters": "dict",
            "args": "args",
            "doc": "dict",
        }

    def requires(self) -> Dict[str, str]:

        return {"dict": "dict"}

    async def retrieve(self, *value_names: str, **requirements) -> Dict[str, Any]:

        parsed_dict = requirements["dict"]
        result = {}
        source = parsed_dict.get("source", {})

        if "source" in value_names:
            result["source"] = source

        if "metadata" in value_names:

            metadata = await self._get_metadata(source)
            result["metadata"] = metadata

        if "artefact" in value_names:
            artefact = get_seed_dict(
                dict_obj=parsed_dict.get("artefact", None),
                seed_dict=DEFAULT_ARTEFACT_METADATA,
            )
            result["artefact"] = artefact

        if "filters" in value_names:
            filters_conf = parsed_dict.get("filters", None)
            filters = await self._tingistry.get_pkg_filters(filters_conf)

            result["filters"] = filters

        if "doc" in value_names:
            result["doc"] = parsed_dict.get("doc", {})

        if "args" in value_names:
            result["args"] = await self._calculate_args(source)

        return result

    async def _calculate_args(self, source_dict):

        metadata = await self._get_metadata(source_dict)
        defaults = metadata["defaults"]

        args = copy.copy(DEFAULT_ARG_DICT)
        if source_dict.get("args", None):
            args = dict_merge(args, source_dict["args"], copy_dct=False)

        result = []

        for arg, default in defaults.items():
            args_dict = args.get(arg, {})
            arg_obj = Arg.from_dict(name=arg, default=default, **args_dict)
            result.append(arg_obj)

        args = Args(*result)

        return args

    async def _get_metadata(self, source_dict):
        return await self._tingistry.get_pkg_metadata(source_dict)

    def _get_translated_value(self, var_map, value):

        if value not in var_map.keys():
            return value

        return var_map[value]

    async def _get_valid_var_combinations(self):

        vals = await self.get_values("metadata", "source")
        metadata = vals["metadata"]
        versions = metadata["versions"]
        source_details = vals["source"]
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

    async def get_info(self):

        vals = await self.get_values("metadata", "source")
        source_details = vals["source"]
        var_map = source_details.get("var_map", {})
        metadata = vals["metadata"]

        timestamp = metadata["metadata_check"]

        defaults = metadata["defaults"]
        values = {}

        for version in metadata["versions"]:

            for k, v in version.items():
                if k == "_meta":
                    continue

                v = self._get_translated_value(var_map, v)

                val = values.setdefault(k, [])
                if v not in val:
                    val.append(v)

        return {"defaults": defaults, "values": values, "timestamp": timestamp}

    async def get_artefact(self, vars: Dict[str, str]) -> Dict:

        vals = await self.get_values("metadata", "source")
        source_details = vals["source"]
        metadata = vals["metadata"]

        resolver = self._tingistry.get_resolver(source_details)

        default_vars = self._tingistry.default_vars
        vars_final = get_seed_dict(dict_obj=vars, seed_dict=default_vars)

        version = resolver.find_version(
            vars=vars_final,
            defaults=metadata["defaults"],
            versions=metadata["versions"],
            source_details=source_details,
        )

        if version is None:

            var_combinations = await self._get_valid_var_combinations()
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

        handler: ArtefactHandler = self._tingistry.get_artefact_handler(
            artefact_details
        )

        art_path = await self.get_artefact(vars=vars)
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
        filters: Union[List[str], str] = None,
        target=None,
        strategy="default",
    ) -> Dict[str, str]:

        if strategy not in ["force", "default"]:
            raise NotImplementedError()

        file_paths = await self.get_file_paths(vars=vars, filters=filters)

        if target is None:
            target = os.getcwd()

        ensure_folder(target)

        copied = {}

        for rel_file, source in file_paths.items():
            target_file = os.path.join(target, rel_file)
            exists = os.path.exists(target_file)

            if not exists:
                log.info(f"Copying file: {rel_file}")
                self.copy_file(source, target_file, force=False)
                copied[rel_file] = target_file
                continue

            if strategy == "default":
                log.info(f"Not copying file '{rel_file}': target file already exists")
                continue
            elif strategy == "force":
                log.info(f"Copying (force) file: {rel_file}")
                self.copy_file(source, target_file, force=True)
                copied[rel_file] = target_file

        return copied

    async def get_file_paths(
        self, vars: Dict[str, str], filters: Union[List[str], str] = None
    ) -> Dict[str, str]:

        vals = await self.get_values("filters")
        pkg_filters: Dict[str, FileSetFilter] = vals["filters"]

        if isinstance(filters, str):
            filters = [filters]

        if not filters:
            filters = [DEFAULT_FILTER]

        path = await self.provide_artefact_folder(vars=vars)

        filter_and = True

        files = {}
        for filter in filters:
            if filter not in pkg_filters.keys():
                continue

            filter_obj = pkg_filters[filter]

            filter_files = filter_obj.get_file_set(folder_path=path)
            if filter_and:
                for target, source in filter_files.items():
                    if target in files.keys() and source != files[target]:
                        log.error(
                            f"Duplicate target file '{target}', ignoring second one: {source}"
                        )
                        continue
                    files[target] = source
            else:
                raise NotImplementedError()

        return files
