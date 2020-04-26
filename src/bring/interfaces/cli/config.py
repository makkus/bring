# -*- coding: utf-8 -*-
import logging

import asyncclick as click
from bring.bring import Bring
from bring.config import BringConfig
from frtls.cli.exceptions import handle_exc_async
from frtls.formats.output_formats import serialize
from tings.tingistry import Tingistries


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
async def list(ctx):
    """List all available config profiles."""

    bring: Bring = ctx.obj["bring"]

    profiles = await bring.config.get_all_context_configs()

    print(profiles)


@config.command()
@click.pass_context
@handle_exc_async
async def show(ctx):
    """Clear the bring cache dir in the relevant location (e.g. '~/.cache/bring' on Linux)."""

    # bring: Bring = ctx.obj["bring"]
    #
    # config = await bring.get_config_dict()
    #
    # print(config)
    tingistry_obj = Tingistries.create("bring")

    bring_config = BringConfig(tingistry_obj)

    # pp(bring_config.__dict__)
    c = await bring_config.get_config_dict()
    print("---")
    print(serialize(c, format="yaml"))
