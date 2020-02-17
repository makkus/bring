# -*- coding: utf-8 -*-

import asyncclick as click
from bring.bring import Bring
from colored import style
from frtls.cli.group import FrklBaseCommand


class BringContextGroup(FrklBaseCommand):
    def __init__(
        self,
        bring: Bring,
        context: str = None,
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
        self._context: str = context

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

    @click.pass_context
    async def all_contexts(ctx, self, *args, **kwargs):

        if ctx.invoked_subcommand:
            return

        self._init_command(ctx)

        click.echo()
        click.echo("Available contexts:")
        click.echo()
        for context_name, context in self._bring.contexts.items():
            info = await context.get_info()
            slug = info.get("slug", "no description available")
            click.echo(f"  - {style.BOLD}{context_name}{style.RESET}: {slug}")

    async def _list_commands(self):

        pkg_names = self._bring.contexts.keys()
        return pkg_names

    async def _get_command(self, name):

        context = self._bring.get_context(name)
        if context is None:
            return None

        from bring.interfaces.cli.command_group import BringCommandGroup

        context_info_command = BringCommandGroup(bring=self._bring, context=name)
        return context_info_command
