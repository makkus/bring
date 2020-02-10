# -*- coding: utf-8 -*-

import asyncclick as click

# from click import Path
# from click_aliases import ClickAliasedGroup
from asyncclick import Path

from bring.bring import Bringistry
from bring.interfaces.cli.info import BringInfoGroup
from bring.interfaces.cli.install import BringInstallGroup
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

    bringistry = Tingistries().add_tingistry("bring", tingistry_class="bringistry")
    ctx.obj["bringistry"] = bringistry

    path = "/home/markus/projects/tings/bring/repos/simple/"
    bringistry.set_source("bring.bring_file_source")
    bringistry.source.add_source_items(path)
    await bringistry.source.sync()


install = BringInstallGroup(name="install")
cli.add_command(install)

info = BringInfoGroup(name="info")
cli.add_command(info)


@cli.command(name="test")
@click.pass_context
@handle_exc
async def test(ctx):

    bringistry: Bringistry = ctx.obj["bringistry"]

    path = "/home/markus/projects/tings/bring/repos/simple/"
    # bringistry._pkg_source.seeds._add_seed(seed_id=path, seed={"path": path})
    # await bringistry._pkg_source.sync()
    # pp(await bringistry._pkg_source.get_values())

    bringistry.set_source("bring.bring_file_source")

    bringistry.source.add_source_items(path)
    await bringistry.source.sync()

    # vars = {"version": "0.12.0"}
    vars = {}
    pkg = bringistry.get_pkg("bat")

    # folder = await pkg.provide_artefact_folder(vars)
    #
    # print(folder)

    files = await pkg.get_file_paths(vars=vars, profile="executables")

    print(files)

    # root = await bringistry.prepare_artefact("bat", artefact_path=dl_path)
    # print(root)

    # pkgs = await bringistry.get_pkgs()
    #
    # pkg = pkgs["bat"]
    #
    # source_details = pkg["source"]
    #
    # resolver: PkgResolver = bringistry._resolvers["github-release"]
    #
    # metadata = pkg["metadata"]
    # version = resolver.find_version(vars={}, defaults=metadata["defaults"], versions=metadata["versions"])
    #
    # download_path = await resolver.get_artefact_path("/tmp/", version=version, source_details=source_details)
    #
    # print("DOWNLOAD: {}".format(download_path))


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

    pkgs = await bringistry.get_pkgs()

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
