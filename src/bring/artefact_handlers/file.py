# -*- coding: utf-8 -*-
import os
import shutil
from typing import Any, Dict, List

from bring.artefact_handlers import SimpleArtefactHandler


class FileHandler(SimpleArtefactHandler):

    _plugin_name: str = "file"

    def __init__(self):

        super().__init__()

    async def _provide_artefact_folder(
        self, artefact_path: str, artefact_details: Dict[str, Any]
    ):

        temp_dir = self.create_temp_dir()

        target = os.path.join(temp_dir, os.path.basename(artefact_path))

        shutil.copyfile(artefact_path, target)

        return temp_dir

    def _supports(self) -> List[str]:
        return "file"
