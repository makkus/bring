# -*- coding: utf-8 -*-
import collections
import os
import shutil
from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional, Union

from bring.target_folder import TargetFolder
from frtls.defaults import DEFAULT_EXCLUDE_DIRS
from frtls.exceptions import FrklException
from frtls.files import ensure_folder
from frtls.types.typistry import Typistry
from frtls.types.utils import is_instance_or_subclass


class MergeStrategy(metaclass=ABCMeta):

    _plugin_type = "instance"

    def __init__(self, **config):

        self._config: Mapping[str, Any] = config

    @property
    def exclude_dirs(self) -> Iterable[str]:

        exclude_dirs = self._config.get("exclude_dirs", DEFAULT_EXCLUDE_DIRS)
        return exclude_dirs

    def get_config(self, key: str, default: Any = None) -> Any:

        return self._config.get(key, default)

    @property
    def flatten(self) -> bool:

        flatten = self._config.get("flatten", False)
        return flatten

    @property
    def move_method(self) -> str:

        method = self._config.get("move_method", "copy")
        return method

    def move(self, source: str, target: str) -> None:

        ensure_folder(os.path.dirname(target))

        if self.move_method == "copy":
            shutil.copy2(source, target)
        elif self.move_method == "move":
            shutil.move(source, target)
        else:
            raise FrklException(
                f"Can't move file '{source}', invalid move method '{self.move_method}'. Allowed: {', '.join(['move', 'copy'])}"
            )

    def merge(
        self, target_folder: Union[TargetFolder, str, Path], *sources: Union[str, Path]
    ):

        if isinstance(target_folder, (str, Path)):
            _target_folder: TargetFolder = TargetFolder(target_folder)
        else:
            _target_folder = target_folder

        _sources: List[str] = []

        for source in sources:
            if isinstance(source, str):
                _source = os.path.realpath(os.path.expanduser(source))
            elif isinstance(source, Path):
                _source = source.resolve().as_posix()
            else:
                raise TypeError(
                    f"Invalid type '{type(source)}' for source path: {source}"
                )

            if not os.path.exists(_source):
                raise ValueError(
                    f"Can't merge into folder '{_target_folder.path}': source '{_source}' does not exist."
                )
            _sources.append(_source)

        for source in _sources:
            for root, dirnames, filenames in os.walk(source, topdown=True):

                if self.exclude_dirs:
                    dirnames[:] = [d for d in dirnames if d not in self.exclude_dirs]

                for filename in filenames:

                    full_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(full_path, source)

                    if self.flatten:
                        target_file = filename
                    else:
                        target_file = rel_path

                    self.merge_source(
                        source_base=source,
                        source_file=rel_path,
                        target_folder=_target_folder,
                        target_file=target_file,
                    )

    @abstractmethod
    def merge_source(
        self,
        source_base: str,
        source_file: str,
        target_folder: TargetFolder,
        target_file: str,
    ) -> None:
        pass


class FolderMerge(object):
    def __init__(
        self,
        typistry: Typistry,
        target: Union[str, Path],
        merge_strategy: Optional[Union[str, Mapping[str, Any], MergeStrategy]] = None,
        flatten: bool = False,
    ):

        self._typistry = typistry
        if merge_strategy is None:
            merge_strategy = "default"

        # if isinstance(target, str):
        #     _target = os.path.realpath(os.path.expanduser(target))
        # elif isinstance(target, Path):
        #     _target = target.resolve().as_posix()
        # else:
        #     raise TypeError(f"Invalid type '{type(target)}' for target path: {target}")

        self._target: TargetFolder = TargetFolder(target)

        if isinstance(merge_strategy, str):
            merge_strategy = {"type": merge_strategy}
        if isinstance(merge_strategy, collections.Mapping):
            ms_config = dict(merge_strategy)
            ms_type = ms_config.pop("type", "default")
            pm = self._typistry.get_plugin_manager(MergeStrategy)
            ms_cls = pm.get_plugin(ms_type)
            if ms_cls is None:
                raise FrklException(
                    msg=f"Can't merge into folder '{self._target.path}' using merge strategy '{ms_type}'.",
                    reason=f"Invalid merge strategy, valid: {', '.join(pm.plugin_names)}",
                )
            self._merge_strategy = ms_cls(**ms_config)
        elif is_instance_or_subclass(merge_strategy, MergeStrategy):
            self._merge_strategy = merge_strategy  # type: ignore
        else:
            raise TypeError(f"Invalid merge strategy type: {type(merge_strategy)}")

        self._flatten: bool = flatten

    @property
    def merge_strategy(self) -> MergeStrategy:

        return self._merge_strategy

    @property
    def target(self) -> TargetFolder:
        return self._target

    def merge_folders(self, *sources: Union[str, Path]) -> None:

        self._target.ensure_exists()

        self.merge_strategy.merge(self._target, *sources)
