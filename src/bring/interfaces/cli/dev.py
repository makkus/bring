# -*- coding: utf-8 -*-
import logging
import shutil

import asyncclick as click
from bring.defaults import BRING_APP_DIRS


log = logging.getLogger("bring")


@click.group()
@click.pass_context
def dev(ctx):
    """Helper tasks for development.

    """

    pass


@dev.command()
@click.pass_context
def clear_cache(ctx):
    """Clear the bring cache dir in the relevant locaiont (e.g. '~/.cache/bring' on Linux)."""

    shutil.rmtree(BRING_APP_DIRS.user_cache_dir, ignore_errors=True)
