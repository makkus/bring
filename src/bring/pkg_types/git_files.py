# -*- coding: utf-8 -*-
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Union

from bring.pkg_types import PkgType, PkgVersion
from frkl.common.subprocesses import GitProcess


class GitFiles(PkgType):

    _plugin_name: str = "git_files"
    _plugin_supports: str = "git_files"

    def __init__(self, **config: Any):

        super().__init__(**config)

    def get_args(self) -> Mapping[str, Any]:

        return {
            "url": {"type": "string", "required": True, "doc": "The git repo url."},
            "tag_filter": {
                "type": "string",
                "required": False,
                "doc": "if provided, is used as regex to select wanted tags",
            }
            # "use_commits_as_versions": {
            #     "type": "boolean",
            #     "required": False,
            #     "default": False,
            #     "doc": "Whether to use commit hashes as version strings.",
            # },
        }

    def _get_unique_source_type_id(self, source_details: Mapping) -> str:

        return source_details["url"]

    def get_artefact_mogrify(
        self, source_details: Mapping[str, Any], version: PkgVersion
    ) -> Union[Mapping, Iterable]:

        return {"type": "archive"}

    async def _process_pkg_versions(self, source_details: Mapping) -> Mapping[str, Any]:

        url = source_details["url"]
        tag_filter = source_details.get("tag_filter", None)
        use_commits = source_details.get("use_commits_as_versions", False)
        files = source_details["files"]

        if use_commits:
            raise NotImplementedError("'use_commits_as_versions' is not supprted yet.")

        git = GitProcess(
            "-c",
            "versionsort.suffix=-",
            "ls-remote",
            "--tags",
            "--heads",
            "--sort=v:refname",
            url,
            GIT_TERMINAL_PROMPT="0",
        )

        await git.run(wait=True)

        stdout = await git.stdout

        heads = []
        tags = []

        for line in stdout.split("\n"):
            i = line.find("refs/")
            version = line[i + 5 :]  # noqa
            if version.startswith("heads/"):
                head = version[6:]
                heads.append(head)
            elif version.startswith("tags/"):
                tag = version[5:]
                if tag_filter:
                    if not re.match(tag_filter, tag):
                        continue
                tags.append(tag)

        latest: Optional[str] = None

        versions: List[PkgVersion] = []

        for t in reversed(tags):
            if latest is None:
                latest = t
            _v = PkgVersion(
                [
                    {
                        "type": "git_archive",
                        "url": source_details["url"],
                        "version": t,
                        "files": files,
                    }
                ],
                vars={"version": t},
                metadata={},
            )
            versions.append(_v)

        if "master" in heads:

            if latest is None:
                latest = "master"

            _v = PkgVersion(
                [
                    {
                        "type": "git_archive",
                        "url": source_details["url"],
                        "version": "master",
                        "files": files,
                    }
                ],
                vars={"version": "master"},
                metadata={},
            )
            versions.append(_v)

        for h in heads:
            if h == "master":
                continue

            _v = PkgVersion(
                [
                    {
                        "type": "git_archive",
                        "url": source_details["url"],
                        "version": h,
                        "files": files,
                    }
                ],
                vars={"version": h},
                metadata={},
            )
            versions.append(_v)

        result: Dict[str, Any] = {"versions": versions}

        if latest is not None:
            aliases: Dict[str, Any] = {"version": {}}
            aliases["version"]["latest"] = latest
            result["aliases"] = aliases

        return result
