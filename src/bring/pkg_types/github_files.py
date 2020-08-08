# -*- coding: utf-8 -*-
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional

from bring.pkg_types import PkgType, PkgVersion
from bring.utils.github import get_list_data_from_github
from deepdiff import DeepHash


class GitFiles(PkgType):

    _plugin_name: str = "github_files"
    _plugin_supports: str = "github_files"

    def __init__(self, **config: Any):

        self._github_username = config.get("github_username", None)
        self._github_token = config.get("github_access_token", None)

        super().__init__(**config)

    def get_args(self) -> Mapping[str, Any]:

        return {
            "user_name": {
                "type": "string",
                "required": True,
                "doc": "The github user name.",
            },
            "repo_name": {
                "type": "string",
                "required": True,
                "doc": "The github repo name.",
            },
            "files": {"type": "list", "doc": "The list of files to retrieve."},
            "tag_filter": {
                "type": "string",
                "required": False,
                "doc": "if provided, is used as regex to select wanted tags",
            },
            # "use_commits_as_versions": {
            #     "type": "boolean",
            #     "required": False,
            #     "default": False,
            #     "doc": "Whether to use commit hashes as version strings.",
            # },
        }

    def _get_unique_source_type_id(self, source_details: Mapping) -> str:

        github_user = source_details.get("user_name")
        repo_name = source_details.get("repo_name")
        files: Iterable[str] = source_details.get("files")  # type: ignore

        files = sorted(files)

        hashes = DeepHash(files)
        hash_str = hashes[files]

        return f"{github_user}_{repo_name}_{hash_str}"

    # def get_artefact_mogrify(
    #     self, source_details: Mapping[str, Any], version: PkgVersion
    # ) -> Union[Mapping, Iterable]:
    #
    #     return {"type": "folder"}

    async def _process_pkg_versions(self, source_details: Mapping) -> Mapping[str, Any]:

        github_user: str = source_details.get("user_name")  # type: ignore
        repo_name: str = source_details.get("repo_name")  # type: ignore
        tag_filter: str = source_details.get("tag_filter", None)  # type: ignore

        use_commits = source_details.get("use_commits_as_versions", False)
        files = source_details["files"]

        if use_commits:
            raise NotImplementedError("'use_commits_as_versions' is not supprted yet.")

        request_path = f"/repos/{github_user}/{repo_name}/tags"

        tags = await get_list_data_from_github(
            path=request_path,
            github_username=self._github_username,
            github_token=self._github_token,
        )

        request_path = f"/repos/{github_user}/{repo_name}/branches"
        branches = await get_list_data_from_github(
            path=request_path,
            github_username=self._github_username,
            github_token=self._github_token,
        )

        latest: Optional[str] = None
        versions: List[PkgVersion] = []

        tag_names: List[str] = []
        for tag in tags:
            name = tag["name"]
            if tag_filter:
                if not re.match(tag_filter, name):
                    continue
            tag_names.append(name)

        for tag_name in tag_names:

            if latest is None:
                latest = tag_name

            _v = create_pkg_version(
                user_name=github_user,
                repo_name=repo_name,
                version=tag_name,
                files=files,
            )
            versions.append(_v)

        branch_names: List[str] = []
        for b in branches:
            branch_names.append(b["name"])

        if "master" in branch_names:
            if latest is None:
                latest = "master"

            _v = create_pkg_version(
                user_name=github_user,
                repo_name=repo_name,
                version="master",
                files=files,
            )
            versions.append(_v)

        for branch in branch_names:
            if branch == "master":
                continue
            if latest is None:
                latest = branch

            _v = create_pkg_version(
                user_name=github_user, repo_name=repo_name, version=branch, files=files
            )
            versions.append(_v)

        result: Dict[str, Any] = {"versions": versions}

        if latest is not None:
            aliases: Dict[str, Any] = {"version": {}}
            aliases["version"]["latest"] = latest
            result["aliases"] = aliases

        return result


def create_pkg_version(
    user_name: str, repo_name: str, version: str, files: Iterable[str]
) -> PkgVersion:

    urls = []
    for f in files:
        dl = {
            "url": f"https://raw.githubusercontent.com/{user_name}/{repo_name}/{version}/{f}",
            "target": f,
        }
        urls.append(dl)

    _v = PkgVersion(
        [{"type": "download_multiple_files", "urls": urls}],
        vars={"version": version},
        metadata={},
    )
    return _v
