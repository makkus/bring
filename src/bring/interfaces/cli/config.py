# -*- coding: utf-8 -*-
import logging
import sys
from typing import Iterable

import asyncclick as click
from bring.config.bring_config import BringConfig
from bring.interfaces.cli import bring_code_theme, console
from frtls.cli.exceptions import handle_exc_async
from frtls.cli.group import FrklBaseCommand
from frtls.doc.explanation.args import ArgsExplanation
from frtls.doc.explanation.info import InfoExplanation, InfoListExplanation
from frtls.doc.utils import create_dict_element


CONFIG_HELP = """Configuration-related utility commands.

This sub-command provides convenience wrappers to display information about, as well as create and manage configuration contexts for 'bring'. Use the '--help' option on the sub-commands for more information.
"""

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
            no_args_is_help=True,
            result_callback=None,
            **kwargs,
        )

    async def _list_commands(self, ctx):

        ctx.obj["list_info_commands"] = True
        return ["contexts", "show", "show-current"]

    async def _get_command(self, ctx, name):

        if name == "show":

            @click.command()
            @click.option("--full", "-f", help="Show full details.", is_flag=True)
            @click.argument(
                "context_name", type=str, nargs=1, required=True, default="default"
            )
            @click.pass_context
            @handle_exc_async
            async def show(ctx, context_name: str, full: bool):
                """Show details for a config context."""

                contexts = await self._bring_config.get_contexts()

                context = contexts.get(context_name, None)
                if context is None:
                    click.echo(f"No context '{context_name}' available.")
                    sys.exit(1)

                console.line()

                vals = await context.get_values()

                config_source = vals["config_source"]
                info = vals["info"]

                info["path"] = config_source.get("full_path", "-- not available --")

                if vals["parent"]:
                    info["parent context"] = vals["parent"]

                info["config_data"] = create_dict_element(
                    _theme=bring_code_theme, **vals["config"]
                )

                exp = InfoExplanation(
                    name=context_name,
                    info_data=info,
                    short_help_key="slug",
                    help_key="desc",
                    full_info=True,
                )
                console.print(exp)

            return show

        elif name == "show-current":

            @click.command()
            @click.option("--full", "-f", help="Show full details.", is_flag=True)
            @click.pass_context
            @handle_exc_async
            async def show_current(ctx, full: bool):
                """Show details for the current config context.

                This takes into account the provided gloabl arguments for this commandline invocation.
                """

                self._bring_config.set_config(*self._config_list)
                c = await self._bring_config.get_config_dict()

                config_explanation = ArgsExplanation(
                    c, BRING_CONFIG_SCHEMAN, arg_hive=self._arg_hive, full_details=full
                )

                console.line()
                console.print(config_explanation)

            return show_current

        elif name == "contexts":

            @click.command()
            @click.pass_context
            @handle_exc_async
            async def contexts(ctx):
                """List available config contexts."""

                contexts = await self._bring_config.get_contexts()

                explanations = []
                for ctx_name, context in contexts.items():

                    vals = await context.get_values()
                    config_source = vals["config_source"]

                    info = vals["info"]
                    info["source"] = config_source

                    exp = InfoExplanation(
                        name=ctx_name,
                        info_data=info,
                        short_help_key="slug",
                        help_key="desc",
                    )
                    explanations.append(exp)

                exp_list = InfoListExplanation(*explanations)

                console.print(exp_list)

            return contexts


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
