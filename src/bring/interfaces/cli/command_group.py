# -*- coding: utf-8 -*-
import os
from collections import Iterable
from typing import Optional

from asyncclick import Option
from bring.bring import Bring
from bring.defaults import BRINGISTRY_INIT
from bring.interfaces.cli.export_context import BringExportContextCommand
from frtls.cli.group import FrklBaseCommand
from frtls.cli.logging import logzero_option_obj_async
from frtls.cli.terminal import create_terminal
from frtls.types.utils import load_modules
from tings.tingistry import Tingistries


COMMAND_GROUP_HELP = """'bring' is a package manager for files and file-sets.

'bring'-managed files that are part of so called 'contexts': collections of metadata items, each describing one specific file or file-set.
"""

ALIASES = {"in": "install", "if": "info"}


class BringCommandGroup(FrklBaseCommand):
    def __init__(self):

        modules: Iterable[str] = BRINGISTRY_INIT["modules"]  # type: ignore
        load_modules(*modules)

        kwargs = {}
        kwargs["help"] = COMMAND_GROUP_HELP

        terminal = create_terminal()
        context_setting = dict(
            # default_map={},
            max_content_width=terminal.width,
            help_option_names=["-h", "--help"],
        )
        kwargs["context_settings"] = context_setting

        logzero_option = logzero_option_obj_async()

        task_log_option = Option(
            param_decls=["--task-log", "-l"],
            multiple=True,
            required=False,
            type=str,
            help=f"running tasks output plugin(s), available: {', '.join(['tree', 'simple'])} ",
        )
        context_option = Option(
            param_decls=["--context", "-c"],
            multiple=True,
            required=False,
            type=str,
            help="default context (first item), and additional contexts",
        )

        profile_option = Option(
            param_decls=["--profile", "-p"],
            help="configuration profile or profile option",
            multiple=True,
            required=False,
            type=str,
        )
        kwargs["params"] = [
            logzero_option,
            task_log_option,
            context_option,
            profile_option,
        ]

        self._tingistry_obj = Tingistries.create("bring")

        self._bring: Optional[Bring] = None

        super(BringCommandGroup, self).__init__(
            name="bring",
            invoke_without_command=False,
            no_args_is_help=True,
            chain=False,
            result_callback=None,
            # callback=callback,
            # callback=None,
            # arg_hive=bring.arg_hive,
            **kwargs,
        )

    def get_bring(self) -> Bring:

        if self._bring is None:
            self._bring = self._tingistry_obj.create_singleting("bring.mgmt", Bring)
        return self._bring

    async def _list_commands(self, ctx):

        ctx.obj["list_info_commands"] = True

        result = [
            "install",
            "plugin",
            "info",
            "list",
            "update",
            "export-context",
            "config",
            "self",
            "differ",
        ]

        if "DEBUG" in os.environ.keys():
            result.append("dev")

        return result

    async def _get_command(self, ctx, name):

        if name in ALIASES.keys():
            name = ALIASES[name]

        is_list_command = ctx.obj.get("list_info_commands", False)
        if not is_list_command:

            profile_options = self._group_params["profile"]

            task_log = self._group_params["task_log"]
            self.get_bring().config.config_input = list(profile_options) + [
                {"task_log": task_log}
            ]

            contexts = self._group_params["context"]

            set_default = True
            for c in contexts:
                await self.get_bring().config.ensure_context(c, set_default=set_default)
                set_default = False

        command = None
        if name == "list":

            from bring.interfaces.cli.list_pkgs import BringListPkgsGroup

            command = BringListPkgsGroup(
                bring=self.get_bring(), name="info", terminal=self._terminal
            )
            command.short_help = "display information for packages"

        elif name == "install":
            from bring.interfaces.cli.install import BringInstallGroup

            command = BringInstallGroup(
                bring=self.get_bring(), name="install", terminal=self._terminal
            )
            command.short_help = "install one or a list of packages"
        elif name == "plugin":
            from bring.interfaces.cli.plugin import BringPluginGroup

            command = BringPluginGroup(
                bring=self.get_bring(), name="process", terminal=self._terminal
            )
            command.short_help = "install one or a list of packages"

        elif name == "info":
            from bring.interfaces.cli.info import BringInfoPkgsGroup

            command = BringInfoPkgsGroup(bring=self.get_bring(), name="info")
            command.short_help = "context-specific sub-command group"

        elif name == "update":
            from bring.interfaces.cli.update import BringUpdateCommand

            command = BringUpdateCommand(
                bring=self.get_bring(), name="update", terminal=self._terminal
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
                bring=self.get_bring(), name="export", terminal=self._terminal
            )
            command.short_help = "export all contexts"

        elif name == "self":

            from frtls.cli.self_command_group import self_command

            command = self_command

        elif name == "differ":
            from bring.interfaces.cli.differ import differ

            command = differ

        return command
