# -*- coding: utf-8 -*-
from typing import Dict, List, Mapping

from bring.pkg_index.gitservice_user_index import (
    BringGitServiceRepo,
    BringGitServiceUserIndex,
)
from bring.utils.github import get_list_data_from_github


class BringGithubUserIndex(BringGitServiceUserIndex):
    def get_service_name(self) -> str:
        return "github"

    async def retrieve_user_repos(self) -> Mapping[str, BringGitServiceRepo]:

        request_path = f"/users/{self.service_username}/repos"
        repo_data = await get_list_data_from_github(path=request_path)
        user_repos = {}
        for data in repo_data:

            issues_url = data["issues_url"].replace("{/number}", "")
            slug = data["description"]
            if not slug:
                slug = f"github repository for {data['name']}"
            info = {
                "slug": slug,
                "homepage": data["homepage"],
                "issues": issues_url,
            }
            url = data["clone_url"]

            tags: List[str] = []
            labels: Dict[str, str] = {}
            if data.get("langauge", None):
                labels["language"] = data["language"]

            user_repos[data["name"]] = BringGitServiceRepo(
                url=url, info=info, tags=tags, labels=labels
            )

        return user_repos
