# -*- coding: utf-8 -*-
import os
import shutil
from typing import Any, Iterable, Mapping, Union

from bring.mogrify import SimpleMogrifier
from bring.utils.paths import find_matches
from frtls.files import ensure_folder


class FileFilterMogrifier(SimpleMogrifier):

    _plugin_name: str = "file_filter"

    def requires(self) -> Mapping[str, str]:

        return {"folder_path": "string", "include": "list"}

    def get_msg(self) -> str:

        return "filtering files"

    def provides(self) -> Mapping[str, str]:

        return {"folder_path": "string"}

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        path: str = requirements["folder_path"]
        include_patterns: Union[str, Iterable[str]] = requirements["include"]

        matches = find_matches(path=path, include_patterns=include_patterns)
        matches = list(matches)

        result = self.create_temp_dir(prefix="file_filter_")

        if not matches:
            return {"folder_path": result}

        for m in matches:
            source = os.path.join(path, m)
            target = os.path.join(result, m)
            parent = os.path.dirname(target)
            ensure_folder(parent)
            shutil.move(source, target)

        return {"folder_path": result}
