# -*- coding: utf-8 -*-
from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import Union


class MetadataHandler(metaclass=ABCMeta):
    def get_metadata(self, target: Union[str, Path]):

        if isinstance(target, Path):
            target = target.as_posix()

        return self._get_metadata(target)

    @abstractmethod
    def _get_metadata(self, target: str):
        pass
