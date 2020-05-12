# -*- coding: utf-8 -*-
import collections
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Optional, Union

from anyio import aopen
from bring.defaults import BRING_TEMP_FOLDER_MARKER
from frtls.exceptions import FrklException
from frtls.files import ensure_folder
from frtls.types.typistry import Typistry
from frtls.types.utils import is_instance_or_subclass


if TYPE_CHECKING:
    from bring.merge_strategy import MergeStrategy


class TargetFolder(object):
    def __init__(self, path: Union[Path, str]):

        if isinstance(path, Path):
            path = path.as_posix()

        self._path: str = os.path.abspath(os.path.expanduser(path))
        self._metadata_path: str = os.path.join(self._path, ".bring", "meta.json")
        self._info: Optional[Mapping[str, Any]] = None

    @property
    def path(self) -> str:
        return self._path

    def ensure_exists(self) -> None:

        ensure_folder(self._path)

    def exists(self, rel_path: str):

        path = self.get_full_path(rel_path)

        return os.path.exists(path)

    def get_full_path(self, rel_path):

        path = os.path.join(self.path, rel_path)
        return path

    @property
    async def info(self) -> Mapping[str, Any]:

        if self._info is not None:
            return self._info

        self._info = {}
        if not os.path.exists(self._metadata_path):
            if not os.path.exists(self._path):
                self._info["exists"] = False
            else:
                self._info["exists"] = True

        else:
            self._info["exists"] = True

            async with await aopen(self._metadata_path) as f:
                content = await f.read()

            if content:
                self._info["meta"] = json.loads(content)
            else:
                self._info["meta"] = {}

        return self._info


class BringTarget(object):
    @classmethod
    def create(
        cls,
        typistry: Typistry,
        target: Optional[Union[str, Path, Mapping[str, Any], "BringTarget"]] = None,
    ) -> "BringTarget":

        if target is None or target == BRING_TEMP_FOLDER_MARKER:
            raise NotImplementedError()

        if is_instance_or_subclass(target, BringTarget):
            return target  # type: ignore

        return cls(typistry=typistry, target=target)  # type: ignore

    def __init__(self, typistry: Typistry, target: Union[str, Path, Mapping[str, Any]]):

        from bring.merge_strategy import MergeStrategy

        self._typistry: Typistry = typistry

        if isinstance(target, collections.Mapping):
            strategy = dict(target)
            if "path" not in strategy.keys():
                raise ValueError(
                    f"Can't create BringTarget, no 'path' value provided: {strategy}"
                )
            _target = strategy.pop("path")
        else:
            strategy = {}
            _target = target

        self._target_folder: TargetFolder = TargetFolder(path=_target)
        ms_type = strategy.pop("type", "default")
        pm = self._typistry.get_plugin_manager(MergeStrategy)
        ms_cls = pm.get_plugin(ms_type)
        if ms_cls is None:
            raise FrklException(
                msg="Can't create BringTarget.",
                reason=f"Invalid merge strategy, valid: {', '.join(pm.plugin_names)}",
            )
        self._merge_strategy: "MergeStrategy" = ms_cls(**strategy)

    @property
    def target_folder(self) -> TargetFolder:

        return self._target_folder

    @property
    def merge_strategy(self) -> "MergeStrategy":

        return self._merge_strategy
