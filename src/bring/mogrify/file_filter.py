# -*- coding: utf-8 -*-
from typing import Any, Iterable, Mapping, Union

from bring.mogrify import SimpleMogrifier
from bring.utils.paths import copy_filtered_files


class FileFilterMogrifier(SimpleMogrifier):

    _plugin_name: str = "file_filter"

    def requires(self) -> Mapping[str, str]:

        return {"folder_path": "string", "include": "list", "flatten": "boolean?"}

    def get_msg(self) -> str:

        return "filtering files"

    def provides(self) -> Mapping[str, str]:

        return {"folder_path": "string"}

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        path: str = requirements["folder_path"]
        flatten: bool = requirements.get("flatten", False)
        include_patterns: Union[str, Iterable[str]] = requirements["include"]

        result = self.create_temp_dir(prefix="file_filter_")
        copy_filtered_files(
            orig=path,
            include=include_patterns,
            target=result,
            move_files=True,
            flatten=flatten,
        )

        return {"folder_path": result}
