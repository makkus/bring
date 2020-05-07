# -*- coding: utf-8 -*-
import os
import stat
from typing import Any, Mapping

from bring.mogrify import SimpleMogrifier
from bring.utils.paths import find_matches


class SetModeMogrifier(SimpleMogrifier):

    _plugin_name: str = "set_mode"
    _requires: Mapping[str, str] = {
        "folder_path": "string",
        "set_executable": "boolean?",
        "set_readable": "boolean?",
        "set_writeable": "boolean?",
        "include": "list?",
    }
    _provides: Mapping[str, str] = {"folder_path": "string"}

    def get_msg(self) -> str:

        return "setting file mode"

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        path = requirements["folder_path"]
        include_pattern = requirements.get("include", ["*", ".*"])
        matches = find_matches(
            path, include_patterns=include_pattern, output_absolute_paths=True
        )

        set_executable = requirements.get("set_executable", None)
        set_readable = requirements.get("set_readable", None)
        set_writeable = requirements.get("set_writeable", None)

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

        return {"folder_path": path}
