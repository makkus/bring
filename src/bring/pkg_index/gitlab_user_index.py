# -*- coding: utf-8 -*-
from typing import Dict, List, Mapping

from bring.pkg_index.gitservice_user_index import (
    BringGitServiceRepo,
    BringGitServiceUserIndex,
)
from bring.utils.gitlab import get_data_from_gitlab


class BringGitlabUserIndex(BringGitServiceUserIndex):
    def get_service_name(self) -> str:
        return "gitlab"

    async def retrieve_user_repos(self) -> Mapping[str, BringGitServiceRepo]:

        try:
            request_path = f"/users/{self.service_username}/projects"
            repo_data = await get_data_from_gitlab(path=request_path)
        except Exception:
            request_path = f"/groups/{self.service_username}/projects"
            repo_data = await get_data_from_gitlab(path=request_path)

        user_repos = {}
        for data in repo_data:

            # issues_url = data["issues_url"].replace("{/number}", "")
            slug = data["description"]
            if not slug:
                slug = f"github repository for {data['name']}"
            info = {
                "slug": slug,
                "homepage": data["web_url"],
                # "issues": issues_url,
            }
            url = data["http_url_to_repo"]

            tags: List[str] = data["tag_list"]
            labels: Dict[str, str] = {}
            if data.get("langauge", None):
                labels["language"] = data["language"]

            user_repos[data["name"]] = BringGitServiceRepo(
                url=url, info=info, tags=tags, labels=labels
            )

        return user_repos
