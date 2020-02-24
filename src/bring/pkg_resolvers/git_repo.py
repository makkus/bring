# -*- coding: utf-8 -*-
import os
import tempfile
from collections import OrderedDict
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional

import git
from bring.context import BringContextTing
from bring.pkg_resolvers import SimplePkgResolver
from frtls.downloads import calculate_cache_path
from frtls.files import ensure_folder
from frtls.subprocesses.git import GitProcess
from pydriller import Commit, GitRepository


class GitRepo(SimplePkgResolver):

    _plugin_name: str = "git"

    def __init__(self, config: Optional[Mapping[str, Any]] = None):

        super().__init__(config=config)

    def _name(self):

        return "git"

    def _supports(self) -> Iterable[str]:
        return ["git"]

    def get_unique_source_id(
        self, source_details: Mapping, bring_context: BringContextTing
    ) -> str:

        return source_details["url"]

    def get_artefact_defaults(self, source_details: Mapping) -> Mapping[str, Any]:
        return {"type": "folder"}

    async def _ensure_repo_cloned(self, path, url, update=False):

        parent_folder = os.path.dirname(path)

        exists = False
        if os.path.exists(path):
            exists = True

        if exists and not update:
            return

        ensure_folder(parent_folder)

        if not exists:

            git = GitProcess(
                "clone", url, path, working_dir=parent_folder, GIT_TERMINAL_PROMPT="0"
            )

        else:
            git = GitProcess("fetch", working_dir=path)

        await git.run(wait=True)

    async def _process_pkg_versions(
        self, source_details: Mapping, bring_context: BringContextTing
    ) -> Mapping[str, Any]:

        cache_path = calculate_cache_path(
            base_path=self._cache_dir, url=source_details["url"]
        )

        await self._ensure_repo_cloned(
            path=cache_path, url=source_details["url"], update=True
        )

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
            versions.append({"version": k, "_meta": {"release_date": timestamp}})

        if "master" in branches.keys():
            c = commits[branches["master"].hexsha]
            timestamp = str(c.author_date)
            versions.append({"version": "master", "_meta": {"release_date": timestamp}})
        for b in branches.keys():
            if b == "master":
                continue
            if branches[b].hexsha not in commits.keys():
                await self._update_commits(gr, commits, b)
            c = commits[branches[b].hexsha]
            timestamp = str(c.author_date)
            versions.append({"version": b, "_meta": {"release_date": timestamp}})

        if source_details.get("use_commits_as_versions", False):
            for c_hash, c in commits.items():
                timestamp = str(c.author_date)
                versions.append(
                    {"version": c_hash, "_meta": {"release_date": timestamp}}
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

    async def get_artefact_path(
        self, version: Dict[str, str], source_details: Dict[str, Any]
    ):

        cache_path = calculate_cache_path(
            base_path=self._cache_dir, url=source_details["url"]
        )

        temp_path = os.path.join(self._cache_dir, "tmp_artefact_folders")
        ensure_folder(temp_path)
        tempdir = tempfile.mkdtemp(dir=temp_path)

        clone_cmd = GitProcess("clone", cache_path, tempdir)
        await clone_cmd.run()
        checkout_cmd = GitProcess("checkout", version["version"], working_dir=tempdir)
        await checkout_cmd.run()

        return tempdir
