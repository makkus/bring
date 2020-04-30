# -*- coding: utf-8 -*-
import logging
from typing import Dict, Iterable, Type

from blessed import Terminal
from frtls.cli.group import FrklBaseCommand
from frtls.types.typistry import Typistry, TypistryPluginManager
from tings.tingistry import Tingistry


log = logging.getLogger("bring")

PLUGIN_HELP = """documentation sub-commands"""


class DocGroup(FrklBaseCommand):
    def __init__(
        self,
        typistry: Tingistry,
        plugin_classes: Iterable[Type],
        name: str = "doc",
        terminal: Terminal = None,
        **kwargs,
    ):
        """Install"""

        # self.print_version_callback = print_version_callback
        self._tingistry: Tingistry = typistry
        self._typistry: Typistry = self._tingistry.typistry
        kwargs["help"] = PLUGIN_HELP

        self._plugin_classes = plugin_classes
        self._plugin_managers: Dict[str, TypistryPluginManager] = {}

        super(DocGroup, self).__init__(
            name=name, arg_hive=self._tingistry.arg_hive, **kwargs
        )

    def get_plugin_manager(self, plugin_name: str):

        if plugin_name in self._plugin_managers.keys():
            return self._plugin_managers[plugin_name]

        plugin_cls = None
        for pcls in self._plugin_classes:
            if hasattr(pcls, "_plugin_name"):
                pn = pcls._plugin_name
            else:
                raise NotImplementedError()
            if pn == plugin_name:
                plugin_cls = pcls
        if plugin_cls is None:
            raise ValueError(f"No plugin class found for: {plugin_name}")

        pm = self._typistry.get_plugin_manager(plugin_cls)
        if pm is None:
            raise ValueError(f"No plugin manager for plugin type: {plugin_name}")

        self._plugin_managers[plugin_name] = pm
        return self._plugin_managers[plugin_name]

    async def _list_commands(self, ctx):

        result = []
        for p in self._plugins:
            command = await p.get_command()
            result.append(command.name)

        return result

    async def _get_command(self, ctx, name):

        for p in self._plugins:
            command = await p.get_command()
            if command.name == name:
                return command

        return None
