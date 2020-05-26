# -*- coding: utf-8 -*-
import collections
import copy
import json
import os
import shutil
from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Union

from anyio import aopen, create_task_group
from bring.defaults import (
    BRING_GLOBAL_METADATA_FOLDER,
    BRING_ITEM_METADATA_FOLDER_NAME,
    BRING_METADATA_FILE_NAME,
    BRING_METADATA_FOLDER_NAME,
)
from frtls.args.arg import DerivedArg
from frtls.cli.vars import DictType
from frtls.defaults import DEFAULT_EXCLUDE_DIRS
from frtls.exceptions import FrklException
from frtls.files import ensure_folder
from frtls.types.typistry import Typistry
from frtls.types.utils import is_instance_or_subclass


def explode_merge_strategy(
    strategy: Optional[Union[str, MutableMapping[str, Any]]] = None,
    default_move_method: str = "copy",
):

    if not strategy:
        strategy = {"type": "default", "config": {"move_method": default_move_method}}

    if isinstance(strategy, str):
        strategy = {"type": strategy, "config": {"move_method": default_move_method}}

    if "config" not in strategy.keys():
        strategy["config"] = {}

    if "move_method" not in strategy["config"].keys():
        strategy["config"]["move_method"] = default_move_method

    return strategy


class LocalFolder(object):
    def __init__(
        self,
        path: Union[Path, str],
        metadata_folder: Optional[str] = None,
        use_global_metadata: Optional[bool] = None,
    ):

        self._path: str = None  # type: ignore
        self._metadata_folder: str = None  # type: ignore
        self._metadata_file: str = None  # type: ignore
        self._item_metadata_path: str = None  # type: ignore
        self._item_path_hashes: str = None  # type: ignore
        self._item_path_files: str = None  # type: ignore

        self._metadata: Optional[Mapping[str, Any]] = None
        self._info: Optional[Mapping[str, Any]] = None
        self._managed_files: Optional[Mapping[str, Any]] = None
        self._hash_contents: Dict[str, Mapping[str, Any]] = {}

        self._use_global_metadata: Optional[bool] = use_global_metadata

        self.load_folder(path=path, metadata_folder=metadata_folder)

    def __eq__(self, other):

        if not isinstance(other, LocalFolder):
            return False

        return self.get_full_path() == other.get_full_path()

    def __hash__(self):

        return hash(self.get_full_path())

    @property
    def use_global_metadata(self) -> Optional[bool]:
        return self._use_global_metadata

    @use_global_metadata.setter
    def use_global_metadata(self, use_global_metadata: bool):

        if use_global_metadata == self._use_global_metadata:
            return

        self._use_global_metadata = use_global_metadata
        self.invalidate()

    @property
    def metadata_folder(self) -> str:
        return self._metadata_folder

    @metadata_folder.setter
    def metadata_folder(self, metadata_folder: Optional[str] = None) -> None:

        if (
            metadata_folder is not None
            and os.path.abspath(metadata_folder) == self._metadata_folder
        ):
            return

        self._metadata_folder = metadata_folder  # type: ignore
        self.invalidate()

    def load_folder(
        self, path: Union[str, Path], metadata_folder: Optional[str] = None
    ):

        if isinstance(path, Path):
            path = path.as_posix()

        self._path = os.path.abspath(os.path.expanduser(path))
        if os.path.exists(self._path) and not os.path.isdir(
            os.path.realpath(self._path)
        ):
            raise FrklException(
                msg=f"Can't create LocalFolder object '{self._path}'",
                reason="Not a folder.",
            )

        if self.use_global_metadata is None:
            if metadata_folder == BRING_GLOBAL_METADATA_FOLDER:
                self._use_global_metadata = True
            elif metadata_folder is None:
                md_path = os.path.realpath(
                    os.path.join(self._path, BRING_METADATA_FOLDER_NAME)
                )
                if os.path.isdir(md_path):
                    self._use_global_metadata = False
                else:
                    self._use_global_metadata = True
                    metadata_folder = BRING_GLOBAL_METADATA_FOLDER
            else:
                self._use_global_metadata = False

        if metadata_folder is None:
            if self.use_global_metadata:
                metadata_folder = BRING_GLOBAL_METADATA_FOLDER
            else:
                metadata_folder = os.path.join(self._path, BRING_METADATA_FOLDER_NAME)
        self._metadata_folder = os.path.abspath(metadata_folder)
        self._metadata_file = os.path.join(
            self._metadata_folder, BRING_METADATA_FILE_NAME
        )
        self._item_metadata_path = os.path.join(
            self._metadata_folder, BRING_ITEM_METADATA_FOLDER_NAME
        )
        self._item_path_hashes = os.path.join(self._item_metadata_path, "hashes")
        self._item_path_files = os.path.join(self._item_metadata_path, "files")

        self._metadata = None
        self._info = None
        self._managed_files = None

    def invalidate(self) -> None:

        self.load_folder(self._path, self._metadata_folder)

    @property
    def path(self) -> str:
        return self._path  # type ignore

    @property
    def base_name(self):

        return os.path.basename(self.path)

    async def get_metadata_for_hash(self, hash: str) -> Mapping[str, Any]:

        if hash in self._hash_contents.keys():
            return self._hash_contents[hash]

        hash_file = os.path.join(self._item_path_hashes, f"{hash}.json")

        async with await aopen(hash_file) as f:
            content = await f.read()

        self._hash_contents[hash] = json.loads(content)
        return self._hash_contents[hash]

    def ensure_exists(self) -> None:

        ensure_folder(self._path)

    def exists(self, rel_path: Optional[str] = None):

        path = self.get_full_path(rel_path)

        return os.path.exists(path)

    def get_full_path(self, rel_path: Optional[str] = None):

        if not rel_path:
            return self._path

        path = os.path.join(self.path, rel_path)
        return path

    async def get_content_from_text_files(
        self, *rel_paths: str, result_type: str = "text"
    ) -> Mapping[str, Any]:

        result = {}

        def wrap(_rel_path, _rel_type):
            result[_rel_path] = self.get_content_from_file(_rel_path, _rel_type)

        async with create_task_group() as tg:
            for rel_path in rel_paths:
                await tg.spawn(wrap, rel_path, result_type)

        return result

    async def get_content_from_text_file(
        self, rel_path: str, result_type: str = "text"
    ) -> Any:

        async with await aopen(self.get_full_path(rel_path)) as f:
            content = await f.read()

        if not result_type == "text":
            raise NotImplementedError()

        return content

    def get_folder_item(self, rel_path: str):

        folder_item = LocalFolderItem(local_folder=self, rel_path=rel_path)
        return folder_item

    async def get_metadata(self):

        if self._metadata is not None:
            return self._metadata

        if not os.path.exists(self._metadata_file):
            self._metadata = {}

        else:
            async with await aopen(self._metadata_file) as f:
                content = await f.read()

            if content:
                metadata = json.loads(content)
            else:
                metadata = {}

            self._metadata = metadata

        return self._metadata

    def get_metadata_path_for_item(
        self, rel_path: Union["LocalFolderItem", str]
    ) -> str:

        if isinstance(rel_path, LocalFolderItem):
            rel_path = rel_path.rel_path

        if not self._use_global_metadata:
            metadata_path = os.path.join(self._item_metadata_path, "files", rel_path)
        else:
            metadata_path = os.path.join(
                self._item_metadata_path,
                "files",
                f"localhost{os.sep}{self.get_full_path(rel_path)}",
            )
        return metadata_path

    async def get_metadata_for_item(
        self, rel_path: Union["LocalFolderItem", str]
    ) -> Mapping[str, Any]:

        if isinstance(rel_path, LocalFolderItem):
            rel_path = rel_path.rel_path

        if not self.exists(rel_path):
            raise FrklException(
                f"Can't retrieve metadata for: {rel_path}", reason="file does not exist"
            )

        metadata_path = self.get_metadata_path_for_item(rel_path=rel_path)

        metadata: Dict[str, Any] = {}

        if not os.path.exists(metadata_path):
            metadata["managed"] = False
        else:

            real_path = os.path.realpath(metadata_path)
            hash = os.path.basename(real_path)[0:-5]

            pkg_md = await self.get_metadata_for_hash(hash)

            if not pkg_md:
                metadata["managed"] = False
                # TODO: delete empty file?
            else:
                metadata["managed"] = True
                metadata["pkg"] = pkg_md

        return metadata

    async def get_managed_files(
        self, file_list: Optional[Iterable[str]] = None
    ) -> Mapping[str, Mapping[str, Any]]:

        if not file_list:
            file_map = await self.get_all_managed_file_hashes()
        else:
            raise NotImplementedError()

        hash_map: Dict[str, List[str]] = {}

        for k, v in file_map.items():
            hash_map.setdefault(v, []).append(k)

        all_metadata_per_hash = {}

        async def get_md(_hash: str):
            _md = await self.get_metadata_for_hash(_hash)
            all_metadata_per_hash[_hash] = _md

        async with create_task_group() as tg:

            for hash_str in hash_map.keys():
                await tg.spawn(get_md, hash_str)

        result: Dict[str, Mapping[str, Any]] = {}
        for p, hash in file_map.items():
            if self._use_global_metadata:
                index_sep = p.index(os.path.sep)
                full_path = p[index_sep:]
                rel_path = os.path.relpath(full_path, self._path)
            else:
                rel_path = p
            result[rel_path] = all_metadata_per_hash[hash]

        return result

    async def get_all_managed_file_hashes(self) -> Mapping[str, Any]:

        if self._managed_files is not None:
            return self._managed_files

        all: Dict[str, Any] = {}
        for root, dirnames, filenames in os.walk(self._item_path_files, topdown=True):

            for filename in filenames:

                path = os.path.join(root, filename)
                hash_file = os.path.realpath(path)

                if not os.path.exists(hash_file):
                    os.unlink(path)
                    continue

                rel_path = os.path.relpath(path, self._item_path_files)
                if not self._use_global_metadata:
                    link_target = rel_path
                else:
                    link_target = os.path.join(self._item_path_files, path)

                if not self.exists(link_target):
                    os.unlink(path)
                    continue

                all[rel_path] = os.path.basename(hash_file)[0:-5]
        self._managed_files = all
        return self._managed_files

    async def get_info(self) -> Mapping[str, Any]:

        if self._info is not None:
            return self._info

        self._info = {}

        self._info["path"] = self._path
        self._info["folder_exists"] = self.exists

        self._info["metadata_folder_exists"] = os.path.isdir(self._metadata_folder)
        self._info["metadata_file_exists"] = os.path.isfile(self._metadata_file)

        self._info["metadata"] = self.get_metadata()

        return self._info

    def __repr__(self):

        return f"[LocalFolder: path={self.path}]"


