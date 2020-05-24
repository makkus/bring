# -*- coding: utf-8 -*-
import collections
import os
from typing import TYPE_CHECKING, Any, Dict, Mapping, MutableMapping, Optional, Union

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
    def __init__(self, tingistry: Tingistry):

        self._tingistry: Tingistry = tingistry

        self._default_indexes: Optional[Dict[str, Mapping[str, Any]]] = None

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
        elif isinstance(index_data, str) and index_data in self.default_indexes.keys():
            _index_data: MutableMapping[str, Any] = dict(
                self.default_indexes[index_data]
            )
        elif isinstance(index_data, str):
            _index_data = await self.explode_index_string(index_data)
        elif isinstance(index_data, collections.Mapping):
            _index_data = dict(index_data)
        else:
            raise ValueError(f"Invalid type for index data: {type(index_data)}")

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
