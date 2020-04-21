# -*- coding: utf-8 -*-
import logging
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, List, Optional

from asyncclick import Command
from blessed import Terminal
from frtls.cli.group import FrklBaseCommand
from frtls.cli.terminal import create_terminal
from frtls.types.typistry import Typistry


if TYPE_CHECKING:
    from bring.bring import Bring

log = logging.getLogger("bring")


def get_cli_plugins(
    bring: "Bring", terminal: Optional[Terminal] = None
) -> List["BringCliPlugin"]:

    typistry: Typistry = bring.typistry
    plugin_manager = typistry.get_plugin_manager(BringCliPlugin, plugin_type="instance")

    result = []
    for pn in plugin_manager.plugin_names:
        p = plugin_manager.get_plugin(pn)
        obj = p(bring=bring, terminal=terminal)
        result.append(obj)

    return result


class BringCliPlugin(metaclass=ABCMeta):
    def __init__(self, bring: "Bring", terminal: Optional[Terminal] = None):

        self._bring: "Bring" = bring
        if terminal is None:
            terminal = create_terminal()

        self._terminal = terminal
        self._command: Optional[Command] = None

    @property
    def bring(self):

        return self._bring

    @property
    def terminal(self):

        return self._terminal

    async def get_command(self):

        if self._command is None:
            self._command = await self.create_command()
        return self._command

    @abstractmethod
    async def create_command(self) -> Command:

        pass


class AbstractBringCommand(FrklBaseCommand):
    def __init__(
        self, name: str, bring: "Bring", terminal: Optional[Terminal] = None, **kwargs
    ):

        self._bring: "Bring" = bring

        if terminal is None:
            terminal = create_terminal()
        self._terminal = terminal

        super().__init__(name=name, arg_hive=self._bring.arg_hive, **kwargs)
