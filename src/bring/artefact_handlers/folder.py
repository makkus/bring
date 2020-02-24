# -*- coding: utf-8 -*-
import shutil
from typing import Any, Dict, List

from bring.artefact_handlers import ArtefactHandler


class FolderHandler(ArtefactHandler):

    _plugin_name: str = "folder"

    async def _provide_artefact_folder(
        self, target_path: str, artefact_path: str, artefact_details: Dict[str, Any]
    ) -> None:

        shutil.copy2(artefact_path, target_path)

    def _supports(self) -> List[str]:
        return "folder"
