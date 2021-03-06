# -*- coding: utf-8 -*-
from typing import Any, Mapping, Optional

import asyncclick as click
from bring.bring import Bring
from bring.pkg import PkgTing
from bring.pkg_index.index import BringIndexTing
from bring.utils import parse_pkg_string
from bring.utils.pkgs import (
    create_info_table_string,
    create_pkg_info_table_string,
    get_values_for_pkgs,
)
from frkl.args.cli.click_commands import FrklBaseCommand
from frkl.common.strings import reindent


class BringListPkgsGroup(FrklBaseCommand):
    def __init__(
        self, bring: Bring, index: Optional[BringIndexTing] = None, name=None, **kwargs
    ):

        self._bring: Bring = bring

        super(BringListPkgsGroup, self).__init__(
            name=name,
            invoke_without_command=True,
            no_args_is_help=False,
            chain=False,
            result_callback=None,
            callback=self.all_info,
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

        click.echo()
        # all: Iterable[PkgTing] = await self._tingistry.get_all_pkgs()
        index_ids = self._bring.index_ids

        pkgs: Mapping[str, PkgTing] = await self._bring.get_alias_pkg_map()

        pkgs_info: Mapping[str, Any] = await get_values_for_pkgs(pkgs, "info")

        index_info = {}
        for pkg_name, info in pkgs_info.items():
            pkg_name, index_name = parse_pkg_string(pkg_name)
            if index_name is None:
                raise Exception(
                    f"No index name for pkg: {pkg_name}. This is most likely a bug."
                )
            index_info.setdefault(index_name, {})[pkg_name] = info

        for idx_id in index_ids:
            click.secho(idx_id, bold=True)
            click.echo()
            table = create_info_table_string(index_info[idx_id])
            click.echo(reindent(table, 2))
            click.echo()

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
                table_str = await create_pkg_info_table_string(_pkgs)
                click.echo(table_str)
            print()

        ctx_info = await index.get_info()
        command.short_help = ctx_info.get("slug", "n/a")

        return command
