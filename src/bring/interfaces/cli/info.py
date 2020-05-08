# -*- coding: utf-8 -*-
import asyncclick as click
from asyncclick import Command, Option
from bring.bring import Bring
from bring.display.info import IndexInfoDisplay, PkgInfoDisplay
from bring.interfaces.cli import console
from bring.interfaces.cli.utils import (
    log,
    print_index_list_for_help,
    print_pkg_list_help,
)
from bring.pkg_index import BringIndexTing
from bring.pkg_index.pkg import PkgTing
from frtls.async_helpers import wrap_async_task
from frtls.cli.group import FrklBaseCommand


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

    def format_commands(self, ctx, formatter):
        """Extra format methods for multi methods that adds all the commands
        after the options.
        """

        wrap_async_task(
            print_index_list_for_help, bring=self._bring, formatter=formatter
        )
        wrap_async_task(print_pkg_list_help, bring=self._bring, formatter=formatter)

    async def _list_commands(self, ctx):

        ctx.obj["list_info_commands"] = True
        return []

    async def _get_command(self, ctx, name):

        # index_name = self._group_params.get("index", None)

        # _ctx_name = await ensure_index(self._bring, name=index_name)
        # await self._bring.get_index(_ctx_name)

        load_details = not ctx.obj.get("list_info_commands", False)

        if not load_details:
            return None

        index = await self._bring.get_index(index_name=name, raise_exception=False)
        if index is not None:
            command = IndexInfoTingCommand(
                name=name, index=index, load_details=load_details
            )
            return command

        pkg = await self._bring.get_pkg(name=name, raise_exception=False)
        if pkg is None:
            return None

        command = PkgInfoTingCommand(name=name, pkg=pkg, load_details=load_details)
        return command


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
