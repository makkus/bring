# -*- coding: utf-8 -*-
import logging
import os

import asyncclick as click
from asyncclick import Command, Option
from bring.bring import Bring
from bring.bring_target.local_folder import LocalFolderTarget
from bring.display.info import IndexInfoDisplay, PkgInfoDisplay
from bring.interfaces.cli import console
from bring.pkg_index.index import BringIndexTing
from bring.pkg_index.pkg import PkgTing
from frtls.cli.group import FrklBaseCommand


log = logging.getLogger("bring")

INFO_HELP = """Display information about a index or package.

You can either provide a index or package name. If the specified value matches a index name, index information will
be displayed. Otherwise all indexes will be looked up to find a matching package name. If you want to display information for a package from the default index, you may omit the 'index' part of the package name.
"""


class BringInfoPkgsGroup(FrklBaseCommand):
    def __init__(self, bring: Bring, name=None, **kwargs):

        self._bring: Bring = bring

        kwargs["help"] = INFO_HELP

        super(BringInfoPkgsGroup, self).__init__(
            name=name,
            invoke_without_command=False,
            no_args_is_help=True,
            chain=False,
            result_callback=None,
            # callback=self.all_info,
            arg_hive=bring.arg_hive,
            subcommand_metavar="CONTEXT_OR_PKG_NAME",
            **kwargs,
        )

    async def _list_commands(self, ctx):

        ctx.obj["list_info_commands"] = True
        return ["target", "index", "package"]

    async def _get_command(self, ctx, name):

        # index_name = self._group_params.get("index", None)

        # _ctx_name = await ensure_index(self._bring, name=index_name)
        # await self._bring.get_index(_ctx_name)

        # load_details = not ctx.obj.get("list_info_commands", False)
        #
        # if not load_details:
        #     return None

        if name == "target":

            @click.command()
            @click.argument("path", nargs=1, required=False)
            @click.pass_context
            async def command(ctx, path):
                if path is None:
                    path = os.getcwd()
                target = LocalFolderTarget(bring=self._bring, path=path)
                console.line()
                console.print(target)
                # print(await tf.get_managed_files())

            return command

        elif name in ["index", "idx"]:

            @click.command()
            @click.argument("index", nargs=1, required=True)
            @click.option(
                "--update",
                "-u",
                help="update index before retrieving info",
                is_flag=True,
            )
            @click.option(
                "--full", "-f", help="display extended information", is_flag=True
            )
            @click.option(
                "--packages", "-p", help="display packages of this index", is_flag=True
            )
            @click.pass_context
            async def command(ctx, index, update, full, packages):

                idx = await self._bring.get_index(index_name=index)

                display = IndexInfoDisplay(
                    index=idx,
                    update=update,
                    display_full=full,
                    display_packages=packages,
                )
                console.print(display)

            return command

        elif name in ["package", "pkg"]:

            @click.command()
            @click.argument("package", nargs=1, required=True)
            @click.option(
                "--update",
                "-u",
                help="update index before retrieving info",
                is_flag=True,
            )
            @click.option(
                "--full", "-f", help="display extended information", is_flag=True
            )
            @click.option("--args", "-a", help="display package args", is_flag=True)
            @click.pass_context
            async def command(ctx, package, update, full, args):

                # await self._bring.add_indexes("kubernetes", "binaries")
                pkg = await self._bring.get_pkg(name=package, raise_exception=True)

                pkg_info: PkgInfoDisplay = PkgInfoDisplay(
                    pkg=pkg, update=update, display_full=full, display_args=args
                )
                console.print(pkg_info)

            return command

        return None


class IndexInfoTingCommand(Command):
    def __init__(
        self, name: str, index: BringIndexTing, load_details: bool = False, **kwargs
    ):

        self._index: BringIndexTing = index
        self._index_info: IndexInfoDisplay = IndexInfoDisplay(index=self._index)
        try:

            # slug = self._pkg_info.slug
            short_help = self._index_info.short_help

            kwargs["short_help"] = short_help
            desc = self._index_info.desc
            help = f"Display info for index '{self._index.name}'"
            if desc:
                help = f"{help}\n\n{desc}"

            params = [
                Option(
                    ["--update", "-u"],
                    help="update index metadata before display",
                    is_flag=True,
                    required=False,
                ),
                Option(
                    ["--pkgs", "-p"],
                    help="display packages of this index",
                    is_flag=True,
                    required=False,
                ),
                Option(
                    ["--config", "-c"],
                    help="display index configuration",
                    is_flag=True,
                    required=False,
                ),
                Option(
                    ["--full", "-f"],
                    help="display full information for index",
                    is_flag=True,
                    required=False,
                ),
            ]

            kwargs["help"] = help
        except (Exception) as e:
            log.debug(f"Can't create IndexInfoTingCommand object: {e}", exc_info=True)
            raise e

        super().__init__(name=name, callback=self.info, params=params, **kwargs)

    @click.pass_context
    async def info(
        ctx,
        self,
        update: bool = False,
        full: bool = False,
        config: bool = False,
        pkgs: bool = False,
    ):

        self._index_info.update = update
        self._index_info.display_full = full
        self._index_info.display_config = config
        self._index_info.display_packages = pkgs

        console.print(self._index_info)


class PkgInfoTingCommand(Command):
    def __init__(self, name: str, pkg: PkgTing, load_details: bool = False, **kwargs):

        self._pkg: PkgTing = pkg

        self._pkg_info: PkgInfoDisplay = PkgInfoDisplay(pkg=pkg)
        try:

            # slug = self._pkg_info.slug
            short_help = self._pkg_info.short_help

            kwargs["short_help"] = short_help
            desc = self._pkg_info.desc
            help = f"Display info for the '{self._pkg.name}' package."
            if desc:
                help = f"{help}\n\n{desc}"

            params = [
                Option(
                    ["--update", "-u"],
                    help="update package metadata",
                    is_flag=True,
                    required=False,
                ),
                Option(
                    ["--args", "-a"],
                    help="display only full arguments for package",
                    is_flag=True,
                    required=False,
                ),
                Option(
                    ["--full", "-f"],
                    help="display full information for package",
                    is_flag=True,
                    required=False,
                ),
            ]

            kwargs["help"] = help
        except (Exception) as e:
            log.debug(f"Can't create PkgInstallTingCommand object: {e}", exc_info=True)
            raise e

        super().__init__(name=name, callback=self.info, params=params, **kwargs)

    @click.pass_context
    async def info(
        ctx, self, update: bool = False, full: bool = False, args: bool = False
    ):

        self._pkg_info.update = update
        self._pkg_info.display_args = args
        self._pkg_info.display_full = full
        console.print(self._pkg_info)
