# -*- coding: utf-8 -*-
import logging
from typing import Any, Mapping, Optional

from bring.mogrify import SimpleMogrifier
from bring.utils.merge_folders import FolderMerge


log = logging.getLogger("bring")


class MergeIntoMogrifier(SimpleMogrifier):

    _plugin_name: str = "merge_into"

    def provides(self) -> Mapping[str, str]:

        return {"folder_path": "string"}

    def requires(self) -> Mapping[str, str]:

        return {"folder_path": "string", "target": "string", "merge_strategy": "dict?"}

    def get_msg(self) -> Optional[str]:

        return "merging folders"

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        strategy: Mapping[str, Any] = requirements.get(
            "merge_strategy", {"type": "default"}
        )
        if isinstance(strategy, str):
            strategy = {"type": strategy}

        source = requirements["folder_path"]
        if not source:
            raise Exception("Can't merge directories, no source folder provided.")

        target_path = requirements.get("target", None)
        if target_path is None:
            target_path = self.create_temp_dir("merge_into_")

        merge_obj = FolderMerge(target=target_path, merge_strategy=strategy)

        merge_obj.merge_folder(source=source)

        return {"folder_path": target_path}
