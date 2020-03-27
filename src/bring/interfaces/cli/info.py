# -*- coding: utf-8 -*-
from typing import Iterable, MutableMapping, Optional

import asyncclick as click
from bring.bring import Bring
from bring.context import BringContextTing
from bring.pkg import PkgTing
from frtls.cli.exceptions import handle_exc_async
from frtls.cli.group import FrklBaseCommand
from sortedcontainers import SortedDict


class BringListPkgsGroup(FrklBaseCommand):
    def __init__(
        self,
        bring: Bring,
        context: Optional[BringContextTing] = None,
        name=None,
        **kwargs,
    ):

        self._bring: Bring = bring

        super(BringListPkgsGroup, self).__init__(
            name=name,
            invoke_without_command=True,
            no_args_is_help=False,
            chain=False,
            result_callback=None,
            callback=self.all_info,
            arg_hive=bring.arg_hive,
            **kwargs,
        )

    @click.pass_context
    async def all_info(ctx, self, *args, **kwargs):

        if ctx.invoked_subcommand:  # type: ignore
            return

        print()
        print(f"{self.terminal.bold}Available contexts:{self.terminal.normal}")
        print()
        all: Iterable[PkgTing] = await self._bring.get_all_pkgs()
        pkgs: MutableMapping[BringContextTing, PkgTing] = SortedDict()

        for pkg in all:
            pkgs.setdefault(pkg.bring_context, []).append(pkg)

        for c in self._bring.contexts.values():
            if c not in pkgs.keys():
                pkgs[c] = []

        for _context, _pkgs in pkgs.items():
            print(f"{self._terminal.bold}{_context.name}{self._terminal.normal}")
            print()
            if not _pkgs:
                print("    No packages")
            else:
                print("  Packages:")
                print()
                for p in sorted(_pkgs):
                    print(f"    - {p.name}")
            print()

    async def _list_commands(self, ctx):

        return sorted(self._bring.contexts.keys())

    async def _get_command(self, ctx, name):
        @click.command(name=name)
        @click.option("--update", "-u", help="update metadata", is_flag=True)
        @click.option("--full", "-f", help="display full info", is_flag=True)
        @handle_exc_async
        async def command(update: bool, full: bool):
            pass
            # args: Dict[str, Any] = {"include_metadata": True}
            # if update:
            #     args["retrieve_config"] = {"metadata_max_age": 0}
            # info = await pkg.get_info(**args)
            #
            # metadata = info["metadata"]
            # age = arrow.get(metadata["timestamp"])

            # to_print = {}
            # to_print["info"] = info["info"]
            # to_print["labels"] = info["labels"]
            # to_print["metadata snapshot"] = age.humanize()
            # to_print["args"] = metadata["pkg_args"]
            # to_print["aliases"] = metadata["aliases"]
            #
            # if full:
            #     to_print["version list"] = metadata["version_list"]
            #
            # click.echo()
            # click.echo(serialize(to_print, format="yaml"))

        # vals = await pkg.get_values("info")
        # command.short_help = vals["info"].get("slug", "n/a")

        return command
