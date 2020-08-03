# -*- coding: utf-8 -*-
import collections
import logging
import os
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Union,
)

from bring.config.bring_config import BringConfig
from bring.defaults import (
    BRING_CONTEXT_NAMESPACE,
    BRING_DEFAULT_INDEX_ALIASES,
    BRING_DEFAULT_INDEX_CONFIG,
    DEFAULT_FOLDER_INDEX_EXTENSION,
    DEFAULT_FOLDER_INDEX_NAME,
)
from bring.pkg_index.config import IndexConfig
from bring.pkg_index.folder_index import BringDynamicIndexTing
from bring.pkg_index.index import BringIndexTing
from bring.pkg_index.utils import ensure_index_file_is_local
from frkl.common.dicts import dict_merge
from frkl.common.exceptions import FrklException
from frkl.common.strings import is_git_repo_url, is_url_or_abbrev
from tings.tingistry import Tingistry


if TYPE_CHECKING:
    from bring.pkg_index.static_index import BringStaticIndexTing
    from bring.pkg_index.github_user_index import BringGithubUserIndex

log = logging.getLogger("bring")


async def resolve_index_string(index_string: str) -> MutableMapping[str, Any]:

    index_id: Optional[str] = None

    if "=" in index_string:
        index_id, index_string = index_string.split("=", maxsplit=1)

    if index_string in BRING_DEFAULT_INDEX_ALIASES.keys():
        if not index_id:
            index_id = index_string
        index_string = BRING_DEFAULT_INDEX_ALIASES[index_string]

    index_data = await explode_index_string(index_string)

    if (
        index_data["id"] in BRING_DEFAULT_INDEX_CONFIG.keys()
        or index_data["id"] in BRING_DEFAULT_INDEX_ALIASES.values()
    ):
        default_data = BRING_DEFAULT_INDEX_CONFIG.get(index_data["id"], None)
        if default_data is None:
            for k, v in BRING_DEFAULT_INDEX_ALIASES.items():
                if v == index_data["id"]:
                    _default_data: MutableMapping = dict(BRING_DEFAULT_INDEX_CONFIG[k])
                    break
        else:
            _default_data = dict(default_data)

        if not _default_data:
            log.error(f"Error adding default data for index: {index_string}")
        else:
            index_data = dict_merge(
                _default_data, index_data, copy_dct=True
            )  # type: ignore

    if index_id:
        index_data["id"] = index_id

    return index_data


async def explode_index_string(index_string: str) -> MutableMapping[str, Any]:

    result: Dict[str, Any] = {}

    if index_string.startswith("gitlab"):

        tokens = index_string.split(".")
        username = tokens[1]

        repo = tokens[2]
        version = "master"

        if len(tokens) > 3:
            version = tokens[3]
            if len(tokens) > 4:
                raise NotImplementedError()
                # path = tokens[5:]

        result["type"] = "git_repo"
        result[
            "index_file"
        ] = f"https://gitlab.com/{username}/{repo}/-/raw/{version}/.bring/{DEFAULT_FOLDER_INDEX_NAME}"
        result["git_url"] = f"https://gitlab.com/{username}/{repo}.git"
        result["version"] = version

        result["id"] = index_string
        result["auto_id"] = index_string

    elif index_string.startswith("github"):
        tokens = index_string.split(".")

        if len(tokens) < 2:
            raise FrklException(
                msg=f"Can't resolve index with id '{index_string}'.",
                reason="No github unsername provided.",
                solution="Make sure you did not forget the package name. Full format if the repo is to be the package: 'github.<user_name>.<repo_name>', or if the repo is a bring index: 'github.<user_name.<repo_name>.<package_name>'.",
            )

        username = tokens[1]

        if len(tokens) == 2:
            # repo is the package
            result["type"] = "github_user"
            result["github_user"] = username
            result["id"] = index_string
            result["auto_id"] = index_string
        else:
            # repo is an index
            repo = tokens[2]
            version = "master"

            if len(tokens) > 3:
                version = tokens[3]
                if len(tokens) > 4:
                    raise NotImplementedError()
                    # path = tokens[5:]

            result["type"] = "git_repo"
            result[
                "index_file"
            ] = f"https://raw.githubusercontent.com/{username}/{repo}/{version}/.bring/{DEFAULT_FOLDER_INDEX_NAME}"
            result["git_url"] = f"https://github.com/{username}/{repo}.git"
            result["version"] = version

            result["id"] = index_string
            result["auto_id"] = index_string

    elif index_string.startswith("bitbucket"):
        tokens = index_string.split(".")
        username = tokens[1]
        repo = tokens[2]
        raise NotImplementedError()

    elif index_string.endswith(DEFAULT_FOLDER_INDEX_EXTENSION):
        result["type"] = "index_file"
        if is_url_or_abbrev(index_string):
            result["index_file"] = index_string
            result["id"] = result["index_file"]
        elif os.path.isfile(index_string):
            result["index_file"] = os.path.abspath(index_string)
            result["id"] = f"file://{result['index_file']}"
        else:
            raise FrklException(
                msg=f"Can't determine type of index file: {index_string}"
            )
        result["auto_id"] = index_string
    elif os.path.isdir(os.path.realpath(index_string)):
        result["type"] = "folder"
        result["path"] = os.path.abspath(index_string)
        result["index_file"] = os.path.join(
            result["path"], ".bring", DEFAULT_FOLDER_INDEX_NAME
        )
        result["id"] = f"file://{result['path']}"
        result["auto_id"] = index_string
    elif is_git_repo_url(index_string):
        result["type"] = "git_repo"
        result["git_url"] = index_string
        result["id"] = result["git_url"]
        # TODO: calculate and insert index_file key for known hosts
        result["auto_id"] = index_string
    else:
        raise FrklException(msg=f"Can't parse index string: {index_string}")

    return result