class LocalFolderItem(object):
    def __init__(self, local_folder: LocalFolder, rel_path: str):

        self._base_folder: LocalFolder = local_folder
        self._rel_path: str = rel_path
        self._metadata: Optional[Mapping[str, Any]] = None

    def __eq__(self, other):

        if not isinstance(other, LocalFolderItem):
            return False

        return self.full_path == other.full_path

    def __hash__(self):

        return hash(self.full_path)

    @property
    def rel_path(self) -> str:
        return self._rel_path

    @property
    def full_path(self):
        return self._base_folder.get_full_path(self._rel_path)

    @property
    def base_folder(self) -> LocalFolder:
        return self._base_folder

    @property
    def file_name(self) -> str:
        return os.path.basename(self.rel_path)

    @property
    def exists(self):
        return os.path.exists(self.full_path)

    def unlink(self):

        os.unlink(self.full_path)

    def ensure_parent_exists(self):

        ensure_folder(os.path.dirname(self.full_path))

    @property
    def metadata_file_path(self) -> str:

        path = self._base_folder.get_metadata_path_for_item(self)
        return path

    async def get_metadata(self) -> Mapping[str, Any]:

        if self._metadata is None:
            self._metadata = await self._base_folder.get_metadata_for_item(
                self.rel_path
            )
        return self._metadata

    def __str__(self):

        return self.rel_path

    def __repr__(self):

        return self.rel_path


