# -*- coding: utf-8 -*-
import logging
import sys
from typing import Iterable, Mapping, Optional

import asyncclick as click
from bring.config import ConfigTing
from bring.config.bring_config import BringConfig
from bring.interfaces.cli import bring_code_theme, console
from frkl.args.cli.click_commands import FrklBaseCommand
from frkl.args.explain import ArgsExplanation
from frkl.common.async_utils import wrap_async_task
from frkl.common.cli.exceptions import handle_exc_async
from frkl.common.cli.output_utils import create_dict_element
from frkl.common.doc import Doc
from frkl.explain.explanations.doc import InfoExplanation, InfoListExplanation


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
        return ["context", "contexts", "show-current"]

    async def _get_command(self, ctx, name):

        if name == "show-current":

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

        elif name in ["context", "ctx"]:

            command = BringContextGroup(bring_config=self._bring_config, name="context")
            return command

        elif name == "contexts":

            @click.command()
            @click.option(
                "--full", "-f", help="display full info for each context", is_flag=True
            )
            @click.argument("context_names", nargs=-1, metavar="CONTEXT_NAME")
            @click.pass_context
            @handle_exc_async
            async def command(ctx, context_names, full: bool):

                contexts = await self._bring_config.get_contexts()

                if not context_names:
                    context_names = contexts.keys()

                all = {}
                for cn in context_names:
                    c = contexts.get(cn, None)
                    if c is None:
                        click.echo(f"No context '{cn}' available.")
                        sys.exit(1)
                    all[cn] = c

                await explain_contexts(all, full_info=full)

            return command


CONTEXT_HELP = """show details about configuration contexts"""


class BringContextGroup(FrklBaseCommand):
    def __init__(
        self,
        bring_config: BringConfig,
        name: str = None,
        **kwargs
        # print_version_callback=None,
        # invoke_without_command=False,
    ):
        """Install"""

        # self.print_version_callback = print_version_callback
        self._bring_config: BringConfig = bring_config
        kwargs["help"] = CONTEXT_HELP

        self._contexts: Optional[Mapping[str, ConfigTing]] = None

        super(BringContextGroup, self).__init__(
            name=name,
            invoke_without_command=True,
            no_args_is_help=False,
            chain=False,
            callback=self.show_all,
            result_callback=None,
            add_help_option=True,
            subcommand_metavar="CONTEXT_NAME",
            **kwargs,
        )

    async def get_contexts(self) -> Mapping[str, ConfigTing]:

        if self._contexts is None:
            self._contexts = await self._bring_config.get_contexts()
        return self._contexts

    @click.pass_context
    async def show_all(ctx, self, **kwargs):

        if ctx.invoked_subcommand is not None:
            return

        full = False
        contexts = await self.get_contexts()

        await explain_contexts(contexts, full_info=full)

    async def _list_commands(self, ctx):

        contexts = await self.get_contexts()
        return contexts.keys()

    async def _get_command(self, ctx, name):

        contexts = await self.get_contexts()
        context = contexts.get(name, None)

        if context is None:
            return None

        command = BringContextCommands(
            bring_config=self._bring_config, bring_context=context, name=name
        )

        return command


class BringContextCommands(FrklBaseCommand):
    def __init__(
        self,
        bring_config: BringConfig,
        bring_context: ConfigTing,
        name: str = None,
        **kwargs
        # print_version_callback=None,
        # invoke_without_command=False,
    ):
        """Install"""

        # self.print_version_callback = print_version_callback
        self._bring_config: BringConfig = bring_config
        self._bring_context: ConfigTing = bring_context
        info = wrap_async_task(self._bring_context.get_value, "info")

        kwargs["help"] = info.get("slug", "-- n/a --")

        super(BringContextCommands, self).__init__(
            name=name,
            invoke_without_command=True,
            no_args_is_help=False,
            chain=False,
            callback=self.show_details,
            result_callback=None,
            add_help_option=True,
            subcommand_metavar="CONTEXT_NAME",
            **kwargs,
        )

    @click.pass_context
    async def show_details(ctx, self):

        if ctx.invoked_subcommand is not None:
            return

        console.line()
        ce = ContextExplanation(
            name=self.name, data=self._bring_context, full_info=True, show_title=True
        )

        console.print(ce)

    async def _list_commands(self, ctx):

        return ["show", "edit", "copy"]

    async def _get_command(self, ctx, name):

        if name == "show":

            @click.command()
            @click.pass_context
            @handle_exc_async
            async def command(ctx):

                console.line()
                ce = ContextExplanation(
                    name=self.name,
                    data=self._bring_context,
                    full_info=True,
                    show_title=True,
                )

                console.print(ce)

            return command


class ContextExplanation(InfoExplanation):
    def __init__(
        self,
        data: ConfigTing,
        name: Optional[str] = None,
        full_info: bool = False,
        show_title: bool = True,
    ):

        super().__init__(
            data=data,
            name=name,
            short_help_key="slug",
            help_key="desc",
            full_info=full_info,
            show_title=show_title,
        )

    async def get_info(self) -> Doc:

        vals = await self.data.get_values()

        config_source = vals["config_source"]
        info = vals["info"]

        info["path"] = config_source.get("full_path", "-- not available --")

        if vals["parent"]:
            info["parent context"] = vals["parent"]

        info["config_data"] = create_dict_element(
            _theme=bring_code_theme, _prefix=" \n", **vals["config"]
        )

        info_data = Doc(
            info, short_help_key=self._short_help_key, help_key=self._help_key
        )
        return info_data


async def explain_contexts(
    contexts: Mapping[str, ConfigTing], full_info: bool = False
) -> None:

    explanations = []
    for ctx_name, context in contexts.items():

        ce = ContextExplanation(
            data=context, name=ctx_name, full_info=full_info, show_title=False
        )

        explanations.append(ce)

    exp_list = InfoListExplanation(*explanations, full_info=full_info)

    console.print(exp_list)
