# -*- coding: utf-8 -*-
import os
import shutil
from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping, Optional, Union

from bring.mogrify import SimpleMogrifier
from bring.utils.pkg_spec import PATH_KEY, PkgSpec
from frkl.common.exceptions import FrklException
from frkl.common.filesystem import ensure_folder
from frkl.targets.local_folder import LocalFolder, log
from frkl.targets.target import MetadataFileItem, TargetItem


# from bring.merge_strategy import FolderMerge, MergeStrategy


class PkgContentLocalFolder(LocalFolder):
    def __init__(self, path: Union[str, Path], pkg_spec: Any):

        self._pkg_spec_raw = pkg_spec
        self._pkg_spec: PkgSpec = PkgSpec.create(self._pkg_spec_raw)

        self._merged_items: MutableMapping[str, TargetItem] = {}

        super().__init__(path=path)

    @property
    def pkg_spec(self) -> PkgSpec:

        return self._pkg_spec

    async def _merge_item(
        self,
        item_id: str,
        item: Any,
        item_metadata: Mapping[str, Any],
        merge_config: Mapping[str, Any],
    ) -> Optional[MutableMapping[str, Any]]:

        item_matches = self.pkg_spec.get_item_details(item_id)

        for item_details in item_matches:
            if not item_details:

                log.debug(f"Ignoring file item: {item_id}")
                return None

            target_id = item_details[PATH_KEY]

            if self.pkg_spec.flatten:
                target_path = os.path.join(self.path, os.path.basename(target_id))
            else:
                target_path = os.path.join(self.path, target_id)

            if self.pkg_spec.single_file:
                childs = os.listdir(self.path)
                if childs:
                    raise FrklException(
                        msg=f"Can't merge item '{item_id}'.",
                        reason=f"Package is marked as single file, and target path '{self.path}' already contains a child.",
                    )

            ensure_folder(os.path.dirname(target_path))

            move_method = merge_config.get("move_method", "copy")
            if move_method == "move":
                shutil.move(item, target_path)
            elif move_method == "copy":
                shutil.copy2(item, target_path)
            else:
                raise ValueError(f"Invalid 'move_method' value: {move_method}")

            if "mode" in item_details.keys():
                mode_value = item_details["mode"]
                if not isinstance(mode_value, str):
                    mode_value = str(mode_value)

                mode = int(mode_value, base=8)
                os.chmod(target_path, mode)

            self._merged_items[target_path] = MetadataFileItem(
                id=target_path, parent=self, metadata=item_metadata
            )

        return {"msg": "installed"}

    async def _get_items(self, *item_ids: str) -> Mapping[str, Optional[TargetItem]]:

        return self._merged_items

    async def _get_managed_item_ids(self) -> Iterable[str]:

        return self._merged_items.keys()


class FolderContentMogrifier(SimpleMogrifier):
    """Merge multiple folders into a single one, using one of the available merge strategies.

    This mogrifier is used internally, and, for now, can't be used in user-created mogrifier lists.
    """

    _plugin_name: str = "transform_folder"

    _requires: Mapping[str, str] = {
        "folder_path": "list",
        "files": "list?",
        "pkg_vars": "dict?",
        "pkg_spec": "dict?",
    }

    _provides: Mapping[str, str] = {"folder_path": "string", "files": "list"}

    def get_msg(self) -> str:

        return "validating package content"

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        target_path = self.create_temp_dir("pkg_")
        folder_path = requirements["folder_path"]

        pkg_spec = requirements.get("pkg_spec", None)
        pkg_vars = requirements["pkg_vars"]

        folder = PkgContentLocalFolder(path=target_path, pkg_spec=pkg_spec)

        await folder.merge_folders(folder_path, item_metadata=pkg_vars)

        return {"folder_path": target_path, "target": folder}
