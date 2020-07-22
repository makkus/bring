# -*- coding: utf-8 -*-
import logging
import os
import shutil
import tempfile
from typing import Any, Iterable, Mapping, Optional, Union

from frkl.common.filesystem import ensure_folder
from pathspec import PathSpec, patterns


log = logging.getLogger("bring")


def resolve_include_patterns(include_patterns: Optional[Union[str, Iterable[str]]]):

    if not include_patterns:
        _include_patterns: Iterable[str] = ["*", ".*"]
    elif isinstance(include_patterns, str):
        _include_patterns = [include_patterns]
    else:
        _include_patterns = include_patterns

    return _include_patterns


def find_matches(
    path: str,
    include_patterns: Optional[Union[str, Iterable[str]]] = None,
    output_absolute_paths=False,
) -> Iterable:

    _include_patterns = resolve_include_patterns(include_patterns)

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
    flatten: bool = False,
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
        if flatten:
            target_file = os.path.join(target, os.path.basename(m))
        else:
            target_file = os.path.join(target, m)
        parent = os.path.dirname(target_file)
        ensure_folder(parent)
        if move_files:
            shutil.move(source_file, target_file)
        else:
            shutil.copy2(source_file, target_file)

    return target


def flatten_folder(
    src_path: str,
    target_path: str,
    strategy: Optional[Union[str, Mapping[str, Any]]] = None,
):

    all_files = find_matches(src_path, output_absolute_paths=True)
    for f in all_files:
        target = os.path.join(target_path, os.path.basename(f))
        if os.path.exists(target):
            if strategy == "ignore":
                log.info(f"Duplicate file '{os.path.basename(target)}', ignoring...")
                continue
            else:
                raise NotImplementedError()
        shutil.move(f, target)
