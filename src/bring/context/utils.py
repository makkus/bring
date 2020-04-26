# -*- coding: utf-8 -*-
import collections
import os
from pathlib import Path
from typing import Any, Iterable

from bring.context import (
    BringContextTing,
    BringDynamicContextTing,
    BringStaticContextTing,
)
from bring.defaults import BRING_CONTEXT_NAMESPACE
from bring.utils.contexts import validate_context_name
from frtls.exceptions import FrklException
from frtls.formats.input_formats import INPUT_FILE_TYPE, determine_input_file_type
from tings.tingistry import Tingistry


async def create_context(
    tingistry_obj: Tingistry, name: str, **config: Any
) -> BringContextTing:

    context_type = config.pop("type", "auto")

    if context_type == "auto":
        raise NotImplementedError()

    if context_type == "folder":
        folder = config.get("indexes", None)
        if folder is None:
            raise FrklException(
                msg=f"Can't create bring context '{name}' from folder.",
                reason="'indexes' config value missing.",
            )
        if isinstance(folder, str):
            folder = [folder]
            config["indexes"] = folder

        ctx: BringContextTing = await create_context_from_folder(
            tingistry_obj=tingistry_obj, context_name=name, **config
        )

    elif context_type == "index":

        index_files = config.get("indexes", None)
        if index_files is None or not isinstance(index_files, collections.Iterable):
            raise FrklException(
                msg=f"Can't create bring context '{name}' from index.",
                reason="'index_file' config value missing or invalid.",
            )
        if isinstance(index_files, str):
            config["indexes"] = [index_files]

        ctx = await create_context_from_index(
            tingistry_obj=tingistry_obj, context_name=name, **config
        )

    else:
        raise FrklException(
            msg=f"Can't create bring context '{name}'.",
            reason=f"Context type '{context_type}' not supported.",
        )

    return ctx


async def create_context_from_index(
    tingistry_obj: Tingistry, context_name: str, indexes: Iterable[str], **config: Any
) -> BringStaticContextTing:

    # if self._contexts.get(context_name, None) is not None:
    #     raise FrklException(
    #         msg=f"Can't add context '{context_name}'.",
    #         reason="Default context with that name already exists.",
    #     )

    ctx: BringStaticContextTing = tingistry_obj.create_ting(  # type: ignore
        "bring.types.contexts.default_context",
        f"{BRING_CONTEXT_NAMESPACE}.{context_name}",
    )

    ctx_config = dict(config)
    ctx_config["indexes"] = indexes

    ctx.input.set_values(ting_dict=ctx_config)
    await ctx.get_values("config")

    return ctx


async def create_context_from_folder(
    tingistry_obj: Tingistry, context_name: str, indexes: Iterable[str], **config: Any
) -> BringDynamicContextTing:

    # if self._contexts.get(context_name, None) is not None:
    #     raise FrklException(
    #         msg=f"Can't add context '{context_name}'.",
    #         reason="Default context with that name already exists.",
    #     )

    indexes = list(indexes)
    if len(indexes) != 1:
        raise NotImplementedError()

    folder = indexes[0]
    input_type = determine_input_file_type(folder)

    # if input_type == INPUT_FILE_TYPE.git_repo:
    #     git_url = expand_git_url(path, DEFAULT_URL_ABBREVIATIONS_GIT_REPO)
    #     _path = await ensure_repo_cloned(git_url)
    if input_type == INPUT_FILE_TYPE.local_dir:
        if isinstance(folder, Path):
            _path: str = os.path.realpath(folder.resolve().as_posix())
        else:
            _path = os.path.realpath(os.path.expanduser(folder))
    else:
        raise FrklException(
            msg=f"Can't add context for: {folder}.",
            reason=f"Invalid input file type {input_type}.",
        )

    validate_context_name(context_name)
    ctx: BringDynamicContextTing = tingistry_obj.create_ting(  # type: ignore
        "bring_dynamic_context_ting", f"{BRING_CONTEXT_NAMESPACE}.{context_name}"
    )
    _ind = [_path]
    ctx_config = dict(config)
    ctx_config["indexes"] = _ind
    ctx.input.set_values(  # type: ignore
        ting_dict=ctx_config
    )

    await ctx.get_values("config")

    return ctx
