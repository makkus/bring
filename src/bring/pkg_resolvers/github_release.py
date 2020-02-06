# -*- coding: utf-8 -*-
from typing import List, Any, Dict, Union

import httpx

from bring.pkg_resolvers import SimplePkgResolver


class GithubRelease(SimplePkgResolver):
    def __init__(self):

        super().__init__()

    def get_supported_source_types(self) -> List[str]:

        return ["github-release"]

    def _get_unique_id(self, source_details: Dict) -> str:

        github_user = source_details.get("user_name")
        repo_name = source_details.get("repo_name")

        return f"{github_user}_{repo_name}"

    async def _retrieve_versions(
        self, source_details: Union[str, Dict]
    ) -> Dict[str, Any]:

        github_user = source_details.get("user_name")
        repo_name = source_details.get("repo_name")

        repo_url = f"https://api.github.com/repos/{github_user}/{repo_name}/releases"

        async with httpx.AsyncClient() as client:
            r = await client.get(repo_url)
            releases = r.json()

        result = {}
        for release in releases:
            version = release["name"]
            # prerelease = release["prerelease"]
            created_at = release["created_at"]
            # tarball_url = release["tarball_url"]
            # zipball_url = release["zipball_url"]

            assets = []
            for asset in release["assets"]:

                asset_name = asset["name"]
                # content_type = asset["content_type"]
                # size = asset["size"]
                # browser_download_url = asset["browser_download_url"]
                assets[asset_name] = {}

            result[version] = {"created_at": created_at}

        return result

    def parse_release_data(self, data):

        pass
