# -*- coding: utf-8 -*-
from typing import Any, Iterable, Mapping, Union

from bring.mogrify import SimpleMogrifier
from bring.utils.paths import copy_filtered_files


class FileFilterMogrifier(SimpleMogrifier):
    """Filters files in a folder using glob patterns.

    Examples:
        - binaries.hugo
        - kube-install-manifests.ingress-nginx
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
        vals = self.input_values

        if vals.get("include", None):
            result = result + f" matching: {', '.join(vals['include'])}"

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
