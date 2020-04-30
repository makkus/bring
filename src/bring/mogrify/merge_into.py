# -*- coding: utf-8 -*-
import logging
from typing import Any, Mapping, MutableMapping, Optional, Union

from bring.merging import FolderMerge
from bring.mogrify import SimpleMogrifier


log = logging.getLogger("bring")


class MergeIntoMogrifier(SimpleMogrifier):

    _plugin_name: str = "merge_into"

    def provides(self) -> Mapping[str, str]:

        return {"folder_path": "string"}

    def requires(self) -> Mapping[str, str]:

        return {"folder_path": "string", "target": "string", "merge_strategy": "dict?"}

    def get_msg(self) -> str:

        vals = self.input_values
        target = vals.get("target", "[dynamic]")
        strategy = self.explode_strategy(vals.get("merge_strategy", None))

        result = f"merging everything into: {target} (strategy: {strategy['type']})"
        return result

    def explode_strategy(
        self, strategy: Optional[Union[str, MutableMapping[str, Any]]] = None
    ):

        if strategy is None:
            strategy = {"type": "default", "move_method": "move"}

        if isinstance(strategy, str):
            strategy = {"type": strategy, "move_method": "move"}

        if "move_method" not in strategy.keys():
            strategy["move_method"] = "move"

        return strategy

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        strategy = requirements.get("merge_strategy", None)
        strategy = self.explode_strategy(strategy)

        source = requirements["folder_path"]
        if not source:
            raise Exception("Can't merge directories, no source folder provided.")

        target_path = requirements.get("target", None)
        if target_path is None:
            target_path = self.create_temp_dir("merge_into_")

        merge_obj = FolderMerge(
            typistry=self._tingistry_obj.typistry,
            target=target_path,
            merge_strategy=strategy,
        )

        merge_obj.merge_folders(source)

        return {"folder_path": target_path}
