# -*- coding: utf-8 -*-
import os
import shutil

from bring.defaults import BRING_GIT_CHECKOUT_CACHE
from frkl.common.downloads.cache import calculate_cache_path
from frkl.common.filesystem import ensure_folder
from frkl.common.strings import generate_valid_identifier
from frkl.common.subprocesses import GitProcess


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
        # clone to a temp location first, in case another process tries to do the same
        temp_name = generate_valid_identifier()
        temp_path = os.path.join(parent_folder, temp_name)
        git = GitProcess(
            "clone", url, temp_path, working_dir=parent_folder, GIT_TERMINAL_PROMPT="0"
        )

        await git.run(wait=True)

        if os.path.exists(path):
            shutil.rmtree(temp_path, ignore_errors=True)
        else:
            shutil.move(temp_path, path)

    else:
        # TODO: some sort of lock?
        git = GitProcess("fetch", working_dir=path)

        await git.run(wait=True)

    return path
