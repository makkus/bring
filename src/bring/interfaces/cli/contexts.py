# -*- coding: utf-8 -*-
from typing import Optional

import asyncclick as click
from bring.bring import Bring
from bring.context import BringContextTing
from frtls.cli.group import FrklBaseCommand


# def to_log(obj):
#     with open("/tmp/click", "a") as myfile:
#         from pprint import pformat
#         myfile.write(pformat(obj)+"\n")


class BringContextGroup(FrklBaseCommand):
    def __init__(
        self,
        bring: Bring,
        context: Optional[BringContextTing] = None,
        name=None,
        print_version_callback=None,
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
        self._context: Optional[BringContextTing] = context

        super(BringContextGroup, self).__init__(
            name=name,
            invoke_without_command=True,
            no_args_is_help=False,
            chain=False,
            result_callback=None,
            callback=self.all_contexts,
            arg_hive=bring.arg_hive,
            **kwargs,
        )

    async def init_command_async(self, ctx):

        await self._bring.init()

    @click.pass_context
    async def all_contexts(ctx, self, *args, **kwargs):

        if ctx.invoked_subcommand:  # type: ignore
            return

        click.echo()
        click.echo("Available contexts:")
        click.echo()
        for context_name, context in self._bring.contexts.items():
            info = await context.get_info()
            slug = info.get("slug")
            click.echo(
                f"  - {self.terminal.bold}{context_name}{self.terminal.normal}: {slug}"
            )

    async def _list_commands(self, ctx):

        pkg_names = self._bring.contexts.keys()
        # to_log(pkg_names)
        return pkg_names

    async def _get_command(self, ctx, name):

        context = self._bring.get_context(name)
        if context is None:
            return None

        from bring.interfaces.cli.command_group import BringCommandGroup

        context_info_command = BringCommandGroup(
            bring=self._bring, context=context, name=name
        )
        # import pp
        # pp(context._input_ting.__dict__)
        vals = await context.get_values("info")

        context_info_command.short_help = vals["info"].get("slug", "n/a")
        return context_info_command
