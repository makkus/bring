# -*- coding: utf-8 -*-
import os
from collections import OrderedDict
from pathlib import Path
from typing import Union, List, Dict, Any

from pydriller import GitRepository

from bring.defaults import BRING_PKG_CACHE
from bring.pkg_resolvers import PkgResolver
from frtls.downloads import calculate_cache_path
from frtls.files import ensure_folder
from frtls.subprocesses.git import GitProcess


class GitRepo(PkgResolver):
    def __init__(self, cache_dir: Union[str, Path] = None):

        if cache_dir is None:
            cache_dir = BRING_PKG_CACHE

        if isinstance(cache_dir, str):
            cache_dir = Path(cache_dir)

        self._cache_dir = cache_dir.resolve()
        ensure_folder(self._cache_dir, mode=0o700)

    def get_resolver_name(self):

        return "git"

    def get_supported_source_types(self) -> List[str]:
        return ["git"]

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

    async def _get_versions(
        self, source_details: Union[str, Dict], update=True
    ) -> Dict[str, Any]:

        if isinstance(source_details, str):
            tmp = {}
            tmp["url"] = source_details
            source_details = tmp

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
        for k in tags.keys():
            # c = commits[v.hexsha]
            # timestamp = str(c.author_date)
            # versions[k] = {"commit": c.hash, "timestamp": timestamp}
            versions.append(k)
        for b in branches.keys():
            versions.append(b)

        return {"version": versions}
