# -*- coding: utf-8 -*-
import os
import shutil
import tempfile
from typing import Iterable, Optional, Union

from frtls.files import ensure_folder
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


def copy_filtered_files(
    orig: str,
    include: Union[str, Iterable[str]],
    target: Optional[str] = None,
    move_files: bool = False,
) -> str:

    matches = find_matches(path=orig, include_patterns=include)
    matches = list(matches)

    if target is None:
        target = tempfile.mkdtemp(prefix="file_filter_")
    else:
        ensure_folder(target)

    if not matches:
        return target

    for m in matches:
        source_file = os.path.join(orig, m)
        target_file = os.path.join(target, m)
        parent = os.path.dirname(target_file)
        ensure_folder(parent)
        if move_files:
            shutil.move(source_file, target_file)
        else:
            shutil.copy2(source_file, target_file)

    return target
