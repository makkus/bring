# -*- coding: utf-8 -*-
import logging

import asyncclick as click
from bring.bring import Bring
from frtls.cli.exceptions import handle_exc_async


log = logging.getLogger("bring")


@click.group()
@click.pass_context
def config(ctx):
    """Helper tasks for development.

    """

    pass


@config.command()
@click.pass_context
@handle_exc_async
async def show(ctx):
    """Clear the bring cache dir in the relevant locaiont (e.g. '~/.cache/bring' on Linux)."""

    bring: Bring = ctx.obj["bring"]

    config = await bring.get_config_dict()

    print(config)

    bring.set_config("test2")
    config = await bring.get_config_dict()

    print(config)
