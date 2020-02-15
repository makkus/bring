# -*- coding: utf-8 -*-

import asyncclick as click
from asyncclick import Path

from bring.bring import Bringistry
from bring.interfaces.cli.info import BringInfoGroup
from bring.interfaces.cli.install import BringInstallGroup
from bring.interfaces.cli.profile import BringProfileGroup
from frtls.cli.logging import logzero_option_async

click.anyio_backend = "asyncio"

bringistry = Bringistry()

# import uvloop
# uvloop.install()


@click.group()
@click.option(
    "--base-path",
    "-p",
    help="A path where to look for '*.bring' files.",
    multiple=True,
    type=Path(
        exists=True, file_okay=True, dir_okay=True, readable=True, allow_dash=False
    ),
)
@logzero_option_async()
@click.pass_context
async def cli(ctx, base_path):

    ctx.obj = {}
    ctx.obj["base_paths"] = base_path

    bringistry._bring_maker.add_base_paths(*base_path)
    await bringistry._bring_maker.sync()

    ctx.obj["bringistry"] = bringistry


install = BringInstallGroup(bringistry, name="install")
cli.add_command(install)

info = BringInfoGroup(bringistry, name="info")
cli.add_command(info)

profile = BringProfileGroup(name="profile")
cli.add_command(info)


if __name__ == "__main__":
    cli()