class MergeStrategy(metaclass=ABCMeta):

    _plugin_type = "instance"

    def __init__(self, **config):

        self._config: MutableMapping[str, Any] = config

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

    def _move_or_copy_file(
        self, source: LocalFolderItem, target: LocalFolderItem
    ) -> None:

        target.base_folder.ensure_exists()

        if self.move_method == "copy":
            shutil.copy2(source.full_path, target.full_path)
        elif self.move_method == "move":
            shutil.move(source.full_path, target.full_path)
        else:
            raise FrklException(
                f"Can't move file '{source}', invalid move method '{self.move_method}'. Allowed: {', '.join(['move', 'copy'])}"
            )

    async def pre_merge_hook(
        self,
        target_folder: LocalFolder,
        merge_map: Mapping[LocalFolderItem, LocalFolderItem],
    ) -> None:

        pass

    async def merge(
        self,
        target_folder: Union[LocalFolder, str, Path],
        *sources: Union[str, Path, LocalFolder],
    ) -> Mapping[str, Any]:

        if isinstance(target_folder, (str, Path)):
            _target_folder: LocalFolder = LocalFolder(target_folder)
        else:
            _target_folder = target_folder

        _sources: List[Union[str, LocalFolder]] = []

        for source in sources:
            if not isinstance(source, LocalFolder):
                if isinstance(source, str):
                    _source: str = os.path.realpath(os.path.expanduser(source))
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
            else:
                _sources.append(source)

        merge_map: Dict[LocalFolderItem, LocalFolderItem] = {}

        for _source_folder in _sources:

            if isinstance(_source_folder, (str, Path)):
                source_folder: LocalFolder = LocalFolder(_source_folder)
            else:
                source_folder = _source_folder

            for root, dirnames, filenames in os.walk(
                source_folder.get_full_path(), topdown=True
            ):

                if self.exclude_dirs:
                    dirnames[:] = [d for d in dirnames if d not in self.exclude_dirs]

                for filename in filenames:

                    full_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(full_path, source_folder.get_full_path())

                    if self.flatten:
                        target_file = filename
                    else:
                        target_file = rel_path

                    source_file_item = LocalFolderItem(
                        local_folder=source_folder, rel_path=rel_path
                    )
                    target_file_item = LocalFolderItem(
                        local_folder=_target_folder, rel_path=target_file
                    )

                    if target_file_item in merge_map.values():
                        raise FrklException(
                            msg=f"Can't merge folders: {source_folder.base_name} -> {_target_folder.base_name}",
                            reason=f"Duplicate target file: {target_file_item.rel_path}",
                        )
                    merge_map[source_file_item] = target_file_item

        await self.pre_merge_hook(target_folder=_target_folder, merge_map=merge_map)

        merge_result = {}
        async with create_task_group() as tg:

            async def merge(_source_file, _target_file):
                r = await self.merge_source(_source_file, _target_file)
                merge_result[_source_file] = {"target": _target_file, "result": r}

            for src, target in merge_map.items():

                await tg.spawn(merge, src, target)

        return merge_result

    @abstractmethod
    async def merge_source(
        self, source_file: LocalFolderItem, target_file: LocalFolderItem
    ) -> None:
        pass


