# -*- coding: utf-8 -*-
from typing import TYPE_CHECKING, Any, Mapping, Optional, Union

from bring.bring_target import BringTarget
from bring.merge_strategy import LocalFolder
from bring.merge_strategy.explanation import LocalFolderExplanation
from rich.console import Console, ConsoleOptions, RenderResult


if TYPE_CHECKING:
    from bring.bring import Bring


class LocalFolderTarget(BringTarget):

    _plugin_name = "local_folder"

    def __init__(self, bring: "Bring", **input_vars: Any):

        self._target_folder: Optional[LocalFolder] = None

        super().__init__(bring=bring, **input_vars)

    def _invalidate(self):

        self._target_folder = None

    def requires(self) -> Mapping[str, Union[str, Mapping[str, Any]]]:

        return {
            "path": {
                "doc": "the path to the local folder",
                "type": "string",
                "required": False,
            },
            # "merge_strategy": {
            #     "doc": "the merge strategy",
            #     "type": "merge_strategy",
            #     "required": True,
            # }
        }

    def provides(self) -> Mapping[str, Union[str, Mapping[str, Any]]]:

        return {
            "path": {
                "doc": "the path to the local folder",
                "type": "string",
                "required": True,
            }
        }

    @property
    def target_folder(self) -> LocalFolder:

        if self._target_folder is None:
            path = self.current_input(validate=True)["path"]
            self._target_folder = LocalFolder(path)
        return self._target_folder

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:

        yield LocalFolderExplanation(self.target_folder)

    # async def process_result(
    #     self, input: Mapping[str, Any], result: Mapping[str, Any]
    # ) -> Mapping[str, Any]:
    #
    #     folder_path = result["folder_path"]
    #
    #     merge_strategy = {
    #         "type": "bring",
    #         "config": {"move_method": "move", "pkg_metadata": input},
    #     }
    #
    #     folder_merge = FolderMerge(
    #         typistry=self._bring.typistry,
    #         target=self.target_folder,
    #         merge_strategy=merge_strategy,
    #     )
    #     await folder_merge.merge_folders(folder_path)
    #
    #     return {"path": self.target_folder.path}
