# -*- coding: utf-8 -*-
import logging
import os
import tempfile
from abc import ABCMeta, abstractmethod
from typing import Any, Dict, List, Tuple

from bring.defaults import BRING_PKG_CACHE
from frtls.exceptions import FrklException
from frtls.files import ensure_folder
from frtls.strings import from_camel_case
from frtls.tasks import SingleTaskAsync, Task


log = logging.getLogger("bring")


class ArtefactHandler(metaclass=ABCMeta):
    def create_temp_dir_path(cls, leaf_folder_name: str):

        handler_base_dir = os.path.join(
            BRING_PKG_CACHE, "handlers", from_camel_case(cls.__name__)
        )
        base = os.path.join(handler_base_dir, "temp")
        ensure_folder(base)
        tempdir = tempfile.mkdtemp(dir=base)
        return os.path.join(tempdir, leaf_folder_name)

    @abstractmethod
    async def _provide_artefact_folder(
        self, target_folder: str, artefact_path: str, artefact_details: Dict[str, Any]
    ) -> None:

        pass

    async def provide_artefact_folder_tasks(
        self, target_folder: str, artefact_path: str, artefact_details: Dict[str, Any]
    ) -> Tuple[str, Task]:

        if os.path.exists(target_folder):
            raise FrklException(
                msg=f"Can't create artefact folder '{target_folder}'.",
                reason="Folder exists.",
            )

        parent = os.path.dirname(target_folder)
        ensure_folder(parent)

        task = SingleTaskAsync(
            self._provide_artefact_folder,
            func_kwargs={
                "target_folder": target_folder,
                "artefact_path": artefact_path,
                "artefact_details": artefact_details,
            },
            name=f"provide version folder '{target_folder}'",
        )

        return target_folder, task

    @abstractmethod
    def _supports(self) -> List[str]:
        pass
