# -*- coding: utf-8 -*-
from typing import Any, Dict, Mapping, Optional

from bring.pkg_index.config import IndexConfig
from bring.pkg_index.index import BringIndexTing
from bring.pkg_index.pkg import PkgTing
from bring.utils.github import get_data_from_github
from frkl.common.exceptions import FrklException
from frkl.tasks.task import Task
from tings.ting import TingMeta


class BringGithubUserIndex(BringIndexTing):
    def __init__(self, name: str, meta: TingMeta):

        self._pkgs: Optional[Mapping[str, PkgTing]] = None
        self._github_username: Optional[str] = None
        self._user_repos: Optional[Dict[str, Mapping[str, Any]]] = None

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

    async def init(self, config: IndexConfig):

        self._github_username = config.index_type_config["github_user"]
        self._uri = f"github.{self._github_username}"

        self.invalidate()

    async def _create_update_tasks(self) -> Optional[Task]:
        raise NotImplementedError()

    async def get_user_repos(self) -> Mapping[str, Mapping[str, Any]]:

        if self._user_repos is not None:
            return self._user_repos

        request_path = f"/users/{self._github_username}/repos"
        user_repos = await get_data_from_github(path=request_path)
        self._user_repos = {}
        for r in user_repos:
            self._user_repos[r["name"]] = r

        return self._user_repos

    async def _get_pkgs(self) -> Mapping[str, PkgTing]:

        if self._pkgs is not None:
            return self._pkgs

        repos = await self.get_user_repos()

        pkgs = {}
        for name, data in repos.items():

            issues_url = data["issues_url"].replace("{/number}", "")

            slug = data["description"]
            if not slug:
                slug = f"github repository for {name}"

            pkg_data: Dict[str, Any] = {
                "info": {
                    "slug": slug,
                    "homepage": data["homepage"],
                    "issues": issues_url,
                },
                "source": {
                    "url": data["clone_url"],
                    "use_commits_as_version": False,
                    "type": "git",
                },
                "tags": [],
                "labels": {},
            }

            if data.get("langauge", None):
                pkg_data["labels"]["language"] = data["language"]

            ting = await self.create_pkg_ting(name, **pkg_data)
            pkgs[name] = ting

        self._pkgs = pkgs
        return self._pkgs

    async def create_pkg_ting(self, pkg_name: str, **pkg_data: Any) -> PkgTing:

        # ting: PkgTing = self.tingistry.get_ting(  # type: ignore
        #     f"{self.full_name}.pkgs.{pkg_name}"
        # )
        # if ting is None:
        ting: PkgTing = self.tingistry.create_ting(  # type: ignore
            "bring.types.dynamic_pkg",
            f"{self.full_name}.pkgs.{pkg_name}",  # type: ignore
        )
        ting.bring_index = self

        ting.set_input(**pkg_data)
        # ting._set_result(data)
        return ting
