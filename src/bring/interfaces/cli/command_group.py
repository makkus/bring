# -*- coding: utf-8 -*-
import os

from bring.bring import Bring
from bring.interfaces.cli.export_context import BringExportContextCommand
from frtls.cli.group import FrklBaseCommand


COMMAND_GROUP_HELP = """'bring' is a package manager for files and file-sets.

'bring'-managed files that are part of so called 'contexts': collections of metadata items, each describing one specific file or file-set.
"""


class BringCommandGroup(FrklBaseCommand):
    def __init__(
        self,
        bring: Bring,
        name=None,
        print_version_callback=None,
        callback=None,
        no_args_is_help=True,
        chain=False,
        result_callback=None,
        **kwargs,
    ):
        kwargs["help"] = COMMAND_GROUP_HELP

        self.print_version_callback = print_version_callback
        # self.params[:0] = self.get_common_options(
        #     print_version_callback=self.print_version_callback
        # )

        self._bring: Bring = bring

        super(BringCommandGroup, self).__init__(
            name=name,
            invoke_without_command=False,
            no_args_is_help=True,
            chain=False,
            result_callback=None,
            callback=callback,
            # callback=None,
            # arg_hive=bring.arg_hive,
            **kwargs,
        )

    # # def init_command(self, ctx):
    # #     await self._bring.init()
    # @click.pass_context
    # async def overview(ctx, self):
    #
    #     if ctx.invoked_subcommand:
    #         return
    #
    #     print(await self._context.get_info())

    # async def init_command_async(self, ctx):
    #
    # if ctx.obj is None:
    #     ctx.obj = {}
    #     ctx.obj["bring"] = self._bring
    #     await self._bring.init()

    async def _list_commands(self, ctx):

        result = [
            "install",
            "info",
            "list",
            "update",
            "export-context",
            "self",
            "differ",
        ]

        if "DEBUG" in os.environ.keys():
            result.append("dev")

        return result

    async def _get_command(self, ctx, name):

        command = None
        if name == "list":

            from bring.interfaces.cli.list_pkgs import BringListPkgsGroup

            command = BringListPkgsGroup(
                bring=self._bring, name="info", terminal=self._terminal
            )
            command.short_help = "display information for packages"

        elif name == "install":
            from bring.interfaces.cli.install import BringInstallGroup

            command = BringInstallGroup(
                bring=self._bring, name="install", terminal=self._terminal
            )
            command.short_help = "install one or a list of packages"

        elif name == "info":
            from bring.interfaces.cli.info import BringInfoPkgsGroup

            command = BringInfoPkgsGroup(bring=self._bring, name="info")
            command.short_help = "context-specific sub-command group"

        elif name == "update":
            from bring.interfaces.cli.update import BringUpdateCommand

            command = BringUpdateCommand(
                bring=self._bring, name="update", terminal=self._terminal
            )
            command.short_help = "update package metadata for all contexts"

        elif name == "dev":
            from bring.interfaces.cli.dev import dev

            command = dev

        elif name == "config":
            from bring.interfaces.cli.config import config

            command = config

        elif name == "export-context":

            command = BringExportContextCommand(
                bring=self._bring, name="export", terminal=self._terminal
            )
            command.short_help = "export all contexts"

        elif name == "self":

            from frtls.cli.self_command_group import self_command

            command = self_command

        elif name == "differ":
            from bring.interfaces.cli.differ import differ

            command = differ

        return command
