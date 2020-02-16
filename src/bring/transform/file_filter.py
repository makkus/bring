# -*- coding: utf-8 -*-
import os
import shutil
from typing import Dict

from frtls.files import ensure_folder

from bring.transform import Transformer


class FileFilterTransformer(Transformer):

    _plugin_name: str = "file_filter"

    def __init__(self, **config):

        super().__init__(**config)

    def get_config_keys(self) -> Dict:

        return {}

    def _transform(self, path: str, transform_config: Dict = None) -> str:

        matches = self.find_matches(path, transform_config=transform_config)

        if not matches:
            return None

        result = self.create_temp_dir()
        for m in matches:
            source = os.path.join(path, m)
            target = os.path.join(result, m)
            parent = os.path.dirname(target)
            ensure_folder(parent)
            shutil.copyfile(source, target)

        return result
