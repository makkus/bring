# -*- coding: utf-8 -*-
from typing import Any, Mapping, MutableMapping

from bring.merging import FolderMerge
from bring.mogrify import SimpleMogrifier


class MergeFolderMogrifier(SimpleMogrifier):

    _plugin_name: str = "merge_folders"

    def provides(self) -> Mapping[str, str]:

        return {"folder_path": "string"}

    def requires(self) -> Mapping[str, str]:

        return {"folder_paths": "list", "merge_strategy": "dict?"}

    def get_msg(self) -> str:

        return "merging folder (if multiple source folders)"

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        strategy: MutableMapping[str, Any] = requirements.get(
            "merge_strategy", {"type": "default", "move_method": "move"}
        )
        if isinstance(strategy, str):
            strategy = {"type": strategy, "move_method": "move"}

        if "move_method" not in strategy.keys():
            strategy["move_method"] = "move"

        folder_paths = requirements["folder_paths"]
        if not folder_paths:
            raise Exception("Can't merge directories, no folder_paths provided.")

        target_path = self.create_temp_dir("merge_")

        merge_obj = FolderMerge(
            typistry=self._tingistry_obj.typistry,
            target=target_path,
            merge_strategy=strategy,
        )

        merge_obj.merge_folders(*folder_paths)

        return {"folder_path": target_path}
