# -*- coding: utf-8 -*-
import logging
import os
import shutil
from typing import Any, Mapping

from bring.mogrify import Mogrifier
from bring.utils.paths import find_matches
from frtls.files import ensure_folder


log = logging.getLogger("bring")


class MoveToSubfolderMogrifier(Mogrifier):

    _plugin_name: str = "move_to_subfolder"

    def requires(self) -> Mapping[str, str]:

        return {"folder_path": "string", "subfolder": "string", "flatten": "boolean?"}

    def get_msg(self) -> str:

        return "move content to subfolder"

    def provides(self) -> Mapping[str, str]:

        return {"folder_path": "string"}

    async def cleanup(self, result: Mapping[str, Any], *value_names, **requirements):

        shutil.rmtree(result["folder_path"])

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        path: str = requirements["folder_path"]
        subfolder: str = requirements["subfolder"]
        flatten: bool = requirements.get("flatten", False)

        target_path = self.create_temp_dir(prefix="subfolder_")
        subfolder_path = os.path.join(target_path, subfolder)

        if not flatten:
            shutil.move(path, subfolder_path)
        else:
            all_files = find_matches(path, output_absolute_paths=True)
            ensure_folder(subfolder_path)
            for f in all_files:
                target = os.path.join(subfolder_path, os.path.basename(f))
                if os.path.exists(target):
                    log.info(
                        f"Duplicate file '{os.path.basename(target)}', ignoring..."
                    )
                    continue
                shutil.move(f, target)

        return {"folder_path": target_path}
