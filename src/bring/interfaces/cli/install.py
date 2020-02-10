# -*- coding: utf-8 -*-
from typing import Dict, Union

import asyncclick as click

from bring.bring import Bringistry
from frtls.args.arg import Args
from frtls.cli.exceptions import handle_exc_async
from frtls.cli.group import FrklBaseCommand

# from click import Path
# from click_aliases import ClickAliasedGroup

click.anyio_backend = "asyncio"


class BringInstallGroup(FrklBaseCommand):
    def __init__(
        self,
        name=None,
        # print_version_callback=None,
        # invoke_without_command=False,
    ):

        # self.print_version_callback = print_version_callback

        super(BringInstallGroup, self).__init__(
            name=name,
            # invoke_without_command=invoke_without_command,
            no_args_is_help=False,
            chain=False,
            result_callback=None,
        )
        self._bringistry: Bringistry = None

    def init_command(self, ctx):
        self._bringistry = ctx.obj["bringistry"]

    def get_common_options(self) -> Union[Args, Dict]:

        return {
            "target": {
                "doc": "The target directory to install the files into.",
                "type": "string",
                "default": ".",
            },
            "filter": {
                "doc": "One or several filters to use.",
                "type": "[string]",
                "default": ["all"],
                "multiple": True,
            },
            "strategy": {
                "doc": "Strategy on how to deal with existing files, options: default, force",
                "type": "string",
                "default": "default",
            },
        }

    async def _list_commands(self):

        pkg_names = self._bringistry.get_pkg_names()
        return pkg_names

    async def _get_command(self, name):

        pkg = self._bringistry.get_pkg(name)

        @click.command(name=name)
        @handle_exc_async
        async def command(**vars):

            target = self._group_params.get("target")
            profiles = self._group_params.get("filter")
            strategy = self._group_params.get("strategy")

            copied = await pkg.install(
                vars=vars, filters=profiles, target=target, strategy=strategy
            )

            if copied:
                click.echo()
                click.echo("Copied files:\n")
                for c in copied.keys():
                    click.echo(f"  - {c}")
            else:
                click.echo()
                click.echo("No files copied.")

        vals = await pkg.get_values("args")
        params = vals["args"].to_cli_options()
        command.params = params

        return command
