# -*- coding: utf-8 -*-
from typing import MutableMapping, Optional

import asyncclick as click
from bring.bring import Bring
from bring.pkg_index.index import BringIndexTing
from bring.pkg_index.pkg import PkgTing
from bring.utils.pkgs import create_pkg_info_table_string
from frtls.cli.group import FrklBaseCommand


class BringListPkgsGroup(FrklBaseCommand):
    def __init__(
        self, bring: Bring, index: Optional[BringIndexTing] = None, name=None, **kwargs
    ):

        self._bring: Bring = bring

        super(BringListPkgsGroup, self).__init__(
            name=name,
            invoke_without_command=True,
            no_args_is_help=True,
            chain=False,
            result_callback=None,
            # callback=self.all_info,
            arg_hive=bring.arg_hive,
            subcommand_metavar="CONTEXT",
            **kwargs,
        )

    def format_commands(self, ctx, formatter):
        """Extra format methods for multi methods that adds all the commands
        after the options.
        """
        commands = []
        for subcommand in self.list_commands(ctx):
            cmd = self.get_command(ctx, subcommand)
            # What is this, the tool lied about a command.  Ignore it
            if cmd is None:
                continue
            if cmd.hidden:
                continue

            commands.append((subcommand, cmd))

        # allow for 3 times the default spacing
        if len(commands):
            limit = formatter.width - 6 - max(len(cmd[0]) for cmd in commands)

            rows = []
            for subcommand, cmd in commands:
                help = cmd.get_short_help_str(limit)
                rows.append((subcommand, help))

            if rows:
                with formatter.section("Indexes"):
                    formatter.write_dl(rows)

    @click.pass_context
    async def all_info(ctx, self, *args, **kwargs):

        if ctx.invoked_subcommand:  # type: ignore
            return

        print()
        # all: Iterable[PkgTing] = await self._tingistry.get_all_pkgs()
        pkgs: MutableMapping[BringIndexTing, PkgTing] = {}

        for pkg in all:
            pkgs.setdefault(pkg.bring_index, []).append(pkg)

        all_indexes = self._bring.indexes
        for c in all_indexes.values():
            if c not in pkgs.keys():
                pkgs[c] = []

        default_index = await self._tingistry.config.get_default_index()

        for _index, _pkgs in pkgs.items():
            if _index.name == default_index:
                _default_marker = " (default index)"
            else:
                _default_marker = ""
            print(f"index: {_index.name}{_default_marker}")
            print()
            if not _pkgs:
                print("  No packages")
            else:
                table_str = await create_pkg_info_table_string(_pkgs, header=False)
                click.echo(table_str)
            print()

    async def _list_commands(self, ctx):

        return sorted(self._bring.index_ids)

    async def _get_command(self, ctx, name):

        index = await self._bring.get_index(name)
        _ctx_name = index.name

        @click.command(_ctx_name)
        @click.pass_context
        async def command(ctx, **kwargs):

            print()

            _pkgs = await index.get_pkgs()

            if not _pkgs:
                print("  No packages")
            else:
                table_str = await create_pkg_info_table_string(_pkgs.values())
                click.echo(table_str)
            print()

        ctx_info = await index.get_info()
        command.short_help = ctx_info.get("slug", "n/a")

        return command
