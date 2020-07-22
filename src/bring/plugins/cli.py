# -*- coding: utf-8 -*-
import logging
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, List, Optional

from asyncclick import Command
from frkl.args.cli.click_commands import FrklBaseCommand
from frkl.types.typistry import Typistry


if TYPE_CHECKING:
    from bring.bring import Bring

log = logging.getLogger("bring")


def get_cli_plugins(bring: "Bring") -> List["BringCliPlugin"]:

    typistry: Typistry = bring.typistry
    plugin_manager = typistry.get_plugin_manager(BringCliPlugin)

    result = []
    for pn in plugin_manager.plugin_names:
        p = plugin_manager.get_plugin(pn)
        obj = p(bring=bring)
        result.append(obj)

    return result


class BringCliPlugin(metaclass=ABCMeta):

    _plugin_type = "instance"

    def __init__(self, bring: "Bring"):

        self._bring: "Bring" = bring
        self._command: Optional[Command] = None

    @property
    def bring(self):

        return self._bring

    async def get_command(self):

        if self._command is None:
            self._command = await self.create_command()
        return self._command

    @abstractmethod
    async def create_command(self) -> Command:

        pass


class AbstractBringCommand(FrklBaseCommand):
    def __init__(self, name: str, bring: "Bring", **kwargs):

        self._bring: "Bring" = bring

        super().__init__(name=name, arg_hive=self._bring.arg_hive, **kwargs)
