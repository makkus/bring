# -*- coding: utf-8 -*-
from typing import Dict

import asyncclick as click

from bring.bring import Bringistry
from frtls.cli.exceptions import handle_exc_async
from frtls.cli.group import FrklBaseCommand

# from click import Path
# from click_aliases import ClickAliasedGroup

click.anyio_backend = "asyncio"


class BringInfoGroup(FrklBaseCommand):
    def __init__(
        self,
        name=None,
        print_version_callback=None,
        invoke_without_command=False,
        no_args_is_help=None,
        chain=False,
        result_callback=None,
        **kwargs
    ):

        self.print_version_callback = print_version_callback
        # self.params[:0] = self.get_common_options(
        #     print_version_callback=self.print_version_callback
        # )

        super(FrklBaseCommand, self).__init__(
            name=name,
            invoke_without_command=invoke_without_command,
            no_args_is_help=False,
            chain=False,
            result_callback=None,
            **kwargs
        )
        self._bringistry: Bringistry = None

    def init_command(self, ctx):
        self._bringistry = ctx.obj["bringistry"]

    def get_common_options(self) -> Dict[str, Dict]:
        return {}

    async def _list_commands(self):

        pkg_names = self._bringistry.get_pkg_names()
        return pkg_names

    async def _get_command(self, name):

        pkg = self._bringistry.get_pkg(name)

        @click.command(name=name)
        @handle_exc_async
        async def command(**vars):

            info = await pkg.get_info()
            import pp

            pp(info)
            return "XXXX"

        vals = await pkg.get_values("args")
        params = vals["args"].to_cli_options()
        command.params = params

        return command
