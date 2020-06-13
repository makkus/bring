# -*- coding: utf-8 -*-
from typing import Any, Iterable, Mapping, Union

from bring.mogrify import SimpleMogrifier
from bring.utils.paths import copy_filtered_files, resolve_include_patterns


class FileFilterMogrifier(SimpleMogrifier):
    """Filters files in a folder using glob patterns.

    Examples:
        - binaries.hugo
        - kubernetes.ingress-nginx
    """

    _plugin_name: str = "file_filter"

    _requires: Mapping[str, str] = {
        "folder_path": "string",
        "include": "list",
        "flatten": "boolean?",
    }
    _provides: Mapping[str, str] = {"folder_path": "string"}

    def get_msg(self) -> str:

        result = "filtering files"
        vals = self.user_input

        if vals.get("include", None):
            _include_patterns = resolve_include_patterns(vals["include"])
            result = result + f" matching: '{', '.join(_include_patterns)}'"

        if vals.get("flatten", None):
            result = result + ", then flatten all files into a single folder"

        return result

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
