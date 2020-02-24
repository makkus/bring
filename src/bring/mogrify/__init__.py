# -*- coding: utf-8 -*-
import tempfile
from abc import ABCMeta, abstractmethod
from typing import Any, Mapping

from bring.defaults import BRING_WORKSPACE_FOLDER
from frtls.strings import from_camel_case


class Mogrifier(metaclass=ABCMeta):
    def __init__(self, name: str, **config: Any) -> None:

        config.pop("type", None)
        self._config = config
        self._merged_config = None

        if not name:
            name = from_camel_case(self.__class__.__name__)
        self._name = name

    @property
    def name(self):
        return self._name

    def create_temp_dir(self, prefix=None):
        if prefix is None:
            prefix = self._name
        tempdir = tempfile.mkdtemp(prefix=f"{prefix}_", dir=BRING_WORKSPACE_FOLDER)
        return tempdir

    def transmogrify(
        self, input_data: Mapping[str, Any], config: Mapping[str, Any] = None
    ) -> Mapping[str, Any]:

        pass

    @abstractmethod
    def _transmogrify(
        self, input_data: Mapping[str, Any], config: Mapping[str, Any]
    ) -> Mapping[str, Any]:

        pass
