# -*- coding: utf-8 -*-
import collections
import os
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    Mapping,
    MutableMapping,
    Optional,
    Union,
)

from bring.config.bring_config import BringConfig
from bring.defaults import BRING_CONTEXT_NAMESPACE, BRING_DEFAULT_INDEXES
from bring.pkg_index.config import IndexConfig
from bring.pkg_index.folder_index import BringDynamicIndexTing
from bring.pkg_index.index import BringIndexTing, retrieve_index_content
from frtls.exceptions import FrklException
from frtls.strings import is_git_repo_url, is_url_or_abbrev
from tings.tingistry import Tingistry


if TYPE_CHECKING:
    from bring.pkg_index.static_index import BringStaticIndexTing


class IndexFactory(object):
    def __init__(
        self, tingistry: Tingistry, bring_config: Optional[BringConfig] = None
    ):

        self._tingistry: Tingistry = tingistry
        self._bring_config: Optional[BringConfig] = bring_config
        self._config_indexes: Optional[
            Mapping[str, Union[None, str, Mapping[str, Any]]]
        ] = None
        self._default_indexes: Optional[Dict[str, Mapping[str, Any]]] = None

    @property
    def bring_config(self) -> Optional[BringConfig]:

        return self._bring_config

    @bring_config.setter
    def bring_config(self, bring_config: BringConfig) -> None:
        self._bring_config = bring_config
        self.invalidate()

    def invalidate(self):

        self._default_indexes = None
        self._config_indexes = None

    async def get_config_indexes(
        self
    ) -> Mapping[str, Union[str, None, Mapping[str, Any]]]:

        if self._config_indexes is not None:
            return self._config_indexes

        if self.bring_config is None:
            return {}

        indexes: Iterable[
            Union[str, Mapping[str, Any]]
        ] = await self.bring_config.get_config_value_async("indexes")

        self._config_indexes = {}
        for item in indexes:
            if isinstance(item, str):
                if "=" in item:
                    id, data = item.split("=", maxsplit=1)
                    self._config_indexes[id] = data
                else:
                    self._config_indexes[item] = None
            elif isinstance(item, collections.Mapping):
                id = item["id"]
                self._config_indexes[id] = item
            else:
                raise TypeError(f"Invalid type for index config: {type(item)}")
        return self._config_indexes

    @property
    def default_indexes(self) -> Mapping[str, Mapping[str, Any]]:

        if self._default_indexes is None:
            self._default_indexes = {}

            idx: Mapping[str, Any]
            for idx in BRING_DEFAULT_INDEXES:
                self._default_indexes[idx["id"]] = idx  # type: ignore

        return self._default_indexes

    async def explode_index_string(self, index_string: str) -> MutableMapping[str, Any]:

        result: Dict[str, Any] = {}

        if index_string.startswith("gitlab"):

            tokens = index_string.split(".")
            username = tokens[1]
            repo = tokens[2]
            version = "master"
            path = None

            if len(tokens) > 3:
                version = tokens[4]
                if len(tokens) > 4:
                    raise NotImplementedError()
                    # path = tokens[5:]

            url = f"https://gitlab.com/{username}/{repo}/-/raw/{version}/.br.idx"

            try:
                content = await retrieve_index_content(index_url=url, update=False)
                result["type"] = "index_file"
                result["uri"] = url
                result["version"] = version
                result["content"] = content
                # result["path"] = path
            except Exception:
                result["type"] = "git_repo"
                result["uri"] = f"https://gitlab.com/{username}/{repo}.git"
                result["version"] = version
                result["content"] = None
                # result["path"] = path

            result["id"] = index_string
        elif index_string.startswith("github"):
            tokens = index_string.split(".")
            username = tokens[1]
            repo = tokens[2]
            version = "master"
            path = None

            if len(tokens) > 3:
                version = tokens[4]
                if len(tokens) > 4:
                    raise NotImplementedError()
                    # path = tokens[5:]

            url = (
                f"https://raw.githubusercontent.com/{username}/{repo}/{version}/.br.idx"
            )

            try:
                content = await retrieve_index_content(index_url=url, update=False)
                result["type"] = "index_file"
                result["uri"] = url
                result["version"] = version
                result["content"] = content
                result["path"] = path
            except Exception:
                result["type"] = "git_repo"
                result["uri"] = f"https://github.com/{username}/{repo}.git"
                result["version"] = version
                result["content"] = None
                result["path"] = path

            result["id"] = index_string

        elif index_string.startswith("bitbucket"):
            tokens = index_string.split(".")
            username = tokens[1]
            repo = tokens[2]
            path = tokens[3:]
            raise NotImplementedError()

        elif index_string.endswith(".br.idx"):
            if is_url_or_abbrev(index_string):
                result["type"] = "index_file"
                result["uri"] = index_string
            elif os.path.isfile(index_string):
                result["type"] = "index_file"
                result["uri"] = os.path.abspath(index_string)
            else:
                raise FrklException(
                    msg=f"Can't determine type of index file: {index_string}"
                )

            result["id"] = result["uri"]
        elif os.path.isdir(os.path.realpath(index_string)):
            result["id"] = os.path.basename(index_string)
            result["type"] = "folder"
            result["uri"] = os.path.abspath(index_string)
        elif is_git_repo_url(index_string):
            result["type"] = "git_repo"
            result["uri"] = index_string
        else:
            raise FrklException(msg=f"Can't parse index string: {index_string}")

        return result

    async def augment_data(self, index_data: MutableMapping[str, Any]) -> None:

        pass
        # if "id" not in index_data.keys():
        #     index_data["id"] = index_data["uri"]
        #
        # if "type" not in index_data.keys():
        #     raise ValueError(f"No 'type' key in index config: {index_data}")

    async def create_index_config(
        self, index_data: Union[str, Mapping[str, Any], IndexConfig]
    ) -> IndexConfig:

        if isinstance(index_data, IndexConfig):
            return index_data

        _idx_id: Optional[str] = None
        _idx_data: Union[str, Mapping[str, Any]]

        if isinstance(index_data, str) and "=" in index_data:
            _idx_id, _idx_data = index_data.split("=", maxsplit=1)
        else:
            _idx_data = index_data

        _index_data: MutableMapping[str, Any]

        if isinstance(_idx_data, str):
            config_indexes = await self.get_config_indexes()
            if _idx_data in config_indexes.keys():
                value = config_indexes[_idx_data]
                if value is None:
                    _index_data = dict(self.default_indexes[_idx_data])
                elif isinstance(value, str):
                    if value in self.default_indexes.keys():
                        _index_data = dict(self.default_indexes[value])
                    else:
                        _index_data = await self.explode_index_string(value)
                        _index_data["id"] = _idx_data
                elif isinstance(_idx_data, collections.Mapping):
                    _index_data = _idx_data
                else:
                    raise TypeError(f"Invalid type for index data: {type(index_data)}")
            elif _idx_data in self.default_indexes.keys():
                _index_data = dict(self.default_indexes[_idx_data])
            else:
                _index_data = await self.explode_index_string(_idx_data)
        elif isinstance(_idx_data, collections.Mapping):
            _index_data = dict(_idx_data)
        else:
            raise TypeError(f"Invalid type for index data: {type(index_data)}")

        if _idx_id is not None:
            _index_data["id"] = _idx_id

        await self.augment_data(_index_data)

        return IndexConfig(**_index_data)

    async def create_index(
        self,
        index_data: Union[str, Mapping[str, Any], IndexConfig],
        allow_existing: bool = False,
    ) -> BringIndexTing:

        index_config: IndexConfig = await self.create_index_config(
            index_data=index_data
        )

        ting_name = f"{BRING_CONTEXT_NAMESPACE}.{index_config.id}"

        if allow_existing:
            existing: BringIndexTing = self._tingistry.get_ting(
                ting_name, raise_exception=False
            )  # type: ignore
            if existing is not None:
                return existing

        if index_config.index_type == "index_file":

            index = await self.create_index_from_index_file(ting_name)

        elif index_config.index_type == "folder":

            index = await self.create_index_from_folder(ting_name)

        elif index_config.index_type == "git_repo":

            index = await self.create_index_from_git(ting_name)

        else:
            raise NotImplementedError()

        index.set_input(
            info=index_config.info,
            uri=index_config.uri,
            id=index_config.id,
            labels=index_config.labels,
            tags=index_config.tags,
        )

        await index.get_values("id")

        return index

    async def create_index_from_git(self, ting_name: str) -> "BringIndexTing":

        ctx: "BringDynamicIndexTing" = self._tingistry.create_ting(  # type: ignore
            "bring_dynamic_index_ting", ting_name
        )

        # await ctx.get_values("config")
        return ctx

    async def create_index_from_folder(self, ting_name: str) -> "BringIndexTing":

        ctx: "BringDynamicIndexTing" = self._tingistry.create_ting(  # type: ignore
            "bring_dynamic_index_ting", ting_name
        )

        # await ctx.get_values("config")
        return ctx

    async def create_index_from_index_file(self, ting_name: str) -> "BringIndexTing":

        # content = index_config.get("content", None)
        # id = index_config.id
        # if content is None:
        #     uri = index_config["uri"]
        #     content = await retrieve_index_content(uri, update=False)

        ctx: "BringStaticIndexTing" = self._tingistry.create_ting(  # type: ignore
            "bring.types.indexes.default_index", ting_name
        )
        return ctx
