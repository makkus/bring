# -*- coding: utf-8 -*-
import os
import stat
from typing import Dict

from bring.transform import Transformer


class SetModeTransformer(Transformer):

    _plugin_name: str = "set_mode"

    def __init__(self, **config):

        super().__init__(**config)

    def get_config_keys(self) -> Dict:

        return {
            "set_executable": self._config,
            "set_readable": None,
            "set_writeable": None,
        }

    def _transform(self, path: str, transform_config: Dict = None) -> str:

        matches = self.find_matches(path, transform_config, output_absolute_paths=True)

        set_executable = transform_config["set_executable"]
        set_readable = transform_config["set_readable"]
        set_writeable = transform_config["set_writeable"]

        for m in matches:
            st = os.stat(m)
            if set_executable is True:
                os.chmod(m, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
            elif set_executable is False:
                raise NotImplementedError()

            if set_readable in [True, False]:
                raise NotImplementedError()
            if set_writeable in [True, False]:
                raise NotImplementedError()

        return path
