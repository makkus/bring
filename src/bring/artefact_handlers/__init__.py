# -*- coding: utf-8 -*-
import logging
import os
import tempfile
from abc import ABCMeta, abstractmethod
from typing import List, Dict, Any

from bring.defaults import BRING_PKG_CACHE
from frtls.files import ensure_folder
from frtls.strings import from_camel_case

log = logging.getLogger("bring")


class ArtefactHandler(metaclass=ABCMeta):
    def get_handler_name(self):
        return from_camel_case(self.__class__.__name__, sep="-")

    @abstractmethod
    async def _provide_artefact_folder(
        self, artefact_path: str, artefact_details: Dict[str, Any]
    ):

        pass

    async def provide_artefact_folder(
        self, artefact_path: str, artefact_details: Dict[str, Any]
    ):

        root = await self._provide_artefact_folder(
            artefact_path=artefact_path, artefact_details=artefact_details
        )

        return root

    @abstractmethod
    def get_supported_artefact_types(self) -> List[str]:
        pass


class SimpleArtefactHandler(ArtefactHandler):
    def __init__(self):
        self._base_dir = os.path.join(
            BRING_PKG_CACHE, "handlers", from_camel_case(self.__class__.__name__)
        )
        ensure_folder(self._base_dir)

    def create_temp_dir(self):

        base = os.path.join(self._base_dir, "temp")
        ensure_folder(base)
        tempdir = tempfile.mkdtemp(dir=base)
        return tempdir
