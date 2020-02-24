# -*- coding: utf-8 -*-
import os
import shutil
from typing import Any, Dict, List

from bring.artefact_handlers import ArtefactHandler
from frtls.files import ensure_folder


class FileHandler(ArtefactHandler):

    _plugin_name: str = "file"

    async def _provide_artefact_folder(
        self, target_folder: str, artefact_path: str, artefact_details: Dict[str, Any]
    ):

        ensure_folder(target_folder)

        target = os.path.join(target_folder, os.path.basename(artefact_path))

        shutil.copyfile(artefact_path, target)

    def _supports(self) -> List[str]:
        return "file"
