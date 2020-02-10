# -*- coding: utf-8 -*-
import os
from typing import List, Dict

from pathspec import PathSpec, patterns

from bring.file_sets import FileSetFilter

DEFAULT_PATTERNS = ["!.git", "*"]
DEFAULT_ALL_PATTERNS = ["*", ".*"]


class DefaultFileSetFilter(FileSetFilter):
    def __init__(self, patterns: List[str]):

        if isinstance(patterns, str):
            patterns = patterns
        self._patterns = patterns
        self._path_spec: PathSpec = None

    @property
    def path_spec(self) -> PathSpec:

        if self._path_spec is not None:
            return self._path_spec

        self._path_spec = PathSpec.from_lines(
            patterns.GitWildMatchPattern, self._patterns
        )
        return self._path_spec

    def get_file_set(self, folder_path) -> Dict[str, str]:

        matches = self.path_spec.match_tree(folder_path)
        result = {}
        for m in matches:
            result[m] = os.path.join(folder_path, m)

        return result


DEFAULT_FILTER = DefaultFileSetFilter(DEFAULT_PATTERNS)
DEFAULT_ALL_FILTER = DefaultFileSetFilter(DEFAULT_ALL_PATTERNS)
