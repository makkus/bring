# -*- coding: utf-8 -*-
import logging
from typing import Iterable

import asyncclick as click
from bring.config.bring_config import BringConfig
from bring.display.args_explanation import ArgsExplanation
from bring.interfaces.cli import console
from frtls.cli.exceptions import handle_exc_async
from frtls.cli.group import FrklBaseCommand
from frtls.formats.output_formats import create_multi_column_table, serialize


CONFIG_HELP = """Configuration-related utility commands"""

log = logging.getLogger("bring")

BRING_CONFIG_SCHEMAN = {
    "defaults": {
        "doc": """Default values for this configuration context.

Will be overwritten by index-specific defaults, but have higher priority than package defaults.
""",
        "type": "dict?",
    },
    "default_index": {
        "doc": "The default index to use when a package name without index part is provided.",
        "type": "string?",
    },
    "indexes": {
        "doc": """A list of indexes and their configuration.

Each item in this list is either an index id string, or a dictionary including additional data to use in this configuration context for this index (for example, default variables). For more information on index configuration, please check out [the relevant documentation site](TODO).

Each item in this list will be pre-loaded at application start, so a 'bring list' for example will list all packages of all indexes in this configuration context.
""",
        "type": "list",
    },
    "output": {
        "doc": "Output plugin to use (not implemented yet).",
        "type": "string?",
        "default": "default",
    },
    "task_log": {"doc": "Format of the task log.\n\nTODO", "type": "string?"},
}


class BringConfigGroup(FrklBaseCommand):
    def __init__(
        self,
        bring_config: BringConfig,
        config_list: Iterable[str],
        name: str = "config",
        **kwargs,
    ):

        self._bring_config: BringConfig = bring_config
        self._config_list = config_list

        kwargs["help"] = CONFIG_HELP

        super(BringConfigGroup, self).__init__(
            name=name,
            invoke_without_command=True,
            no_args_is_help=False,
            callback=self.show,
            result_callback=None,
            **kwargs,
        )

    # def format_commands(self, ctx, formatter):
    #     """Extra format methods for multi methods that adds all the commands
    #     after the options.
    #     """
    #
    #     wrap_async_task(
    #         print_config_list_for_help, bring_config=self._bring_config, formatter=formatter
    #     )

    @click.pass_context
    async def show(ctx, self):

        if ctx.invoked_subcommand is not None:
            return

        self._bring_config.set_config(*self._config_list)
        c = await self._bring_config.get_config_dict()

        config_explanation = ArgsExplanation(
            c, BRING_CONFIG_SCHEMAN, arg_hive=self._arg_hive
        )

        console.line()
        console.print(config_explanation)
        # click.echo(serialize(c, format="yaml"))

    async def _list_commands(self, ctx):

        ctx.obj["list_info_commands"] = True
        return ["profile"]

    async def _get_command(self, ctx, name):

        command = None

        # if name == "show":
        #     @click.command()
        #     @click.pass_context
        #     @handle_exc_async
        #     async def show(ctx):
        #         """show the current configuration"""
        #
        #
        #
        #     command = show

        if name == "profile":

            @click.command()
            @click.argument("profile_name", nargs=1, required=False)
            @click.pass_context
            @handle_exc_async
            async def list(ctx, profile_name):

                profiles = await self.get_config().get_contexts()

                if profile_name is None:

                    profile_list = []
                    for profile_name, profile in sorted(profiles.items()):
                        info = await profile.get_value("info")
                        slug = info.get("slug", "no description available")
                        profile_list.append([profile_name, slug])

                    table = create_multi_column_table(
                        profile_list, headers=["profile", "description"]
                    )
                    click.echo()
                    click.echo(table)
                    return

                profile = profiles.get(profile_name, None)
                if profile is None:
                    click.echo()
                    click.echo(f"No profile '{profile_name}' available.")
                    return

                values = await profile.get_values()
                click.echo(serialize(values, format="yaml"))

            return list

        return command


# @click.group()
# @click.pass_context
# def config(ctx):
#     """Helper tasks for development.
#
#     """
#
#     pass
#
#
# @config.command()
# @click.pass_context
# @handle_exc_async
# async def list(ctx):
#     """List all available config profiles."""
#
#     bring: Bring = ctx.obj["bring"]
#
#     profiles = await bring.config.get_all_index_configs()
#
#     print(profiles)
