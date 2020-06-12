# -*- coding: utf-8 -*-
import os
from collections import Iterable
from typing import Any, Mapping, Optional

from asyncclick import Choice, Option
from bring.bring import Bring
from bring.config.bring_config import BringConfig
from bring.defaults import BRINGISTRY_INIT
from bring.interfaces.cli.export_index import BringExportIndexCommand
from frtls.cli.group import FrklBaseCommand
from frtls.cli.logging import logzero_option_obj_async
from frtls.cli.terminal import create_terminal
from frtls.types.utils import load_modules
from tings.tingistry import Tingistries


COMMAND_GROUP_HELP = """'bring' is a package manager for files and file-sets.

'bring'-managed files that are part of so called 'indexes': collections of metadata items, each describing one specific file or file-set.
"""

ALIASES = {"in": "install", "if": "info"}


class BringCommandGroup(FrklBaseCommand):
    def __init__(self):

        modules: Iterable[str] = BRINGISTRY_INIT["modules"]  # type: ignore
        load_modules(*modules)

        kwargs = {}
        kwargs["help"] = COMMAND_GROUP_HELP

        terminal = create_terminal()

        self._tingistry_obj = Tingistries.create("bring")

        self._bring_config: Optional[BringConfig] = None
        self._bring: Optional[Bring] = None

        index_setting = dict(
            # default_map={},
            max_content_width=terminal.width,
            help_option_names=["-h", "--help"],
        )
        kwargs["context_settings"] = index_setting

        logzero_option = logzero_option_obj_async()

        task_log_option = Option(
            param_decls=["--task-log", "-l"],
            multiple=True,
            required=False,
            type=str,
            help=f"task log output plugin(s), available: {', '.join(['terminal', 'tree', 'simple'])} ",
        )
        index_option = Option(
            param_decls=["--index", "-i"],
            multiple=True,
            required=False,
            type=str,
            help="one or several profile index(s), overwrites indexes in configuration",
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
            index_option,
            profile_option,
            output_option,
        ]

        super(BringCommandGroup, self).__init__(
            name="bring",
            invoke_without_command=False,
            no_args_is_help=True,
            chain=False,
            result_callback=None,
            **kwargs,
        )

    @property
    def bring_config(self):

        if self._bring_config is None:
            self._bring_config = BringConfig(tingistry=self._tingistry_obj)

        return self._bring_config

    def create_bring_config_list(self, group_params: Mapping[str, Any]):

        profile_options = group_params["config"]
        task_log = group_params["task_log"]
        output = group_params["output"]
        indexes = group_params["index"]

        user_config = {}
        if task_log:
            user_config["task_log"] = task_log

        if output:
            user_config["output"] = output

        if indexes:
            user_config["indexes"] = indexes

        config_list = list(profile_options) + [user_config]

        return config_list

    @property
    def bring(self):

        return self.bring_config.get_bring()

    async def _list_commands(self, ctx):

        ctx.obj["list_info_commands"] = True

        result = [
            "install",
            "explain",
            "list",
            "update",
            "export-index",
            "config",
            "doc",
            # "plugin",
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
            config_list = self.create_bring_config_list(self._group_params)

        if name == "config":

            from bring.interfaces.cli.config import BringConfigGroup

            command = BringConfigGroup(
                bring_config=self.bring_config,
                config_list=config_list,
                name=name,
                arg_hive=self._tingistry_obj.arg_hive,
            )

            return command

        if not is_list_command:

            self.bring.config.set_config(*config_list)
            await self.bring.add_all_config_indexes()

        if name == "list":

            from bring.interfaces.cli.list_pkgs import BringListPkgsGroup

            command = BringListPkgsGroup(bring=self.bring, name="info")
            command.short_help = "list packages for all registered indexes"

        elif name == "install":
            from bring.interfaces.cli.install import BringInstallGroup

            command = BringInstallGroup(bring=self.bring, name="install")
            command.short_help = "install one or a list of packages"
        # elif name == "process":
        #     from bring.interfaces.cli.process import BringProcessGroup
        #
        #     command = BringProcessGroup(bring=self.bring, name="process")
        #     command.short_help = "process on or a list of packages"
        elif name == "plugin":
            from bring.interfaces.cli.plugin import BringPluginGroup

            command = BringPluginGroup(bring=self.bring, name="plugin")
            command.short_help = "install one or a list of packages"

        elif name in ["explain", "exp", "x"]:
            from bring.interfaces.cli.explain import BringInfoPkgsGroup

            command = BringInfoPkgsGroup(bring=self.bring, name="info")
            command.short_help = "display index, pkg, and target information"

        elif name == "update":
            from bring.interfaces.cli.update import BringUpdateCommand

            command = BringUpdateCommand(bring=self.bring, name="update")
            command.short_help = "update index metadata"

        elif name == "doc":
            from bring.interfaces.cli.doc import BringDocGroup

            command = BringDocGroup(tingistry=self._tingistry_obj)

        elif name == "dev":
            from bring.interfaces.cli.dev import dev

            command = dev

        elif name == "export-index":

            command = BringExportIndexCommand(bring=self.bring, name="export")
            command.short_help = "export index folder metadata to file"

        elif name == "self":

            from frtls.cli.self_command_group import self_command

            command = self_command

        elif name == "differ":
            from bring.interfaces.cli.differ import differ

            command = differ

        return command
