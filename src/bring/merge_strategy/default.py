# -*- coding: utf-8 -*-
from typing import Any

from bring.merge_strategy import LocalFolderItem, MergeStrategy


class DefaultMergeStrategy(MergeStrategy):

    _plugin_name = "default"

    async def merge_source(
        self, source_file: LocalFolderItem, target_file: LocalFolderItem
    ) -> Any:

        force = self.get_config("force", False)
        backup = self.get_config("backup", True)

        if target_file.exists:
            if not force:
                return "file already exists, and 'force' not set"
            else:
                if backup:
                    self.backup_file(target_file=target_file)
                    msg = "installed (existing file backed up)"
                else:
                    target_file.unlink()
                    msg = "installed (existing file deleted)"
        else:
            msg = "installed"

        self._move_or_copy_file(source_file, target_file)

        return msg
