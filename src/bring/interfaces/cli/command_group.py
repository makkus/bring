# -*- coding: utf-8 -*-
import os
from collections import Iterable
from typing import Any, Mapping, Optional

from asyncclick import Option
from bring import BRING
from bring.bring import Bring
from bring.config.bring_config import BringConfig
from bring.defaults import BRINGISTRY_INIT, BRING_DEFAULT_LOG_FILE
from bring.interfaces.cli.commands.export_index import BringExportIndexCommand
from freckles.core.freckles import Freckles
from frkl.args.cli.click_commands import FrklBaseCommand
from frkl.common.cli import get_console
from frkl.common.types import load_modules
from frkl.events.app_events.mgmt import AppEventManagement
from rich.console import Console
from tings.tingistry import Tingistry


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

        self._console: Console = get_console()

        self._freckles: Freckles = BRING.get_singleton(Freckles)

        self._app_event_management: Optional[AppEventManagement] = None

        self._tingistry_obj: Tingistry = self._freckles.tingistry

        self._bring_config: Optional[BringConfig] = None
        self._bring: Optional[Bring] = None

        index_setting = dict(
            # default_map={},
            max_content_width=self._console.width,
            help_option_names=["-h", "--help"],
        )
        kwargs["context_settings"] = index_setting

        output_option = Option(
            param_decls=["--output", "-o"],
            multiple=True,
            required=False,
            type=str,
            help="which output plugins to use, defaults to 'terminal'",
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

        kwargs["params"] = [
            output_option,
            index_option,
            profile_option,
        ]

        super(BringCommandGroup, self).__init__(
            name="bring",
            invoke_without_command=False,
            no_args_is_help=True,
            chain=False,
            result_callback=None,
            arg_hive=self._tingistry_obj.arg_hive,
            **kwargs,
        )

    def init_app_env_mgmt(self, *targets) -> None:

        if self._app_event_management is not None:
            return

        if not targets:
            _targets: Iterable = [{"type": "terminal"}]
        else:
            _targets = targets

        log_file = None
        # TODO: adjust default log level according to current version of this app, and env vars
        if True:
            log_file = BRING_DEFAULT_LOG_FILE
        self._app_event_management = AppEventManagement(
            base_topic=f"{self._freckles.full_name}",
            target_configs=_targets,
            typistry=self._tingistry_obj.typistry,
            log_file=log_file,
            logger_name="bring",
        )
        self._app_event_management.start_monitoring()
        self._freckles.set_app_event_management(self._app_event_management)

    @property
    def bring_config(self):

        if self._bring_config is None:
            self._bring_config = BringConfig(freckles=self._freckles)

        return self._bring_config

    def create_bring_config_list(self, group_params: Mapping[str, Any]):

        profile_options = group_params["config"]
        indexes = group_params["index"]

        user_config = {}

        if indexes:
            user_config["indexes"] = indexes

        config_list = []
        if profile_options:
            config_list.extend(profile_options)
        if user_config:
            config_list.append(user_config)

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
            "create",
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

        group_params = dict(self._group_params)

        default_output = [{"type": "terminal"}]
        output_config = group_params.pop("output", None)
        if not output_config:
            output_config = default_output

        if not is_list_command:
            config_list = self.create_bring_config_list(group_params)

        # if name == "config":
        #
        #     from bring.interfaces.cli.config import BringConfigGroup
        #
        #     command = BringConfigGroup(
        #         bring_config=self.bring_config,
        #         config_list=config_list,
        #         name=name,
        #         arg_hive=self._tingistry_obj.arg_hive,
        #     )
        #
        #     return command

        self.init_app_env_mgmt(*output_config)

        if name in ["explain", "exp", "x"]:

            from bring.interfaces.cli.commands.explain import BringInfoPkgsGroup

            command = BringInfoPkgsGroup(
                bring_config=self.bring_config,
                config_list=config_list,
                name="info",
                arg_hive=self._tingistry_obj.arg_hive,
            )
            command.short_help = "display context, index, pkg, or target information"

            return command

        elif name == "create":

            from bring.interfaces.cli.commands.create import BringCreateGroup

            command = BringCreateGroup(name="create", arg_hive=self.arg_hive)
            return command

        if not is_list_command:

            self.bring.config.set_config(*config_list)
            await self.bring.add_all_config_indexes()

        if name == "list":

            from bring.interfaces.cli.list_pkgs import BringListPkgsGroup

            command = BringListPkgsGroup(
                bring=self.bring, name="info", arg_hive=self.arg_hive
            )
            command.short_help = "list packages for all registered indexes"

        elif name == "install":
            from bring.interfaces.cli.commands.install import BringInstallGroup

            command = BringInstallGroup(
                bring=self.bring, name="install", arg_hive=self.arg_hive
            )
            command.short_help = "install one or a list of packages"
        # elif name == "process":
        #     from bring.interfaces.cli.process import BringProcessGroup
        #
        #     command = BringProcessGroup(bring=self.bring, name="process")
        #     command.short_help = "process on or a list of packages"
        # elif name == "plugin":
        #     from bring.interfaces.cli.plugin import BringPluginGroup
        #
        #     command = BringPluginGroup(bring=self.bring, name="plugin")
        #     command.short_help = "install one or a list of packages"

        elif name == "update":
            from bring.interfaces.cli.commands.update import BringUpdateCommand

            command = BringUpdateCommand(bring=self.bring, name="update")
            command.short_help = "update index metadata"

        elif name == "doc":
            from bring.interfaces.cli.commands.doc import BringDocGroup

            command = BringDocGroup(freckles=self._freckles, arg_hive=self.arg_hive)

        elif name == "dev":
            from bring.interfaces.cli.dev import BringDevGroup

            command = BringDevGroup(bring=self.bring, arg_hive=self.arg_hive)

        # elif name == "plugin":
        #     ctx.obj["bring"] = self.bring
        #     from bring.interfaces.cli.plugin import plugin
        #
        #     command = plugin

        elif name == "export-index":

            command = BringExportIndexCommand(bring=self.bring, name="export")
            command.short_help = "export index folder metadata to file"

        elif name == "self":

            from frkl.args.cli.click_commands.self_command import SelfCommandGroup

            command = SelfCommandGroup(app_env=BRING, arg_hive=self.arg_hive)

        elif name == "differ":
            from bring.interfaces.cli.differ import differ

            command = differ

        return command
