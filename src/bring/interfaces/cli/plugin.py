# -*- coding: utf-8 -*-
import logging
from typing import List

from blessed import Terminal
from bring.bring import Bring
from bring.plugins.cli import BringCliPlugin, get_cli_plugins
from frtls.cli.group import FrklBaseCommand


log = logging.getLogger("bring")

PLUGIN_HELP = """Execute one of the available plugins"""


class BringPluginGroup(FrklBaseCommand):
    def __init__(
        self, bring: Bring, name: str = None, terminal: Terminal = None, **kwargs
    ):
        """Install"""

        # self.print_version_callback = print_version_callback
        self._bring = bring
        kwargs["help"] = PLUGIN_HELP

        self._plugins: List[BringCliPlugin] = get_cli_plugins(self._bring)

        super(BringPluginGroup, self).__init__(
            name=name, arg_hive=bring.arg_hive, **kwargs
        )

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
