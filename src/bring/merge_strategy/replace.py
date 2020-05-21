# -*- coding: utf-8 -*-
from bring.merge_strategy import LocalFolderItem, MergeStrategy


class ReplaceMergeStrategy(MergeStrategy):

    _plugin_name = "replace"

    async def merge_source(
        self, source_file: LocalFolderItem, target_file: LocalFolderItem
    ) -> None:

        pass
        # protected_folders = ["~/.config", "~/Documents", "~/Desktop"]

        # target_path = os.path.relpath(target_folder.path)

        # for protected in protected_folders:
        #     _p = os.path.realpath(os.path.expanduser(protected))
