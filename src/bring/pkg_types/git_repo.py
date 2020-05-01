# -*- coding: utf-8 -*-
from collections import OrderedDict
from typing import Any, Iterable, Mapping, MutableMapping

import git
from bring.pkg_index import BringIndexTing
from bring.pkg_types import SimplePkgType
from bring.utils.git import ensure_repo_cloned
from pydriller import Commit, GitRepository


class GitRepo(SimplePkgType):

    _plugin_name: str = "git"

    def __init__(self, **config: Any):

        super().__init__(**config)

    def _name(self):

        return "git"

    def _supports(self) -> Iterable[str]:
        return ["git"]

    def get_args(self) -> Mapping[str, Any]:

        return {"url": {"type": "string", "required": True, "doc": "The git repo url."}}

    def get_unique_source_id(
        self, source_details: Mapping, bring_index: BringIndexTing
    ) -> str:

        return source_details["url"]

    async def _process_pkg_versions(
        self, source_details: Mapping, bring_index: BringIndexTing
    ) -> Mapping[str, Any]:

        cache_path = await ensure_repo_cloned(url=source_details["url"], update=True)

        gr = GitRepository(cache_path)
        commits: MutableMapping[str, Commit] = OrderedDict()
        tags: MutableMapping[str, git.objects.commit.Commit] = OrderedDict()
        branches: MutableMapping[str, git.objects.commit.Commit] = OrderedDict()

        for c in gr.get_list_commits():
            commits[c.hash] = c

        for t in gr.repo.tags:
            tags[t.name] = t.commit

        for b in gr.repo.branches:
            branches[b.name] = b.commit

        versions = []
        for k in sorted(tags.keys(), reverse=True):

            if tags[k].hexsha not in commits.keys():
                await self._update_commits(gr, commits, k)
            c = commits[tags[k].hexsha]
            timestamp = str(c.author_date)
            versions.append(
                {
                    "version": k,
                    "_meta": {"release_date": timestamp},
                    "_mogrify": [
                        {
                            "type": "git_clone",
                            "url": source_details["url"],
                            "version": k,
                        }
                    ],
                }
            )

        if "master" in branches.keys():
            c = commits[branches["master"].hexsha]
            timestamp = str(c.author_date)
            versions.append(
                {
                    "version": "master",
                    "_meta": {"release_date": timestamp},
                    "_mogrify": [
                        {
                            "type": "git_clone",
                            "url": source_details["url"],
                            "version": "master",
                        }
                    ],
                }
            )
        for b in branches.keys():
            if b == "master":
                continue
            if branches[b].hexsha not in commits.keys():
                await self._update_commits(gr, commits, b)
            c = commits[branches[b].hexsha]
            timestamp = str(c.author_date)
            versions.append(
                {
                    "version": b,
                    "_meta": {"release_date": timestamp},
                    "_mogrify": [
                        {
                            "type": "git_clone",
                            "url": source_details["url"],
                            "version": b,
                        }
                    ],
                }
            )

        if source_details.get("use_commits_as_versions", False):
            for c_hash, c in commits.items():
                timestamp = str(c.author_date)
                versions.append(
                    {
                        "version": c_hash,
                        "_meta": {"release_date": timestamp},
                        "_mogrify": [
                            {
                                "type": "git_clone",
                                "url": source_details["url"],
                                "version": c_hash,
                            }
                        ],
                    }
                )

        return {"versions": versions}

    async def _update_commits(
        self,
        git_repo: GitRepository,
        current_commits: MutableMapping,
        checkout_point: str,
    ) -> None:

        for c in git_repo.get_list_commits(branch=checkout_point):
            if c.hash not in current_commits.keys():
                current_commits[c.hash] = c
