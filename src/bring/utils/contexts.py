# -*- coding: utf-8 -*-
import logging
import os
from typing import TYPE_CHECKING

from bring.utils.git import ensure_repo_cloned
from frtls.defaults import DEFAULT_URL_ABBREVIATIONS_GIT_REPO
from frtls.strings import expand_git_url, is_url_or_abbrev
from frtls.types.utils import generate_valid_identifier


if TYPE_CHECKING:
    from bring.bring import Bring

log = logging.getLogger("bring")


# TODO: implement
def validate_context_name(name: str):

    pass


async def ensure_context(bring: "Bring", name: str) -> str:

    context = bring.get_context(name, raise_exception=False)

    if context is None:

        if is_url_or_abbrev(name, DEFAULT_URL_ABBREVIATIONS_GIT_REPO):

            git_url = expand_git_url(name, DEFAULT_URL_ABBREVIATIONS_GIT_REPO)
            full_path = await ensure_repo_cloned(git_url, update=True)
        else:
            full_path = os.path.realpath(os.path.expanduser(name))

        _ctx_name = generate_valid_identifier(full_path, sep="_")
        if os.path.isdir(full_path):
            await bring.add_extra_context(
                name=_ctx_name, type="folder", folder=full_path
            )
        elif full_path.endswith(".bx"):
            await bring.add_extra_context(
                name=_ctx_name, type="index", index_file=full_path
            )
    else:
        _ctx_name = name

    return _ctx_name
