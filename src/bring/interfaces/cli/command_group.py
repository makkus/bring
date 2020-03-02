# -*- coding: utf-8 -*-
from typing import Optional

import asyncclick as click
from bring.bring import Bring
from bring.context import BringContextTing
from bring.interfaces.cli.export_context import BringExportContextCommand
from frtls.cli.group import FrklBaseCommand


class BringCommandGroup(FrklBaseCommand):
    def __init__(
        self,
        bring: Bring,
        context: Optional[BringContextTing] = None,
        name=None,
        print_version_callback=None,
        callback=None,
        no_args_is_help=None,
        chain=False,
        result_callback=None,
        **kwargs,
    ):

        self.print_version_callback = print_version_callback
        # self.params[:0] = self.get_common_options(
        #     print_version_callback=self.print_version_callback
        # )
        self._bring: Bring = bring

        self._bring: Bring = bring

        self._context: Optional[BringContextTing] = context

        if not callback:
            callback = self.overview

        super(BringCommandGroup, self).__init__(
            name=name,
            invoke_without_command=True,
            no_args_is_help=False,
            chain=False,
            result_callback=None,
            callback=callback,
            # callback=None,
            # arg_hive=bring.arg_hive,
            **kwargs,
        )

    # def init_command(self, ctx):
    #     await self._bring.init()
    @click.pass_context
    async def overview(ctx, self):

        if ctx.invoked_subcommand:
            return

        print(await self._context.get_info())

    async def init_command_async(self, ctx):

        await self._bring.init()

    async def _list_commands(self, ctx):

        result = ["info", "install", "update", "export"]
        if self._context is None:
            result.append("context")
            result.append("dev")

        return result

    async def _get_command(self, ctx, name):
        if name == "info":

            from bring.interfaces.cli.info import BringInfoGroup

            command = BringInfoGroup(
                bring=self._bring,
                context=self._context,
                name="info",
                terminal=self._terminal,
            )
            command.short_help = "display information for packages"
        elif name == "install":
            from bring.interfaces.cli.install import BringInstallGroup

            command = BringInstallGroup(
                bring=self._bring,
                context=self._context,
                name="install",
                terminal=self._terminal,
            )
            if self._context:
                command.short_help = "install a package"
            else:
                command.short_help = "install one or a list of packages"
        elif name == "context":
            from bring.interfaces.cli.contexts import BringContextGroup

            command = BringContextGroup(
                bring=self._bring, name="context", terminal=self._terminal
            )
            command.short_help = "context-specific sub-command group"

        elif name == "update":
            from bring.interfaces.cli.update import BringUpdateCommand

            command = BringUpdateCommand(
                bring=self._bring,
                context=self._context,
                name="update",
                terminal=self._terminal,
            )
            if self._context:
                command.short_help = "update package metadata for this context"
            else:
                command.short_help = "update package metadata for all contexts"

        elif name == "dev":
            from bring.interfaces.cli.dev import dev

            command = dev

        elif name == "export":

            command = BringExportContextCommand(
                bring=self._bring,
                context=self._context,
                name="export",
                terminal=self._terminal,
            )
            if self._context:
                command.short_help = f"export context '{self._context.name}'"
            else:
                command.short_help = "export all contexts"

        return command
