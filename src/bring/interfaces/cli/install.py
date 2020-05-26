# -*- coding: utf-8 -*-
from typing import Dict, Union

import asyncclick as click
from bring.bring import Bring
from bring.interfaces.cli.utils import print_pkg_list_help
from frtls.args.arg import Arg
from frtls.async_helpers import wrap_async_task
from frtls.cli.group import FrklBaseCommand
from frtls.formats.output_formats import serialize


INSTALL_HELP = """Install one or several packages."""


class BringInstallGroup(FrklBaseCommand):
    def __init__(
        self,
        bring: Bring,
        name: str = None,
        **kwargs
        # print_version_callback=None,
        # invoke_without_command=False,
    ):
        """Install"""

        # self.print_version_callback = print_version_callback
        self._bring: Bring = bring
        kwargs["help"] = INSTALL_HELP

        super(BringInstallGroup, self).__init__(
            name=name,
            invoke_without_command=True,
            no_args_is_help=True,
            callback=self.install_info,
            chain=False,
            result_callback=None,
            add_help_option=False,
            arg_hive=bring.arg_hive,
            subcommand_metavar="PROCESSOR",
            **kwargs,
        )

    @click.pass_context
    async def install_info(ctx, self, **kwargs):

        if ctx.invoked_subcommand is not None:
            return

        help = self.get_help(ctx)
        click.echo(help)

    def format_commands(self, ctx, formatter):
        """Extra format methods for multi methods that adds all the commands
        after the options.
        """

        wrap_async_task(print_pkg_list_help, bring=self._bring, formatter=formatter)

    def get_group_options(self) -> Union[Arg, Dict]:

        # target = wrap_async_task(self.get_bring_target)
        # target_args = target.requires()

        default_args = {
            "explain": {
                "doc": "Don't perform installation, only explain steps.",
                "type": "boolean",
                "default": False,
                "required": False,
                "cli": {"is_flag": True},
            },
            "help": {
                "doc": "Show this message and exit.",
                "type": "boolean",
                "default": False,
                "required": False,
                "cli": {"is_flag": True},
            },
            "target": {
                "doc": "The target directory to install the files into.",
                "type": "string",
                "required": False,
            },
            "merge_strategy": {
                "doc": "Strategy on how to deal with existing files, options",
                "type": "merge_strategy",
                "required": False,
            },
        }

        return default_args

    async def _list_commands(self, ctx):

        return []

    async def _get_command(self, ctx, name):

        explain = self._group_params.get("explain")
        load_details = not ctx.obj.get("list_install_commands", False)
        target = self._group_params_parsed.get("target", None)
        merge_strategy = self._group_params_parsed.get("merge_strategy")

        install_args = {}
        if merge_strategy:
            install_args["merge_strategy"] = merge_strategy
        if target:
            install_args["target"] = target

        if not load_details:
            return None

        pkg = await self._bring.get_pkg(name, raise_exception=True)
        install_args["pkg_name"] = pkg.name
        install_args["pkg_index"] = pkg.bring_index.id

        processor = self._bring.create_processor("install_pkg")

        processor.add_constants(_constants_name="install_args", **install_args)

        args = await processor.get_user_input_args()

        if explain:

            @click.command()
            @click.pass_context
            async def command(ctx, **kwargs):

                user_input = args.from_cli_input(**kwargs)
                processor.set_user_input(**user_input)
                explanation = processor.args_holder.explain()

                s = serialize(explanation, format="yaml")
                click.echo(s)

        else:

            @click.command()
            @click.pass_context
            async def command(ctx, **kwargs):

                user_input = args.from_cli_input(**kwargs)
                processor.set_user_input(**user_input)

                result = await processor.process()
                print(result)

        command.params = args.to_cli_options(add_defaults=False)

        return command
