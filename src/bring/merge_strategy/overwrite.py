# -*- coding: utf-8 -*-
import os

from bring.merge_strategy import MergeStrategy
from bring.target_folder import TargetFolder


class OverwriteMergeStrategy(MergeStrategy):

    _plugin_name = "overwrite"

    def merge_source(
        self,
        source_base: str,
        source_file: str,
        target_folder: TargetFolder,
        target_file: str,
    ) -> None:

        source = os.path.join(source_base, source_file)
        target = target_folder.get_full_path(target_file)

        if os.path.exists(target):
            os.unlink(target)

        self.move(source, target)
