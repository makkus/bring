# -*- coding: utf-8 -*-
from bring.merge_strategy import MergeStrategy
from bring.target_folder import TargetFolder


class ReplaceMergeStrategy(MergeStrategy):

    _plugin_name = "replace"

    def merge_source(
        self,
        source_base: str,
        source_file: str,
        target_folder: TargetFolder,
        target_file: str,
    ) -> None:

        pass
        # protected_folders = ["~/.config", "~/Documents", "~/Desktop"]

        # target_path = os.path.relpath(target_folder.path)

        # for protected in protected_folders:
        #     _p = os.path.realpath(os.path.expanduser(protected))
