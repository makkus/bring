# -*- coding: utf-8 -*-
from typing import Dict, Optional, Union

import asyncclick as click
from bring.bring import Bring
from bring.context import BringContextTing
from bring.defaults import DEFAULT_INSTALL_PROFILE_NAME
from frtls.args.arg import Arg, RecordArg
from frtls.cli.exceptions import handle_exc_async
from frtls.cli.group import FrklBaseCommand


class BringInstallGroup(FrklBaseCommand):
    def __init__(
        self,
        bring: Bring,
        name: str = None,
        context: Optional[BringContextTing] = None,
        **kwargs
        # print_version_callback=None,
        # invoke_without_command=False,
    ):

        # self.print_version_callback = print_version_callback
        self._bring = bring

        self._context: Optional[BringContextTing] = context

        super(BringInstallGroup, self).__init__(
            name=name,
            # invoke_without_command=invoke_without_command,
            no_args_is_help=False,
            chain=False,
            result_callback=None,
            arg_hive=bring.arg_hive,
            **kwargs
        )

    def get_common_options(self) -> Union[Arg, Dict]:

        return {
            "target": {
                "doc": "The target directory to install the files into.",
                "type": "string",
                "required": False,
            },
            "profile": {
                "doc": "One or several profiles to use.",
                "type": "[string]",
                "default": [DEFAULT_INSTALL_PROFILE_NAME],
                "multiple": True,
                "required": False,
            },
            "merge": {
                "doc": "Whether to merge the resulting files (if applicable).",
                "type": "boolean",
                "required": False,
                "default": True,
                "cli": {"param_decls": ["--merge/--no-merge"]},
            },
            "strategy": {
                "doc": "Strategy on how to deal with existing files, options: default, force",
                "type": "string",
                "default": "default",
                "required": False,
            },
            "write_metadata": {
                "doc": "Write metadata for this install process.",
                "type": "boolean",
                "default": False,
                "required": False,
            },
        }

    # async def init_command_async(self, ctx):
    #
    #     await self._bring.init()

    async def _list_commands(self, ctx):

        if self._context is not None:
            pkg_names = await self._context.pkg_names
            return pkg_names

        return []

    async def _get_command(self, ctx, name):

        if self._context is not None:
            pkg = await self._context.get_pkg(name)

            @click.command(name=name)
            @handle_exc_async
            async def command(**vars):

                target = self._group_params.get("target")
                # profiles = self._group_params.get("profile")
                # strategy = self._group_params.get("strategy")
                # merge = self._group_params.get("merge")
                #
                # write_metadata = self._group_params.get("write_metadata")

                path = await pkg.create_version_folder(vars=vars, target=target)
                print(path)

            try:
                vals = await pkg.get_values("args", "info", raise_exception=True)
                args: RecordArg = vals["args"]
                info: Dict = vals["info"]
                params = args.to_cli_options()
                command.params = params
                command.short_help = info.get("slug", "n/a")
            except (Exception) as e:
                return e

        else:

            @click.command(name)
            @handle_exc_async
            async def command(**vars):

                # target = self._group_params.get("target")
                # profiles = self._group_params.get("profile")
                # strategy = self._group_params.get("strategy")
                # merge = self._group_params.get("merge")
                #
                # write_metadata = self._group_params.get("write_metadata")

                print("HELLO")

        return command
