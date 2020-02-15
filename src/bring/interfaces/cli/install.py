# -*- coding: utf-8 -*-
from typing import Dict, Union

import asyncclick as click

from frtls.args.arg import Arg, RecordArg
from frtls.cli.exceptions import handle_exc_async
from frtls.cli.group import FrklBaseCommand

# from click import Path
# from click_aliases import ClickAliasedGroup

click.anyio_backend = "asyncio"


class BringInstallGroup(FrklBaseCommand):
    def __init__(
        self,
        bringistry,
        name=None,
        # print_version_callback=None,
        # invoke_without_command=False,
    ):

        # self.print_version_callback = print_version_callback
        self._bringistry = bringistry

        super(BringInstallGroup, self).__init__(
            name=name,
            # invoke_without_command=invoke_without_command,
            no_args_is_help=False,
            chain=False,
            result_callback=None,
            arg_hive=bringistry._arg_hive,
        )

    def get_common_options(self) -> Union[Arg, Dict]:

        return {
            "target": {
                "doc": "The target directory to install the files into.",
                "type": "string",
                "default": ".",
            },
            "profile": {
                "doc": "One or several profiles to use.",
                "type": "[string]",
                "default": ["all"],
                "multiple": True,
            },
            "strategy": {
                "doc": "Strategy on how to deal with existing files, options: default, force",
                "type": "string",
                "default": "default",
            },
            "write_metadata": {
                "doc": "Write metadata for this install process.",
                "type": "boolean",
                "default": False,
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
            profiles = self._group_params.get("profile")
            strategy = self._group_params.get("strategy")

            write_metadata = self._group_params.get("write_metadata")

            result = await pkg.install(
                vars=vars,
                profiles=profiles,
                target=target,
                strategy=strategy,
                write_metadata=write_metadata,
            )

            print(result)

            # if copied:
            #     click.echo()
            #     click.echo("Copied files:\n")
            #     print(copied)
            #     for c in copied["target"].keys():
            #         click.echo(f"  - {c}")
            # else:
            #     click.echo()
            #     click.echo("No files copied.")

        try:
            vals = await pkg.get_values("args", raise_exception=True)
            args: RecordArg = vals["args"]
            params = args.to_cli_options()
            command.params = params
        except (Exception) as e:
            return e

        return command
