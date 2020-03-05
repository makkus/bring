# -*- coding: utf-8 -*-
import os
import shutil
from pathlib import Path
from typing import Any, Mapping, Union

from frtls.defaults import DEFAULT_EXCLUDE_DIRS
from frtls.exceptions import FrklException
from frtls.files import ensure_folder


class FolderMerge(object):
    def __init__(
        self,
        target: Union[str, Path],
        merge_strategy: Union[str, Mapping[str, Any]] = "default",
    ):

        if isinstance(target, str):
            _target = os.path.realpath(os.path.expanduser(target))
        elif isinstance(target, Path):
            _target = target.resolve().as_posix()
        else:
            raise TypeError(f"Invalid type '{type(target)}' for target path: {target}")

        self._target: str = _target
        ensure_folder(self._target)
        if isinstance(merge_strategy, str):
            merge_strategy = {"type": merge_strategy}
        self._merge_strategy: Mapping[str, Any] = merge_strategy

    @property
    def target(self):
        return self._target

    def merge_folder(self, source: Union[str, Path]):

        if isinstance(source, str):
            source = Path(os.path.realpath(os.path.expanduser(source)))
        elif isinstance(source, Path):
            source = source.resolve().as_posix()
        else:
            raise TypeError(f"Invalid type '{type(source)}' for source path: {source}")

        exclude_dirs = self._merge_strategy.get("exclude_dirs", DEFAULT_EXCLUDE_DIRS)

        strategy_type = self._merge_strategy["type"]
        if not hasattr(self, f"merge_{strategy_type}"):
            raise Exception(f"No '{strategy_type}' merge strategy implemented.")

        func = getattr(self, f"merge_{strategy_type}")

        for root, dirnames, filenames in os.walk(source, topdown=True):

            if exclude_dirs:
                dirnames[:] = [d for d in dirnames if d not in exclude_dirs]

            for filename in filenames:

                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, source)

                func(source, rel_path)

    def merge_default(self, source_base: str, rel_path: str):

        target = os.path.join(self._target, rel_path)
        if os.path.exists(target):
            raise FrklException(
                msg=f"Can't merge/copy file '{rel_path}'.",
                reason=f"File already exists in target: {self._target}",
            )

        source = os.path.join(source_base, rel_path)

        ensure_folder(os.path.dirname(target))
        shutil.move(source, target)

    def merge_overwrite(self, source_base: str, rel_path: str):

        target = os.path.join(self._target, rel_path)
        if os.path.exists(target):
            os.unlink(target)

        source = os.path.join(source_base, rel_path)

        ensure_folder(os.path.dirname(target))
        shutil.move(source, target)
