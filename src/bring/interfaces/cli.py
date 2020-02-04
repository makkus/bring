# -*- coding: utf-8 -*-

import asyncclick as click

# from click import Path
# from click_aliases import ClickAliasedGroup
from asyncclick import Path

from bring.bring import Bringistry
from frtls.cli.exceptions import handle_exc
from frtls.cli.logging import logzero_option_async
from tings.tingistry import Tingistries

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

    bringistry = Tingistries().add_tingistry(
        "bring", tingistry_class="bringistry", paths=base_path
    )
    ctx.obj["bringistry"] = bringistry


@cli.command(name="list")
@click.pass_context
@handle_exc
async def list_packages(ctx):

    bringistry: Bringistry = ctx.obj["bringistry"]

    path = "/home/markus/projects/tings/bring/repos/simple/"
    # bringistry._pkg_source.seeds._add_seed(seed_id=path, seed={"path": path})
    # await bringistry._pkg_source.sync()
    # pp(await bringistry._pkg_source.get_values())

    bringistry._pkg_source.source.add_base_path(path)

    # await bringistry.sync()
    # import pp
    # for v in bringistry.pkg_tings.tings.values():
    #     vals = await v.get_values()
    #     print('---')
    #     pp(vals)

    # def listener(source, event_type, event_details, topic=pub.AUTO_TOPIC):
    #     print("----")
    #     print(topic.getName())
    #     print(event_type)
    #     print(source)
    #
    #     loop = asyncio.get_event_loop()
    #     async def vals():
    #         for v in bringistry.pkg_tings.tings.values():
    #             va = await v.get_values()
    #             pp(va)
    #     loop.create_task(vals())
    #
    #
    # pub.subscribe(listener, "bring")
    #
    # ctx.obj["listener"] = listener

    await bringistry._pkg_source.watch()


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
