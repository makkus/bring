# -*- coding: utf-8 -*-
import os
import shutil
from typing import Any, Iterable, Mapping, Union

from bring.mogrify import Mogrifier
from frtls.files import ensure_folder
from pathspec import PathSpec, patterns


class FileFilterMogrifier(Mogrifier):

    _plugin_name: str = "file_filter"

    def requires(self) -> Mapping[str, str]:

        return {"folder_path": "string", "include": "list"}

    def get_msg(self) -> str:

        return "filtering files"

    def provides(self) -> Mapping[str, str]:

        return {"folder_path": "string"}

    async def cleanup(self, result: Mapping[str, Any], *value_names, **requirements):

        shutil.rmtree(result["folder_path"], ignore_errors=True)

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        path: str = requirements["folder_path"]
        include_patterns: Union[str, Iterable[str]] = requirements["include"]

        matches = self.find_matches(path, include_patterns=include_patterns)

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

    def find_matches(
        self,
        path: str,
        include_patterns: Union[str, Iterable[str]],
        output_absolute_paths=False,
    ) -> Iterable:

        if isinstance(include_patterns, str):
            _include_patterns: Iterable[str] = [include_patterns]
        else:
            _include_patterns = include_patterns

        path_spec = PathSpec.from_lines(patterns.GitWildMatchPattern, _include_patterns)

        matches = path_spec.match_tree(path)

        if output_absolute_paths:
            matches = (os.path.join(path, m) for m in matches)

        return matches
