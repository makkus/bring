# -*- coding: utf-8 -*-
import os
import shutil
from typing import Any, Dict, List

from bring.artefact_handlers import ArtefactHandler
from frtls.exceptions import FrklException


class ArchiveHandler(ArtefactHandler):

    _plugin_name: str = "archive"

    def _supports(self) -> List[str]:

        return ["archive"]

    async def _provide_artefact_folder(
        self, target_folder: str, artefact_path: str, artefact_details: Dict[str, Any]
    ) -> None:

        base_temp = os.path.dirname(target_folder)
        extract_folder = os.path.join(base_temp, "extract")
        shutil.unpack_archive(artefact_path, extract_folder)

        if "remove_root" in artefact_details.keys():
            remove_root = artefact_details["remove_root"]
        else:
            childs = os.listdir(extract_folder)
            if len(childs) == 1 and os.path.isdir(
                os.path.join(extract_folder, childs[0])
            ):
                remove_root = True
            else:
                remove_root = False

        if remove_root:
            childs = os.listdir(extract_folder)
            if len(childs) == 0:
                raise FrklException(
                    msg="Can't remove archive subfolder.",
                    reason=f"No root file/folder for extracted archive: {artefact_path}",
                )
            elif len(childs) > 1:
                raise FrklException(
                    msg="Can't remove archive subfolder.",
                    reason=f"More than one root files/folders: {', '.join(childs)}",
                )

            root = os.path.join(extract_folder, childs[0])
            if not os.path.isdir(root):
                raise FrklException(
                    msg="Can't remove archive root.",
                    reason=f"Not a folder: {childs[0]}",
                )
        else:
            root = extract_folder

        shutil.move(root, target_folder)
