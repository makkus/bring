# -*- coding: utf-8 -*-
from typing import Any

from bring.merge_strategy import FileItem, LocalFolderItem, MergeStrategy


class ReplaceMergeStrategy(MergeStrategy):

    _plugin_name = "replace"

    async def merge_source(
        self, source_file: FileItem, target_file: LocalFolderItem
    ) -> Any:

        pass
        # protected_folders = ["~/.config", "~/Documents", "~/Desktop"]

        # target_path = os.path.relpath(target_folder.path)

        # for protected in protected_folders:
        #     _p = os.path.realpath(os.path.expanduser(protected))
