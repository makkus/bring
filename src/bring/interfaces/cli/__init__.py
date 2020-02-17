# -*- coding: utf-8 -*-
import sys

import asyncclick as click
import uvloop
from bring.bring import Bring
from bring.interfaces.cli.command_group import BringCommandGroup
from frtls.cli.logging import logzero_option_async


uvloop.install()
click.anyio_backend = "asyncio"

bring_obj: Bring = Bring("bring")


@click.command(name="bring", cls=BringCommandGroup, bring=bring_obj)
@logzero_option_async()
@click.pass_context
# @handle_exc_async
async def cli(ctx, *args, **kwargs):

    await bring_obj.init()

    if ctx.invoked_subcommand:
        return

    print("XXX")

    # ctx.obj = {}
    # ctx.obj["bringistry"] = bring_obj
    # await bring_obj.init()


# cli = BringCommandGroup(bring=bring_obj)


# contexts = BringContextGroup(bring_obj, name="context")
# cli.add_command(contexts)
# install = BringInstallGroup(bring_obj, name="install")
# cli.add_command(install)

# info = BringInfoGroup(bring_obj, name="info")
# cli.add_command(info)

# profile = BringProfileGroup(name="profile")
# cli.add_command(info)


if __name__ == "__main__":
    cli()

if getattr(sys, "frozen", False):
    cli(sys.argv[1:])
