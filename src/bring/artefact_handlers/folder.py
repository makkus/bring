# -*- coding: utf-8 -*-
from typing import List, Dict, Any

from bring.artefact_handlers import SimpleArtefactHandler


class FolderHandler(SimpleArtefactHandler):
    def __init__(self):
        super().__init__()

    async def _provide_artefact_folder(
        self, artefact_path: str, artefact_details: Dict[str, Any]
    ):

        return artefact_path

    def get_supported_artefact_types(self) -> List[str]:
        return "folder"
