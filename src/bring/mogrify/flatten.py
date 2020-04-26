# -*- coding: utf-8 -*-
import logging
from typing import Any, Mapping

from bring.mogrify import SimpleMogrifier
from bring.utils.paths import flatten_folder


log = logging.getLogger("bring")


class FlattenFolderMogrifier(SimpleMogrifier):

    _plugin_name: str = "flatten"

    def requires(self) -> Mapping[str, str]:

        return {"folder_path": "string", "duplicate": "string?"}

    def get_msg(self) -> str:

        return "flatten folder"

    def provides(self) -> Mapping[str, str]:

        return {"folder_path": "string"}

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        path: str = requirements["folder_path"]
        duplicate_strategy = requirements.get("duplicate", "ignore")

        target_path = self.create_temp_dir("flatten_")

        flatten_folder(
            src_path=path, target_path=target_path, strategy=duplicate_strategy
        )

        return {"folder_path": target_path}
