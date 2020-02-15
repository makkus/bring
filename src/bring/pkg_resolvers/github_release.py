# -*- coding: utf-8 -*-
import copy
import logging
import re
from typing import List, Dict, Union, Tuple

import httpx

from bring.pkg_resolvers import HttpDownloadPkgResolver

DEFAULT_URL_REGEXES = [
    "https://github.com/.*/releases/download/v(?P<version>.*)/.*-v(?P=version)-(?P<arch>[^-]*)-(?P<os>[^.]*)\\..*$"
]

# "https://github.com/.*/releases/download/v(?P<version>.*)/.*-v(?P=version)-(?P<arch>[^-]*)-(?P<os>[^.]*)\\.(?P<type>.*)$"

log = logging.getLogger("bring")


class GithubRelease(HttpDownloadPkgResolver):
    def __init__(self):

        super().__init__()

    def _supports(self) -> List[str]:

        return ["github-release"]

    def get_unique_source_id(self, source_details: Dict) -> str:

        github_user = source_details.get("user_name")
        repo_name = source_details.get("repo_name")

        artefact_name = source_details.get("artefact_name", "")

        if artefact_name:
            artefact_name = f"_{artefact_name}"

        return f"{github_user}_{repo_name}{artefact_name}"

    async def _retrieve_versions(
        self, source_details: Union[str, Dict]
    ) -> List[Dict[str, str]]:

        github_user = source_details.get("user_name")
        repo_name = source_details.get("repo_name")

        repo_url = f"https://api.github.com/repos/{github_user}/{repo_name}/releases"

        async with httpx.AsyncClient() as client:
            r = await client.get(repo_url)
            releases = r.json()

        # import pp
        # pp(releases)
        url_regexes = source_details.get("url_regex", None)
        if not url_regexes:
            url_regexes = DEFAULT_URL_REGEXES
        elif isinstance(url_regexes, str):
            url_regexes = [url_regexes]

        log.info(f"Regexes for {github_user}/{repo_name}: {url_regexes}")
        result = []
        aliases = {}
        for release in releases:

            version_data = self.parse_release_data(release, url_regexes, aliases)
            if version_data:
                result.extend(version_data)

        return result, aliases

    def parse_release_data(
        self, data: Dict, url_regexes: List, aliases: Dict
    ) -> Union[Tuple[List[Dict], Dict], List[Dict]]:

        result = []

        version = data["name"]
        prerelease = data["prerelease"]
        created_at = data["created_at"]
        tarball_url = data["tarball_url"]
        zipball_url = data["zipball_url"]

        meta = {
            "orig_version_name": version,
            "prerelease": prerelease,
            "source_tarball_url": tarball_url,
            "source_zipball_url": zipball_url,
            "release_date": created_at,
        }

        for asset in data["assets"]:
            browser_download_url = asset["browser_download_url"]
            log.info(f"trying url: {browser_download_url}")
            vars = None
            for regex in url_regexes:
                match = re.search(regex, browser_download_url)

                if match is not None:
                    vars = match.groupdict()
                    break

            if vars is None:
                log.info("No match")
                continue

            missing = []
            for k, v in vars.items():
                if v is None:
                    missing.append(k)
            for m in missing:
                vars.pop(m)
            log.info(f"Matched vars: {vars}")

            if "version" in vars.keys():
                vers = vars["version"]
                if not prerelease:
                    if "stable" not in aliases.setdefault("version", {}).keys():
                        aliases["version"]["stable"] = vers
                    if "latest" not in aliases.setdefault("version", {}).keys():
                        aliases["version"]["latest"] = vers
                else:
                    if "pre-release" not in aliases.setdefault("version", {}).keys():
                        aliases["version"]["pre-release"] = vers

            asset_name = asset["name"]
            content_type = asset["content_type"]
            size = asset["size"]

            m = copy.copy(meta)
            m["asset_name"] = asset_name
            m["content_type"] = content_type
            m["size"] = size
            m["url"] = browser_download_url
            vars["_meta"] = m

            result.append(vars)

        return result

    def get_download_url(self, version: Dict[str, str], source_details: Dict):

        return version["_meta"]["url"]
