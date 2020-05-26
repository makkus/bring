# -*- coding: utf-8 -*-
import tempfile
from typing import Any, Dict, Iterable, Mapping, Union

from bring.defaults import BRING_RESULTS_FOLDER
from bring.pkg_processing import PkgProcessor
from frtls.args.arg import Arg
from frtls.files import ensure_folder


class InstallPkgProcessor(PkgProcessor):

    _plugin_name = "install_pkg"

    async def get_pkg_name(self) -> str:

        return self._args_holder.merged_vars.get("pkg_name", None)

    async def get_pkg_index(self) -> str:

        return self._args_holder.merged_vars.get("pkg_index", None)

    async def extra_requires(self) -> Mapping[str, Union[str, Arg, Mapping[str, Any]]]:
        """Overwrite this method if you inherit from this class, not '_requires' directly."""

        return {
            "pkg_name": {"type": "string", "doc": "the package name", "required": True},
            "pkg_index": {
                "type": "string",
                "doc": "the name of the index that contains the package",
                "required": True,
            },
            "target": {"type": "string", "doc": "the target folder", "required": False},
            "merge_strategy": {
                "type": "merge_strategy",
                "doc": "the merge strategy to use",
                "default": "bring",
                "required": True,
            },
        }

    async def get_mogrifiers(self, **vars) -> Iterable[Union[str, Mapping[str, Any]]]:

        pkg = await self.get_pkg()
        pkg_metadata = await pkg.create_id_dict(_include_hash=True, **vars)

        merge_strategy: Dict = vars["merge_strategy"]
        merge_strategy.setdefault("config", {})["pkg_metadata"] = pkg_metadata
        merge_strategy["config"]["move_method"] = "move"

        target = vars.get("target", None)
        if not target:
            ensure_folder(BRING_RESULTS_FOLDER)
            target = tempfile.mkdtemp(dir=BRING_RESULTS_FOLDER)

        mogrifiers = [
            {"type": "merge_into", "merge_strategy": merge_strategy, "target": target}
        ]

        return mogrifiers
