# -*- coding: utf-8 -*-
import os
from typing import Iterable, Optional, Union

from pathspec import PathSpec, patterns


def find_matches(
    path: str,
    include_patterns: Optional[Union[str, Iterable[str]]] = None,
    output_absolute_paths=False,
) -> Iterable:

    if not include_patterns:
        _include_patterns: Iterable[str] = ["*", ".*"]
    elif isinstance(include_patterns, str):
        _include_patterns = [include_patterns]
    else:
        _include_patterns = include_patterns

    path_spec = PathSpec.from_lines(patterns.GitWildMatchPattern, _include_patterns)

    matches = path_spec.match_tree(path)

    if output_absolute_paths:
        matches = (os.path.join(path, m) for m in matches)

    return matches
