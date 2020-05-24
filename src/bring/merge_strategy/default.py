# -*- coding: utf-8 -*-
from bring.merge_strategy import LocalFolderItem, MergeStrategy
from frtls.exceptions import FrklException


class DefaultMergeStrategy(MergeStrategy):

    _plugin_name = "default"

    async def merge_source(
        self, source_file: LocalFolderItem, target_file: LocalFolderItem
    ) -> None:

        raise_exception = False
        if target_file.exists:
            if raise_exception:
                raise FrklException(
                    msg=f"Can't merge/copy file '{target_file.rel_path}'.",
                    reason=f"File already exists in target: {target_file.base_folder}",
                )
            else:
                return

        self._move_or_copy_file(source_file, target_file)