class IndexFactory(object):
    def __init__(
        self, tingistry: Tingistry, bring_config: Optional[BringConfig] = None
    ):

        self._tingistry: Tingistry = tingistry
        self._bring_config: Optional[BringConfig] = bring_config
        self._aliases: Optional[Dict[str, str]] = None
        self._indexes_in_config: Optional[List[str]] = None
        self._config_indexes: Optional[Mapping[str, Mapping[str, Any]]] = None
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
        self._aliases = None

    async def index_name_aliases(self) -> Mapping[str, str]:

        if self._aliases is None:
            self._aliases = dict(BRING_DEFAULT_INDEX_ALIASES)
            if self._bring_config is None:
                return self._aliases

            indexes: Iterable[
                Union[str, Mapping[str, Any]]
            ] = await self._bring_config.get_config_value_async("indexes")

            for item in indexes:
                if isinstance(item, str):
                    if "=" in item:
                        alias, idx = item.split("=", maxsplit=1)
                        self._aliases[alias] = idx
                elif isinstance(item, collections.Mapping):
                    raise NotImplementedError()

        return self._aliases  # type: ignore

    async def get_indexes_in_config(self) -> Iterable[str]:

        if self._indexes_in_config is None:
            await self.get_index_configs()
        return self._indexes_in_config  # type: ignore

    async def get_index_configs(self) -> Mapping[str, Mapping[str, Any]]:

        if self._config_indexes is not None:
            return self._config_indexes

        self._indexes_in_config = []

        if self.bring_config is None:
            self._config_indexes = {}
            return self._config_indexes

        indexes: Iterable[
            Union[str, Mapping[str, Any]]
        ] = await self.bring_config.get_config_value_async("indexes")

        self._config_indexes = {}
        auto_ids = {}
        for item in indexes:
            if isinstance(item, str):
                index_data = await resolve_index_string(item)
            elif isinstance(item, collections.Mapping):
                id = item["id"]
                index_data = await resolve_index_string(id)
                dict_merge(index_data, item, copy_dct=False)
            else:
                raise TypeError(f"Invalid type for index config: {type(item)}")

            id = index_data["id"]
            self._indexes_in_config.append(id)
            auto_id = index_data["auto_id"]

            auto_ids[auto_id] = id
            if id in self._config_indexes.keys():
                raise FrklException(
                    msg=f"Can't add index config with id '{id}'",
                    reason="Duplicate index id.",
                )
            self._config_indexes[id] = index_data

        # make sure we also use the config if the lower-level id is used
        for auto_id in auto_ids.keys():
            if auto_id in self._config_indexes.keys():
                continue
            self._config_indexes[auto_id] = self._config_indexes[auto_ids[auto_id]]

        return self._config_indexes

    # @property
    # def default_indexes(self) -> Mapping[str, Mapping[str, Any]]:
    #
    #     if self._default_indexes is None:
    #         self._default_indexes = {}
    #
    #         idx: Mapping[str, Any]
    #         for idx in BRING_DEFAULT_INDEXES:
    #             self._default_indexes[idx["id"]] = idx  # type: ignore
    #
    #     return self._default_indexes

    async def create_index_config(
        self, index_data: Union[str, Mapping[str, Any], IndexConfig]
    ) -> IndexConfig:

        if isinstance(index_data, IndexConfig):
            raise NotImplementedError()
        elif not isinstance(index_data, str):
            raise NotImplementedError()

        index_configs = await self.get_index_configs()

        if index_data in index_configs.keys():
            index_config = index_configs[index_data]
        else:
            index_config = await resolve_index_string(index_data)

        return IndexConfig(**index_config)

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
            existing: BringIndexTing = self._tingistry.get_ting(  # type: ignore
                ting_name, raise_exception=False
            )  # type: ignore
            if existing is not None:
                return existing

        if index_config.index_type == "index_file":

            index = await self.create_index_from_index_file(ting_name)

        elif index_config.index_type == "folder":

            index = await self.create_index_from_folder(ting_name)

        elif index_config.index_type == "git_repo":

            if index_config.index_file:
                try:
                    await ensure_index_file_is_local(index_config.index_file)
                    index = await self.create_index_from_index_file(ting_name)
                except Exception:
                    log.debug(
                        f"No valid index file exists for git repo index '{index_config.id}', using git repo directly..."
                    )
                    index = await self.create_index_from_git(ting_name)

        elif index_config.index_type == "github_user":

            index = await self.create_index_from_github_user(ting_name)

        else:
            raise NotImplementedError()

        index.set_input(config=index_config)

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

    async def create_index_from_github_user(self, ting_name: str) -> "BringIndexTing":

        ctx: "BringGithubUserIndex" = self._tingistry.create_ting(  # type: ignore
            "bring_github_user_index", ting_name
        )

        # await ctx.get_values("config")
        return ctx
