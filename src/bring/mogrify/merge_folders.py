# -*- coding: utf-8 -*-
from typing import Any, Mapping, MutableMapping

# from bring.merge_strategy import FolderMerge, MergeStrategy
from bring.mogrify import SimpleMogrifier


class MergeFoldersMogrifier(SimpleMogrifier):
    """Merge multiple folders into a single one, using one of the available merge strategies.

    This mogrifier is used internally, and, for now, can't be used in user-created mogrifier lists.
    """

    _plugin_name: str = "merge_folders"

    _requires: Mapping[str, str] = {"folder_paths": "list", "merge_strategy": "dict?"}

    _provides: Mapping[str, str] = {"folder_path": "string"}

    def get_msg(self) -> str:

        return "merging folder (if multiple source folders)"

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        strategy: MutableMapping[str, Any] = requirements.get(
            "merge_strategy", {"type": "default", "config": {"move_method": "move"}}
        )
        if isinstance(strategy, str):
            strategy = {"type": strategy, "config": {"move_method": "move"}}

        if "config" not in strategy.keys():
            strategy["config"] = {}
        if "move_method" not in strategy["config"].keys():
            strategy["config"]["move_method"] = "copy"

        folder_paths = requirements["folder_paths"]
        if not folder_paths:
            raise Exception("Can't merge directories, no folder_paths provided.")

        target_path = self.create_temp_dir("merge_")

        raise NotImplementedError()
        # merge_strategy = MergeStrategy.create_merge_strategy(
        #     typistry=self._tingistry_obj.typistry, merge_strategy=strategy
        # )
        #
        # merge_obj = FolderMerge(target=target_path, merge_strategy=merge_strategy)
        #
        # await merge_obj.merge_folders(*folder_paths)

        return {"folder_path": target_path}
