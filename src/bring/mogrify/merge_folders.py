# -*- coding: utf-8 -*-
from typing import Any, Mapping

from bring.mogrify import SimpleMogrifier
from bring.utils.merge_folders import FolderMerge


class MergeFolderMogrifier(SimpleMogrifier):

    _plugin_name: str = "merge_folders"

    def provides(self) -> Mapping[str, str]:

        return {"folder_path": "string"}

    def requires(self) -> Mapping[str, str]:

        return {"folder_paths": "list", "merge_strategy": "dict?"}

    def get_msg(self) -> str:

        return "merging folder (if multiple source folders)"

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        strategy: Mapping[str, Any] = requirements.get(
            "merge_strategy", {"type": "default"}
        )
        if isinstance(strategy, str):
            strategy = {"type": strategy}

        folder_paths = requirements["folder_paths"]
        if not folder_paths:
            raise Exception("Can't merge directories, no folder_paths provided.")

        target_path = self.create_temp_dir("merge_")

        merge_obj = FolderMerge(target=target_path, merge_strategy=strategy)

        for source in folder_paths:

            merge_obj.merge_folder(source=source)

        return {"folder_path": target_path}
