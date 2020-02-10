# -*- coding: utf-8 -*-
from abc import ABCMeta, abstractmethod
from typing import Dict


class FileSetFilter(metaclass=ABCMeta):
    @abstractmethod
    def get_file_set(self, folder_path: str) -> Dict[str, str]:

        pass
