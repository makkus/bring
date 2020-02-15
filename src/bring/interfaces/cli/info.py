# -*- coding: utf-8 -*-
from typing import Dict

import arrow
import asyncclick as click
from colored import style

from bring.bring import Bringistry
from frtls.args.arg import RecordArg
from frtls.cli.exceptions import handle_exc_async
from frtls.cli.group import FrklBaseCommand
from frtls.formats.output import serialize


class BringInfoGroup(FrklBaseCommand):
    def __init__(
        self,
        bringistry: Bringistry,
        name=None,
        print_version_callback=None,
        no_args_is_help=None,
        chain=False,
        result_callback=None,
        **kwargs,
    ):

        self.print_version_callback = print_version_callback
        # self.params[:0] = self.get_common_options(
        #     print_version_callback=self.print_version_callback
        # )
        self._bringistry: Bringistry = bringistry
        self._pkgs = self._bringistry.tingistry.get_ting(
            "bring.pkgs", raise_exception=True
        )

        super(BringInfoGroup, self).__init__(
            name=name,
            invoke_without_command=True,
            no_args_is_help=False,
            chain=False,
            result_callback=None,
            callback=self.all_info,
            arg_hive=bringistry.tingistry._arg_hive,
            **kwargs,
        )

    @click.pass_context
    async def all_info(ctx, self, *args, **kwargs):

        if ctx.invoked_subcommand:
            return

        self._init_command(ctx)

        click.echo()
        click.echo("Available packages:")
        click.echo()
        for pkg_name, pkg in self._pkgs.get_pkgs().items():
            info = await pkg.get_info()
            slug = info["info"].get("slug", "no description available")
            click.echo(f"  - {style.BOLD}{pkg_name}{style.RESET}: {slug}")

    def get_common_options(self) -> Dict[str, Dict]:
        return {
            "full": {
                "type": "boolean",
                "doc": "Display full info.",
                "required": False,
                "default": False,
            }
        }

    async def _list_commands(self):

        pkg_names = self._bringistry.pkgs.get_pkg_names()
        return pkg_names

    async def _get_command(self, name):

        pkg = self._pkgs.get_pkg(name)

        @click.command(name=name)
        @handle_exc_async
        async def command(**vars):

            full = self._group_params["full"]
            info = await pkg.get_info(include_metadata=True)

            metadata = info["metadata"]
            age = arrow.get(metadata["timestamp"])

            to_print = {}
            to_print["info"] = info["info"]
            to_print["labels"] = info["labels"]
            to_print["metadata snapshot"] = age.humanize()
            to_print["vars"] = {
                "defaults": metadata["defaults"],
                "aliases": metadata["aliases"],
                "values": metadata["allowed_values"],
            }
            if full:
                to_print["version list"] = metadata["version_list"]

            click.echo()
            click.echo(serialize(to_print, format="yaml"))

        try:
            vals = await pkg.get_values("args", raise_exception=True)
            args: RecordArg = vals["args"]
            params = args.to_cli_options()
            command.params = params
        except (Exception) as e:
            return e

        return command
