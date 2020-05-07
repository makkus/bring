# -*- coding: utf-8 -*-
import logging
from typing import Any, Mapping

from bring.mogrify import SimpleMogrifier
from bring.utils.paths import flatten_folder


log = logging.getLogger("bring")


class FlattenFolderMogrifier(SimpleMogrifier):

    _plugin_name: str = "flatten"

    _requires: Mapping[str, str] = {"folder_path": "string", "duplicate": "string?"}
    _provides: Mapping[str, str] = {"folder_path": "string"}

    def get_msg(self) -> str:

        duplicate = self.input_values.get("duplicate", "ignore")
        return (
            f"flattening all files into root folder (duplicate strategy: {duplicate})"
        )

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        path: str = requirements["folder_path"]
        duplicate_strategy = requirements.get("duplicate", "ignore")

        target_path = self.create_temp_dir("flatten_")

        flatten_folder(
            src_path=path, target_path=target_path, strategy=duplicate_strategy
        )

        return {"folder_path": target_path}
