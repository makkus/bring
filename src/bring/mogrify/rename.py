# -*- coding: utf-8 -*-
import logging
import os
import shutil
from typing import Any, Mapping

from bring.mogrify import SimpleMogrifier


log = logging.getLogger("bring")


class RenameMogrifier(SimpleMogrifier):

    _plugin_name: str = "rename"

    _requires: Mapping[str, str] = {"rename_map": "dict", "folder_path": "string"}
    _provides: Mapping[str, str] = {"folder_path": "string"}

    def get_msg(self) -> str:

        return "renaming files"

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        path = requirements["folder_path"]
        rename_map = requirements["rename_map"]

        if not rename_map:
            return path

        for source, target in rename_map.items():
            full_source = os.path.join(path, source)
            full_target = os.path.join(path, target)
            shutil.move(full_source, full_target)

        return {"folder_path": path}
