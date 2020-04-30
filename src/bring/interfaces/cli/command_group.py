# -*- coding: utf-8 -*-
import os
from collections import Iterable
from typing import Optional

from asyncclick import Choice, Option
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
            help=f"task log output plugin(s), available: {', '.join(['tree', 'simple'])} ",
        )
        context_option = Option(
            param_decls=["--context", "-ctx", "-x"],
            multiple=True,
            required=False,
            type=str,
            help="one or several profile context(s), overwrites contexts in configuration",
        )

        profile_option = Option(
            param_decls=["--config", "-c"],
            help="configuration option(s) and/or profile name(s)",
            multiple=True,
            required=False,
            type=str,
        )

        output_option = Option(
            param_decls=["--output", "-o"],
            help="output format for sub-commands that offer an option",
            multiple=False,
            required=False,
            type=Choice(["default", "json", "yaml"]),
        )
        kwargs["params"] = [
            logzero_option,
            task_log_option,
            context_option,
            profile_option,
            output_option,
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
            "info",
            "list",
            "update",
            "export-context",
            "config",
            "doc",
            "plugin",
            "self",
            # "differ",
        ]

        if "DEVELOP" in os.environ.keys():
            result.append("differ")
            # result.append("dev")

        return result

    async def _get_command(self, ctx, name):

        if name in ALIASES.keys():
            name = ALIASES[name]

        is_list_command = ctx.obj.get("list_info_commands", False)
        command = None

        config_list = None
        if not is_list_command:
            profile_options = self._group_params["config"]
            task_log = self._group_params["task_log"]
            output = self._group_params["output"]
            contexts = self._group_params["context"]

            user_config = {}
            if task_log:
                user_config["task_log"] = task_log

            if output:
                user_config["output"] = output

            if contexts:
                user_config["contexts"] = contexts

            config_list = list(profile_options) + [user_config]

        if name == "config":

            from bring.interfaces.cli.config import BringConfigGroup

            command = BringConfigGroup(
                config_list=config_list, name=name, terminal=self._terminal
            )

            return command

        elif not is_list_command:

            self.get_bring().config.config_input = config_list

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
            command.short_help = "display context or pkg information"

        elif name == "update":
            from bring.interfaces.cli.update import BringUpdateCommand

            command = BringUpdateCommand(
                bring=self.get_bring(), name="update", terminal=self._terminal
            )
            command.short_help = "update package metadata for all contexts"

        elif name == "doc":
            from bring.interfaces.cli.doc import BringDocGroup

            command = BringDocGroup(
                tingistry=self._bring._tingistry_obj, terminal=self._terminal
            )

        elif name == "dev":
            from bring.interfaces.cli.dev import dev

            command = dev

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
