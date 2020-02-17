# -*- coding: utf-8 -*-
import asyncclick as click
from bring.bring import Bring
from frtls.cli.group import FrklBaseCommand


class BringCommandGroup(FrklBaseCommand):
    def __init__(
        self,
        bring: Bring,
        context: str = None,
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
        self._context = context

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

        context = self._bring.get_context(self._context)

        print(await context.get_info())

    async def _list_commands(self):

        result = ["info", "install"]
        if self._context is None:
            result.append("context")

        return result

    async def _get_command(self, name):
        if name == "info":

            from bring.interfaces.cli.info import BringInfoGroup

            command = BringInfoGroup(bring=self._bring, context=self._context)
        elif name == "install":
            from bring.interfaces.cli.install import BringInstallGroup

            command = BringInstallGroup(bring=self._bring, context=self._context)
        elif name == "context":
            from bring.interfaces.cli.contexts import BringContextGroup

            command = BringContextGroup(bring=self._bring)

        return command
