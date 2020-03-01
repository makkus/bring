# -*- coding: utf-8 -*-
import os
import shutil
from typing import Any, Dict, Mapping, Optional

from bring.mogrify import SimpleMogrifier
from frtls.defaults import DEFAULT_EXCLUDE_DIRS
from frtls.exceptions import FrklException
from frtls.files import ensure_folder


class MergeMogrifier(SimpleMogrifier):

    _plugin_name: str = "merge"

    def provides(self) -> Mapping[str, str]:

        return {"folder_path": "string"}

    def requires(self) -> Mapping[str, str]:

        return {"folder_paths": "list", "merge_strategy": "dict?"}

    def get_msg(self) -> Optional[str]:

        return "merging folders"

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        strategy: Mapping[str, Any] = requirements.get(
            "merge_strategy", {"type": "default"}
        )
        if isinstance(strategy, str):
            strategy = {"type": strategy}

        folder_paths = requirements["folder_paths"]
        if not folder_paths:
            raise Exception("Can't merge directories, no folder_paths provided.")

        target_path = self.create_temp_dir("merge_")

        for source in folder_paths:

            self.process_folder(source=source, target=target_path, strategy=strategy)

        return {"folder_path": target_path}

    def process_folder(self, source: str, target: str, strategy: Dict):

        exclude_dirs = strategy.get("exclude_dirs", DEFAULT_EXCLUDE_DIRS)

        strategy_type = strategy["type"]
        if not hasattr(self, f"merge_{strategy_type}"):
            raise Exception(f"No '{strategy_type}' merge strategy implemented.")

        func = getattr(self, f"merge_{strategy_type}")

        for root, dirnames, filenames in os.walk(source, topdown=True):

            if exclude_dirs:
                dirnames[:] = [d for d in dirnames if d not in exclude_dirs]

            for filename in filenames:

                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, source)

                func(source, target, rel_path, strategy)

    def merge_default(
        self, source_base: str, target_base: str, rel_path: str, strategy_config: Dict
    ):

        target = os.path.join(target_base, rel_path)
        if os.path.exists(target):
            raise FrklException(
                msg=f"Can't merge/copy file '{rel_path}'.",
                reason=f"File already exists in target: {target_base}",
            )

        source = os.path.join(source_base, rel_path)

        ensure_folder(os.path.dirname(target))
        shutil.move(source, target)
