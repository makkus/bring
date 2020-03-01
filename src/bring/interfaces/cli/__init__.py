# -*- coding: utf-8 -*-
import sys

import asyncclick as click
from blessings import Terminal
from bring.bring import Bring
from bring.interfaces.cli.command_group import BringCommandGroup
from frtls.cli.exceptions import handle_exc_async
from frtls.cli.logging import logzero_option_async


click.anyio_backend = "asyncio"


# uvloop.install()

bring_obj: Bring = Bring("bring")

terminal = Terminal()


@click.command(name="bring", cls=BringCommandGroup, bring=bring_obj, terminal=terminal)
@logzero_option_async()
@click.pass_context
@handle_exc_async
async def cli_func(ctx, *args, **kwargs):

    await bring_obj.init()

    if ctx.invoked_subcommand:
        return

    # print_formatted_text('Hello world')


def cli():

    return cli_func()


if __name__ == "__main__":
    cli()

if getattr(sys, "frozen", False):
    cli(sys.argv[1:])
