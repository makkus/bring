# -*- coding: utf-8 -*-
import logging
import os
import shutil
from typing import Any, Mapping

from bring.mogrify import Mogrifier
from bring.utils.paths import find_matches
from frtls.files import ensure_folder


log = logging.getLogger("bring")


class FlattenFolderMogrifier(Mogrifier):

    _plugin_name: str = "flatten"

    def requires(self) -> Mapping[str, str]:

        return {"folder_path": "string", "duplicate": "string?"}

    def get_msg(self) -> str:

        return "flatten folder"

    def provides(self) -> Mapping[str, str]:

        return {"folder_path": "string"}

    async def cleanup(self, result: Mapping[str, Any], *value_names, **requirements):

        shutil.rmtree(result["folder_path"])

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        path: str = requirements["folder_path"]
        duplicate_strategy = requirements.get("duplicate", "ignore")

        target_path = self.create_temp_dir("flatten_")

        all_files = find_matches(path, output_absolute_paths=True)
        ensure_folder(target_path)
        for f in all_files:
            target = os.path.join(target_path, os.path.basename(f))
            if os.path.exists(target):
                if duplicate_strategy == "ignore":
                    log.info(
                        f"Duplicate file '{os.path.basename(target)}', ignoring..."
                    )
                    continue
                else:
                    raise NotImplementedError()
            shutil.move(f, target)

        return {"folder_path": target_path}
