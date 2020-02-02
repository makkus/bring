# -*- coding: utf-8 -*-

import asyncclick as click

# from click import Path
# from click_aliases import ClickAliasedGroup
from asyncclick import Path

from bring.bring import Bringistry
from frtls.cli.exceptions import handle_exc
from frtls.cli.logging import logzero_option_async
from tings.tingistry import TingistryTingistry

click.anyio_backend = "asyncio"


# @click.group(cls=ClickAliasedGroup)
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

    bringistry = TingistryTingistry().add_tingistry(
        "bring", tingistry_class="bringistry", paths=base_path
    )
    ctx.obj["bringistry"] = bringistry


@cli.command(name="list")
@click.pass_context
@handle_exc
async def list_packages(ctx):

    bringistry: Bringistry = ctx.obj["bringistry"]
    bringistry.sync()
    # print(bt)
    for v in bringistry.pkg_tings.tings.values():

        vals = await v.get_values("versions")
        print(vals)


# @cli.command(name="watch")
# @click.option("--property", "-p", multiple=True)
# @click.pass_context
# async def watch(ctx, property):
#
#     bring_repo: Bringistry = ctx.obj["bring_repo"]
#
#     await bring_repo.watch()
#
# # @cli.command(name="install", aliases=["in"])
# # @click.pass_context
# # @handle_exc
# # def install(ctx):
# #
# #     print("HH")


if __name__ == "__main__":
    cli()
