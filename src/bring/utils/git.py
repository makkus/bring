# -*- coding: utf-8 -*-
import os

from bring.defaults import BRING_GIT_CHECKOUT_CACHE
from frtls.downloads import calculate_cache_path
from frtls.files import ensure_folder
from frtls.subprocesses.git import GitProcess


async def ensure_repo_cloned(url, update=False) -> str:

    path = calculate_cache_path(base_path=BRING_GIT_CHECKOUT_CACHE, url=url)
    parent_folder = os.path.dirname(path)

    exists = False
    if os.path.exists(path):
        exists = True

    if exists and not update:
        return path

    ensure_folder(parent_folder)

    if not exists:

        git = GitProcess(
            "clone", url, path, working_dir=parent_folder, GIT_TERMINAL_PROMPT="0"
        )

    else:
        git = GitProcess("fetch", working_dir=path)

    await git.run(wait=True)

    return path
