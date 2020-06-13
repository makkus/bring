# -*- coding: utf-8 -*-
from typing import Any

from bring.merge_strategy import FileItem, LocalFolderItem, MergeStrategy


class OverwriteMergeStrategy(MergeStrategy):

    _plugin_name = "overwrite"

    async def merge_source(
        self, source_file: FileItem, target_file: LocalFolderItem
    ) -> Any:

        pass

        # source = os.path.join(source_folder, source_file)
        #
        # target_file.unlink()
        #
        # self._move_or_copy_file(source, target_file.full_path)
