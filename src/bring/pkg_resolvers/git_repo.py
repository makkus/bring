# -*- coding: utf-8 -*-
import os
import tempfile
from collections import OrderedDict
from typing import List, Dict, Any

from pydriller import GitRepository

from bring.pkg_resolvers import SimplePkgResolver
from frtls.downloads import calculate_cache_path
from frtls.files import ensure_folder
from frtls.subprocesses.git import GitProcess


class GitRepo(SimplePkgResolver):
    def __init__(self):

        super().__init__()

    def get_resolver_name(self):

        return "git"

    def get_supported_source_types(self) -> List[str]:
        return ["git"]

    def get_unique_source_id(self, source_details: Dict) -> str:

        return source_details["url"]

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

    async def _retrieve_versions(
        self, source_details: Dict, update=True
    ) -> List[Dict[str, str]]:

        cache_path = calculate_cache_path(
            base_path=self._cache_dir, url=source_details["url"]
        )

        update = False
        await self._ensure_repo_cloned(
            path=cache_path, url=source_details["url"], update=update
        )

        gr = GitRepository(cache_path)
        commits = OrderedDict()
        tags = OrderedDict()
        branches = OrderedDict()

        for c in gr.get_list_commits():
            commits[c.hash] = c

        for t in gr.repo.tags:
            tags[t.name] = t.commit

        for b in gr.repo.branches:
            branches[b.name] = b.commit

        versions = []
        if "master" in branches.keys():
            c = commits[branches["master"].hexsha]
            timestamp = str(c.author_date)
            versions.append({"version": "master", "_meta": {"release_date": timestamp}})
        for b in branches.keys():
            if b == "master":
                continue
            c = commits[branches[b].hexsha]
            timestamp = str(c.author_date)
            versions.append({"version": b, "_meta": {"release_date": timestamp}})

        for k in tags.keys():

            c = commits[tags[k].hexsha]
            timestamp = str(c.author_date)
            versions.append({"version": k, "_meta": {"release_date": timestamp}})

        return versions

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
