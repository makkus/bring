# -*- coding: utf-8 -*-
import os

from bring.merge_strategy import MergeStrategy
from bring.target_folder import TargetFolder
from frtls.exceptions import FrklException


class DefaultMergeStrategy(MergeStrategy):

    _plugin_name = "default"

    def merge_source(
        self,
        source_base: str,
        source_file: str,
        target_folder: TargetFolder,
        target_file: str,
    ) -> None:

        target_folder.ensure_exists()

        raise_exception = False
        if target_folder.exists(target_file):
            if raise_exception:
                raise FrklException(
                    msg=f"Can't merge/copy file '{target_folder}'.",
                    reason=f"File already exists in target: {target_file}",
                )
            else:
                return

        source = os.path.join(source_base, source_file)
        target = target_folder.get_full_path(target_file)

        self.move(source, target)
