# -*- coding: utf-8 -*-
import logging
import os
import shutil
from typing import Any, Mapping

from bring.mogrify import SimpleMogrifier
from bring.utils.paths import find_matches


log = logging.getLogger("bring")


class PickSubfolderMogrifier(SimpleMogrifier):

    _plugin_name: str = "pick_subfolder"
    _requires: Mapping[str, str] = {
        "folder_path": "string",
        "subfolder": "string",
        "flatten": "boolean?",
    }
    _provides: Mapping[str, str] = {"folder_path": "string"}

    def get_msg(self) -> str:

        return "pick a subfolder and use as new root"

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        path: str = requirements["folder_path"]
        subfolder: str = requirements["subfolder"]
        flatten: bool = requirements.get("flatten", False)

        target_path = self.create_temp_dir(prefix="pick_subfolder_")

        subfolder_path = os.path.realpath(os.path.join(path, subfolder))
        if not os.path.isdir(subfolder_path):
            raise Exception(f"Subfolder '{subfolder}' does not exist.")

        if not flatten:
            shutil.move(subfolder_path, target_path)
            target_path = os.path.join(target_path, os.path.basename(subfolder_path))
        else:
            all_files = find_matches(subfolder_path, output_absolute_paths=True)
            for f in all_files:
                target = os.path.join(target_path, os.path.basename(f))
                if os.path.exists(target):
                    log.info(
                        f"Duplicate file '{os.path.basename(target)}', ignoring..."
                    )
                    continue
                shutil.move(f, target)

        return {"folder_path": target_path}
