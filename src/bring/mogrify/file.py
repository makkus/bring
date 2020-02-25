# -*- coding: utf-8 -*-
import shutil
from typing import Any, Mapping

from bring.mogrify import Mogrifier


class FileMogrifier(Mogrifier):

    _plugin_name: str = "file"

    def requires(self) -> Mapping[str, str]:

        return {"file_path": "string"}

    def get_msg(self) -> str:

        return "moving file"

    def provides(self) -> Mapping[str, str]:

        return {"folder_path": "string"}

    async def cleanup(self, result: Mapping[str, Any], *value_names, **requirements):

        shutil.rmtree(result["folder_path"])

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        path: str = requirements["file_path"]

        target_path = self.create_temp_dir(prefix="folder_")
        shutil.copy2(path, target_path)

        return {"folder_path": target_path}