class FolderMerge(object):
    def __init__(
        self,
        typistry: Typistry,
        target: Union[str, Path, LocalFolder],
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

        if isinstance(target, (str, Path)):
            target = LocalFolder(target)
        self._target: LocalFolder = target

        if isinstance(merge_strategy, str):
            merge_strategy = explode_merge_strategy(merge_strategy)
        if isinstance(merge_strategy, collections.Mapping):
            ms_type = merge_strategy.get("type", "default")
            _ms_config = merge_strategy.get("config", None)
            if _ms_config is None:
                ms_config = {}
            else:
                ms_config = copy.deepcopy(_ms_config)

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
    def target(self) -> LocalFolder:
        return self._target

    async def merge_folders(self, *sources: Union[str, Path]) -> Mapping[str, Any]:

        self._target.ensure_exists()
        result = await self.merge_strategy.merge(self._target, *sources)
        return result


class MergeStrategyClickType(DictType):

    name = "merge_strategy_type"

    def __init__(self):

        super().__init__()

    def convert(self, value, param, ctx):

        if isinstance(value, str) and "=" in value:
            value = super().convert(value, param, ctx)

        result = explode_merge_strategy(value)

        return result


class MergeStrategyArgType(DerivedArg):
    def _pre_check_value(self, value: Any) -> Any:

        if isinstance(value, str):
            value = {"type": value}
        else:
            value.setdefault("type", "default")

        return value
