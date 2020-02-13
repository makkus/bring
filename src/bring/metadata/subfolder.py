# -*- coding: utf-8 -*-
import os

from bring.metadata import MetadataHandler


class SubfolderMetadataHandler(MetadataHandler):
    def __init__(self, metadata_folder_location: str = ".bring"):

        self._metadata_folder_location = metadata_folder_location

    def _get_metadata(self, target: str):

        if os.path.isabs(self._metadata_folder_location):
            raise NotImplementedError()
        else:
            target_folder = os.path.join(target, self._metadata_folder_location)
        print(target_folder)

    def _write_metadata(self, rel_target_file: str, metadata):
        pass
