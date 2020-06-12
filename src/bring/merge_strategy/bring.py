# -*- coding: utf-8 -*-
import json
import logging
import os
import shutil
import time
from typing import Any, Mapping

from anyio import aopen
from bring.defaults import BRING_BACKUP_FOLDER
from bring.merge_strategy import LocalFolder, LocalFolderItem, MergeStrategy
from deepdiff import DeepHash
from frtls.exceptions import FrklException
from frtls.files import ensure_folder


log = logging.getLogger("bring")


class BringMergeStrategy(MergeStrategy):

    _plugin_name = "bring"

    @property
    def item_metadata(self) -> Mapping[str, Any]:

        return self.get_config("item_metadata")

    @property
    def item_metadata_hash(self) -> str:

        if "_item_hash" not in self._config.keys():

            hashes = DeepHash(self.item_metadata)

            h = hashes[self.item_metadata]

            self._config["_item_hash"] = h

        return self.get_config("_item_hash")

    def get_item_hash_file_path(self, target_folder: LocalFolder):

        full_path = os.path.join(
            target_folder._item_metadata_path,
            "hashes",
            f"{self.item_metadata_hash}.json",
        )
        return full_path

    async def ensure_item_hash_file(self, target_folder: LocalFolder):

        full_path = self.get_item_hash_file_path(target_folder=target_folder)

        if os.path.isfile(full_path):
            return

        md_string = json.dumps(self.item_metadata)
        ensure_folder(os.path.dirname(full_path))
        async with await aopen(full_path, "w") as f:
            await f.write(md_string)

    def link_metadata_file(self, target_file: LocalFolderItem, force: bool = False):

        if force and os.path.islink(target_file.metadata_file_path):
            os.unlink(target_file.metadata_file_path)

        ensure_folder(os.path.dirname(target_file.metadata_file_path))
        pkg_hash_files = self.get_item_hash_file_path(
            target_folder=target_file.base_folder
        )
        mirror_link = target_file.metadata_file_path
        rel_path = os.path.relpath(pkg_hash_files, os.path.dirname(mirror_link))
        os.symlink(rel_path, mirror_link)

    async def pre_merge_hook(
        self,
        target_folder: LocalFolder,
        merge_map: Mapping[LocalFolderItem, LocalFolderItem],
    ) -> None:

        await self.ensure_item_hash_file(target_folder=target_folder)

    async def write_target_file(
        self, source_file: LocalFolderItem, target_file: LocalFolderItem
    ):

        self._move_or_copy_file(source_file, target_file)
        self.link_metadata_file(target_file=target_file, force=True)

    async def merge_source(
        self, source_file: LocalFolderItem, target_file: LocalFolderItem
    ) -> Any:

        force = self.get_config("force", False)
        update = self.get_config("update", False)

        backup = self.get_config("backup", True)

        if not target_file.exists:
            await self.write_target_file(
                source_file=source_file, target_file=target_file
            )
            return "installed"

        md = await target_file.get_metadata()

        if md["managed"]:
            if not update and not force:
                return "file already exists/update not set"

            await self.write_target_file(
                source_file=source_file, target_file=target_file
            )
            return "updated"

        if not force:
            return FrklException(
                msg=f"Can't merge/copy file '{target_file.rel_path}'.",
                reason=f"File already exists in target and 'force' not set: {target_file.base_folder}",
            )

        if backup:
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            ensure_folder(BRING_BACKUP_FOLDER)
            backup_file = f"{BRING_BACKUP_FOLDER}{os.path.sep}{target_file.file_name}.{timestamp}.bak"
            shutil.move(target_file.full_path, backup_file)
            log.debug(f"Backed up file '{target_file.rel_path}' to: {backup_file}")
        else:
            target_file.unlink()
        await self.write_target_file(source_file=source_file, target_file=target_file)

        return "force-updated"
