# -*- coding: utf-8 -*-

import asyncclick as click

from asyncclick import Path

from bring.bring import Bringistry

# from bring.interfaces.cli.info import BringInfoGroup
# from bring.interfaces.cli.install import BringInstallGroup
# from bring.interfaces.cli.profile import BringProfileGroup
from frtls.cli.exceptions import handle_exc
from frtls.cli.logging import logzero_option_async
from tings.makers.file import TextFileTingMaker
from tings.tingistry import Tingistries

click.anyio_backend = "asyncio"


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

    bringistry = Tingistries().add_tingistry("bring", tingistry_class="bringistry")
    ctx.obj["bringistry"] = bringistry

    path = "/home/markus/projects/tings/repos/executables/"
    ctx.obj["path"] = path
    # bringistry.set_source("bring.bring_file_source")
    # bringistry.source.add_source_items(path)
    # await bringistry.source.sync()


# install = BringInstallGroup(name="install")
# cli.add_command(install)
#
# info = BringInfoGroup(name="info")
# cli.add_command(info)
#
# profile = BringProfileGroup(name="profile")
# cli.add_command(info)


@cli.command(name="test")
@click.pass_context
@handle_exc
async def test(ctx):

    # path = ctx.obj["path"]
    bringistry: Bringistry = ctx.obj["bringistry"]

    # tings = bringistry.create_ting("test_tings", type_name="bring.pkgs")

    # def handle(event_name, source, subject, event_details):
    # def handle(**subject):
    #     print(subject)

    # bringistry.subscribe_to_tingistry_event(handle, TingistryEvent.TING_CREATED, ting_type="bring.bring_pkg_metadata")

    # hive = bringistry._arg_hive

    # arg_dict = {"type": "boolean", "properties": {"doc": "whatever", "required": False}}

    # arg = hive.create_derived_arg(id="docker", **arg_dict)

    ting_maker = TextFileTingMaker(
        ting_type="bring.bring_pkg_metadata", tingistry=bringistry
    )

    await ting_maker.add_file(
        "/home/markus/projects/tings/repos/executables/terminal/system/info/ytop.bring",
        "testxxx",
    )
    # await ting_maker.add_file('https://gitlab.com/tingistries/executables/-/raw/master/system/install/languages/eclectica-proxy.bring')
    print(ting_maker._ids)
    print(ting_maker._tings)
    bringistry._tings_tree.show()

    await ting_maker.remove_ting(
        "/home/markus/projects/tings/repos/executables/terminal/system/info/ytop.bring"
    )
    print(ting_maker._ids)
    print(ting_maker._tings)
    bringistry._tings_tree.show()
    print("Xxxxx")
    # vars = {}
    # pkg = bringistry.get_pkg("kubectl")
    # print(pkg)
    #
    # profile = bringistry.get_transform_profile("executables")
    # print(profile)
    #
    # result = await pkg.install(vars={}, profiles=["executables"], target="/tmp/markus")
    #
    # print(result)


@cli.command(name="list")
@click.pass_context
@handle_exc
async def list_packages(ctx):

    bringistry: Bringistry = ctx.obj["bringistry"]

    path = "/home/markus/projects/tings/bring/repos/simple/"
    # bringistry._pkg_source.seeds._add_seed(seed_id=path, seed={"path": path})
    # await bringistry._pkg_source.sync()
    # pp(await bringistry._pkg_source.get_values())

    bringistry.set_source("bring.bring_file_source")

    bringistry.source.add_source_items(path)
    await bringistry.source.sync()

    pkgs = await bringistry.get_pkg_values_list()

    for k, v in pkgs.items():
        print(k)
        print(v.keys())

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

    # await bringistry._pkg_source.watch()


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
