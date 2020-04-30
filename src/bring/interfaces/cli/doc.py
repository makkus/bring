# -*- coding: utf-8 -*-
import logging
from typing import Optional

import asyncclick as click
from blessed import Terminal
from bring.mogrify import Mogrifier
from bring.pkg_types import PkgType
from frtls.args.hive import ArgHive
from frtls.cli.group import FrklBaseCommand
from frtls.types.plugins import TypistryPluginManager
from frtls.types.typistry import Typistry
from tings.tingistry import Tingistry


log = logging.getLogger("bring")

PLUGIN_HELP = """documentation for application components"""


class BringDocGroup(FrklBaseCommand):
    def __init__(
        self,
        tingistry: Tingistry,
        name: str = "doc",
        terminal: Terminal = None,
        **kwargs,
    ):
        """Install"""

        # self.print_version_callback = print_version_callback
        self._tingistry: Tingistry = tingistry
        self._typistry: Typistry = self._tingistry.typistry
        kwargs["help"] = PLUGIN_HELP

        # self._plugin_managers: Dict[str, TypistryPluginManager] = None

        super(BringDocGroup, self).__init__(
            name=name, arg_hive=self._tingistry.arg_hive, terminal=terminal, **kwargs
        )

    # def plugin_managers(self) -> Mapping[str, TypistryPluginManager]:
    #
    #     if self._plugin_managers is not None:
    #         return self._plugin_managers
    #
    #     self._plugin_managers = {}
    #     for pl_cls in self._plugin_classes:
    #
    #         pm = self._typistry.get_plugin_manager(pl_cls)
    #         self._plugin_managers[pm.manager_name] = pm
    #
    #     return self._plugin_managers

    async def _list_commands(self, ctx):

        return ["pkg-type", "mogrifier"]

    async def _get_command(self, ctx, name):

        command = None
        if name == "pkg-type":
            plugin_manager = self._typistry.get_plugin_manager(PkgType)
            command = PkgTypePluginGroup(
                plugin_manager=plugin_manager,
                arg_hive=self._tingistry.arg_hive,
                terminal=self._terminal,
            )

        elif name == "mogrifier":
            plugin_manager = self._typistry.get_plugin_manager(Mogrifier)
            command = MogrifyPluginGroup(
                plugin_manager=plugin_manager,
                arg_hive=self._tingistry.arg_hive,
                terminal=self._terminal,
            )

        return command


class BringPluginGroup(FrklBaseCommand):
    def __init__(
        self,
        plugin_manager: TypistryPluginManager,
        arg_hive: ArgHive,
        terminal: Optional[Terminal] = None,
    ):

        self._plugin_manager = plugin_manager

        super(BringPluginGroup, self).__init__(
            name=self._plugin_manager.manager_name,
            arg_hive=arg_hive,
            terminal=terminal,
            subcommand_metavar="PLUGIN",
        )

    async def _list_commands(self, ctx):

        return sorted(self._plugin_manager.plugin_names)


class PkgTypePluginGroup(BringPluginGroup):
    async def _get_command(self, ctx, name):

        if name not in self._plugin_manager.plugin_names:
            return None

        @click.command()
        @click.pass_context
        def plugin_command(ctx):

            pm = self._plugin_manager
            desc = pm.get_plugin_description(name)
            plugin = pm.get_plugin(name)

            args = plugin.get_args()
            import pp

            pp(desc)
            pp(args)

        return plugin_command


class MogrifyPluginGroup(BringPluginGroup):
    async def _get_command(self, ctx, name):
        @click.command()
        @click.pass_context
        def plugin_command(ctx):

            pm = self._plugin_manager
            plugin = pm.get_plugin(name)
            desc = pm.get_plugin_description(name)

            print(desc)
            print(plugin)

        return plugin_command
