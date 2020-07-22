# -*- coding: utf-8 -*-
import logging

import asyncclick as click
from bring.bring import Bring
from bring.interfaces.cli import console
from frkl.common.cli.exceptions import handle_exc_async


log = logging.getLogger("bring")

PLUGIN_HELP = """Execute one of the available plugins"""


# class BringPluginGroup(FrklBaseCommand):
#     def __init__(
#         self, bring: Bring, name: str = None, terminal: Terminal = None, **kwargs
#     ):
#         """Install"""
#
#         # self.print_version_callback = print_version_callback
#         self._bring = bring
#         kwargs["help"] = PLUGIN_HELP
#
#         self._plugins: List[BringCliPlugin] = get_cli_plugins(self._bring)
#
#         super(BringPluginGroup, self).__init__(
#             name=name, arg_hive=bring.arg_hive, **kwargs
#         )
#
#     async def _list_commands(self, ctx):
#
#         result = []
#         for p in self._plugins:
#             command = await p.get_command()
#             result.append(command.name)
#
#         return result
#
#     async def _get_command(self, ctx, name):
#
#         for p in self._plugins:
#             command = await p.get_command()
#             if command.name == name:
#                 return command
#
#         return None


@click.command()
@click.pass_context
@handle_exc_async
async def plugin(ctx):
    """Clear the bring cache dir in the relevant locaiont (e.g. '~/.cache/bring' on Linux)."""

    bring: Bring = ctx.obj["bring"]

    print(bring)

    fc = {"type": "template"}

    frecklet = await bring.freckles.create_frecklet(fc)

    frecklet.input_sets.add_input_values(template="zile-config")
    print(frecklet)

    msg = await frecklet.get_msg()
    print(msg)
    pi = frecklet.input_sets.explain()
    console.print(pi)

    vals = await frecklet.get_values(raise_exception=True)
    print(vals)

    # result = await frecklet.get_frecklet_result()
    # console.print(result)
