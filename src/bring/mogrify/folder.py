# -*- coding: utf-8 -*-
import os
import shutil
from typing import Any, Mapping

from bring.mogrify import SimpleMogrifier


class FolderMogrifier(SimpleMogrifier):

    _plugin_name: str = "folder"

    _requires: Mapping[str, str] = {"folder_path": "string"}
    _provides: Mapping[str, str] = {"folder_path": "string"}

    def get_msg(self) -> str:

        return "copying folder"

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        path: str = requirements["folder_path"]

        target_path = self.create_temp_dir(prefix="folder_")
        target_path = os.path.join(target_path, os.path.basename(path))
        shutil.copytree(path, target_path)
        return {"folder_path": target_path}
