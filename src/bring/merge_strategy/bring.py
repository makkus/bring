# -*- coding: utf-8 -*-
import json
import os
from typing import Any, Mapping

from anyio import aopen
from bring.merge_strategy import LocalFolder, LocalFolderItem, MergeStrategy
from deepdiff import DeepHash
from frtls.exceptions import FrklException
from frtls.files import ensure_folder


class BringMergeStrategy(MergeStrategy):

    _plugin_name = "bring"

    @property
    def pkg_metadata(self) -> Mapping[str, Any]:

        return self.get_config("pkg_metadata")

    @property
    def pkg_metadata_hash(self) -> str:

        if "_pkg_hash" not in self._config.keys():
            pkg_hash = DeepHash(self.pkg_metadata)
            self._config["_pkg_hash"] = pkg_hash[self.pkg_metadata]

        return self.get_config("_pkg_hash")

    def get_pkg_hash_file_path(self, target_folder: LocalFolder):

        full_path = os.path.join(
            target_folder._item_metadata_path,
            "hashes",
            f"{self.pkg_metadata_hash}.json",
        )
        return full_path

    async def ensure_pkg_hash_file(self, target_folder: LocalFolder):

        full_path = self.get_pkg_hash_file_path(target_folder=target_folder)

        if os.path.isfile(full_path):
            return

        md_string = json.dumps(self.pkg_metadata)
        ensure_folder(os.path.dirname(full_path))
        async with await aopen(full_path, "w") as f:
            await f.write(md_string)

    def link_metadata_file(self, target_file: LocalFolderItem, force: bool = False):

        if force and os.path.islink(target_file.metadata_file_path):
            os.unlink(target_file.metadata_file_path)

        ensure_folder(os.path.dirname(target_file.metadata_file_path))
        pkg_hash_files = self.get_pkg_hash_file_path(
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

        await self.ensure_pkg_hash_file(target_folder=target_folder)

    async def write_target_file(
        self, source_file: LocalFolderItem, target_file: LocalFolderItem
    ):

        self._move_or_copy_file(source_file, target_file)
        self.link_metadata_file(target_file=target_file, force=True)

    async def merge_source(
        self, source_file: LocalFolderItem, target_file: LocalFolderItem
    ) -> Any:

        if not target_file.exists:
            await self.write_target_file(
                source_file=source_file, target_file=target_file
            )
            return None

        md = await target_file.get_metadata()

        if md["managed"]:
            await self.write_target_file(
                source_file=source_file, target_file=target_file
            )
            return None

        raise FrklException(
            msg=f"Can't merge/copy file '{target_file.rel_path}'.",
            reason=f"File already exists in target: {target_file.base_folder}",
        )
