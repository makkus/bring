# -*- coding: utf-8 -*-
import os
import shutil
import tempfile
from typing import List, Any, Dict

from bring.artefact_handlers import SimpleArtefactHandler
from frtls.exceptions import FrklException


class ArchiveHandler(SimpleArtefactHandler):
    def __init__(self):

        super().__init__()

    def get_supported_artefact_types(self) -> List[str]:

        return ["archive"]

    def create_temp_dir(self):
        tempdir = tempfile.mkdtemp(dir=self._base_dir)
        return tempdir

    async def _provide_artefact_folder(
        self, artefact_path: str, artefact_details: Dict[str, Any]
    ):

        tempdir = self.create_temp_dir()

        shutil.unpack_archive(artefact_path, tempdir)

        if artefact_details.get("remove_root", False):
            childs = os.listdir(tempdir)
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

            root = os.path.join(tempdir, childs[0])
            if not os.path.isdir(root):
                raise FrklException(
                    msg="Can't remove archive root.",
                    reason=f"Not a folder: {childs[0]}",
                )

        else:
            root = tempdir

        return root
