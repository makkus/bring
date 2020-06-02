# -*- coding: utf-8 -*-
import logging
from typing import Any, Mapping

from bring.defaults import BRING_TEMP_FOLDER_MARKER
from bring.merge_strategy import FolderMerge, LocalFolder, explode_merge_strategy
from bring.mogrify import SimpleMogrifier


log = logging.getLogger("bring")


class MergeIntoMogrifier(SimpleMogrifier):

    _plugin_name: str = "merge_into"

    _requires = {
        "target": "string?",
        "merge_strategy": {"type": "dict"},
        "folder_path": "string",
    }

    _provides = {"folder_path": "string", "merge_result": "dict"}

    # async def check_status(self, **user_input: Any) -> bool:
    #
    #     target_path = self.user_input.get("target", None)
    #     if not target_path:
    #         return False
    #
    #     if not os.path.exists(target_path):
    #         return False
    #
    #     # bring_target = BringTarget(typistry=self._tingistry_obj.typistry, target=target_path)

    def get_msg(self) -> str:

        vals = self.user_input
        target = vals.get("target", "[dynamic]")
        strategy = explode_merge_strategy(
            vals.get("merge_strategy", None), default_move_method="move"
        )

        target_auto_gen = vals.get("target_path_autogenerated", False)

        if target_auto_gen:
            result = "merging everything into a temporary folder"
        else:
            result = f"merging everything into: {target} (strategy: {strategy['type']})"
        return result

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        strategy = requirements.get("merge_strategy", None)
        strategy = explode_merge_strategy(strategy, default_move_method="move")

        source = requirements["folder_path"]
        if not source:
            raise Exception("Can't merge directories, no source folder provided.")

        target_path = requirements.get("target", None)
        if target_path is None or target_path == BRING_TEMP_FOLDER_MARKER:
            target_path = self.create_temp_dir("merge_into_")

        use_global_metadata = None
        metadata_folder = None

        target = LocalFolder(
            path=target_path,
            use_global_metadata=use_global_metadata,
            metadata_folder=metadata_folder,
        )

        merge_obj = FolderMerge(
            typistry=self._tingistry_obj.typistry,
            target=target,
            merge_strategy=strategy,
        )

        merge_result = await merge_obj.merge_folders(source)

        return {"folder_path": target_path, "merge_result": merge_result}
