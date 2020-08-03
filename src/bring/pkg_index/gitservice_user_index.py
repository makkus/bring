# -*- coding: utf-8 -*-
import logging
from abc import abstractmethod
from typing import Any, Dict, Iterable, Mapping, Optional

import arrow
from bring.pkg_index.config import IndexConfig
from bring.pkg_index.index import BringIndexTing
from bring.pkg_index.pkg import PkgTing
from frkl.common.exceptions import FrklException
from frkl.tasks.task import Task
from tings.ting import TingMeta


log = logging.getLogger("bring")


class BringGitServiceRepo(object):
    def __init__(
        self,
        url: str,
        info: Optional[Mapping[str, Any]] = None,
        tags: Optional[Iterable[str]] = None,
        labels: Optional[Mapping[str, str]] = None,
    ):

        self.url: str = url
        self.info: Optional[Mapping[str, Any]] = info
        self.tags: Optional[Iterable[str]] = tags
        self.labels: Optional[Mapping[str, str]] = labels

    def to_dict(self) -> Dict[str, Any]:

        result: Dict[str, Any] = {
            "source": {"url": self.url, "use_commits_as_version": False, "type": "git"}
        }
        if self.info:
            result["info"] = self.info
        if self.tags:
            result["tags"] = self.tags
        if self.labels:
            result["labels"] = self.labels

        return result


class BringGitServiceUserIndex(BringIndexTing):
    def __init__(self, name: str, meta: TingMeta):

        self._pkgs: Optional[Mapping[str, PkgTing]] = None
        self._service_username: Optional[str] = None
        self._user_repos: Optional[Mapping[str, BringGitServiceRepo]] = None

        self._metadata_timestamp: Optional[str] = None

        super().__init__(name=name, meta=meta)

    def _invalidate(self) -> None:

        self._pkgs = None
        self._user_repos = None

    async def get_uri(self) -> str:
        if self._uri is None:
            raise FrklException(
                "Can't retrieve uri for index.", reason="Index not initialized yet."
            )
        return self._uri

    @property
    def service_username(self) -> str:

        if not self._service_username:
            raise FrklException(
                msg=f"Can't retrieve service username for index {self.id}.",
                reason="Index not initialized yet.",
            )

        return self._service_username

    @abstractmethod
    def get_service_name(self) -> str:
        pass

    async def init(self, config: IndexConfig):

        self._service_username = config.index_type_config["service_user"]
        self._uri = f"{self.get_service_name()}.{self._service_username}"

        self.invalidate()

    async def _create_update_tasks(self) -> Optional[Task]:
        raise NotImplementedError()

    @abstractmethod
    async def retrieve_user_repos(self) -> Mapping[str, BringGitServiceRepo]:
        pass

    async def get_user_repos(self) -> Mapping[str, BringGitServiceRepo]:
        if self._user_repos is None:
            self._user_repos = await self.retrieve_user_repos()
            self._metadata_timestamp = str(arrow.Arrow.now())
        return self._user_repos

    async def _get_metadata_timestamp(self) -> Optional[str]:

        return self._metadata_timestamp

    async def _get_pkgs(self) -> Mapping[str, PkgTing]:

        if self._pkgs is not None:
            return self._pkgs

        repos = await self.get_user_repos()

        pkgs = {}
        for name, data in repos.items():

            if "." in name:
                repl_name = name.replace(".", "_")
                if repl_name in repos.keys():
                    log.warning(
                        f"Ignoring repository '{name}', not unique, since repository '{repl_name}' also exists."
                    )
                    continue
                name = repl_name

            pkg_data = data.to_dict()

            ting = await self.create_pkg_ting(name, **pkg_data)
            pkgs[name] = ting

        self._pkgs = pkgs
        return self._pkgs

    async def create_pkg_ting(self, pkg_name: str, **pkg_data: Any) -> PkgTing:

        ting: PkgTing = self.tingistry.create_ting(  # type: ignore
            "bring.types.dynamic_pkg",
            f"{self.full_name}.pkgs.{pkg_name}",  # type: ignore
        )
        ting.bring_index = self

        ting.set_input(**pkg_data)

        return ting
