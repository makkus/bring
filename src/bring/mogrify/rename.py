# -*- coding: utf-8 -*-
import os
import shutil
from typing import Any, Mapping, Optional

from bring.mogrify import SimpleMogrifier


class RenameTransformer(SimpleMogrifier):

    _plugin_name: str = "rename"

    def __init__(self, **config):

        super().__init__(**config)

    def get_msg(self) -> Optional[str]:

        return "renaming files"

    def requires(self) -> Mapping[str, str]:

        return {"rename": "dict", "folder_path": "string"}

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        path = requirements["folder_path"]
        rename = requirements["rename"]

        if not rename:
            return path

        for source, target in rename.items():
            full_source = os.path.join(path, source)
            full_target = os.path.join(path, target)
            shutil.move(full_source, full_target)

        return path
