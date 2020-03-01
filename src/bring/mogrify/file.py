# -*- coding: utf-8 -*-
import shutil
from typing import Any, Mapping

from bring.mogrify import SimpleMogrifier


class FileMogrifier(SimpleMogrifier):

    _plugin_name: str = "file"

    def requires(self) -> Mapping[str, str]:

        return {"file_path": "string"}

    def get_msg(self) -> str:

        return "moving file"

    def provides(self) -> Mapping[str, str]:

        return {"folder_path": "string"}

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        path: str = requirements["file_path"]

        target_path = self.create_temp_dir(prefix="folder_")
        shutil.copy2(path, target_path)

        return {"folder_path": target_path}
