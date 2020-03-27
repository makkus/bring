# -*- coding: utf-8 -*-
import os
from typing import Iterable, MutableMapping, Optional

import asyncclick as click
from bring.bring import Bring
from bring.context import BringContextTing
from bring.pkg import PkgTing
from bring.utils.git import ensure_repo_cloned
from bring.utils.pkgs import create_pkg_info_table_string
from frtls.cli.group import FrklBaseCommand
from frtls.defaults import DEFAULT_URL_ABBREVIATIONS_GIT_REPO
from frtls.strings import expand_git_url, is_url_or_abbrev
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
                with formatter.section("Contexts"):
                    formatter.write_dl(rows)

    @click.pass_context
    async def all_info(ctx, self, *args, **kwargs):

        if ctx.invoked_subcommand:  # type: ignore
            return

        print()
        all: Iterable[PkgTing] = await self._bring.get_all_pkgs()
        pkgs: MutableMapping[BringContextTing, PkgTing] = SortedDict()

        for pkg in all:
            pkgs.setdefault(pkg.bring_context, []).append(pkg)

        for c in self._bring.contexts.values():
            if c not in pkgs.keys():
                pkgs[c] = []

        for _context, _pkgs in pkgs.items():
            print(
                f"{self._terminal.bold}context: {_context.name}{self._terminal.normal}"
            )
            print()
            if not _pkgs:
                print("  No packages")
            else:
                table_str = await create_pkg_info_table_string(_pkgs, header=False)
                click.echo(table_str)
            print()

    async def _list_commands(self, ctx):

        return sorted(self._bring.contexts.keys())

    async def _get_command(self, ctx, name):

        context = self._bring.contexts.get(name, None)
        if context is None:

            if is_url_or_abbrev(name, DEFAULT_URL_ABBREVIATIONS_GIT_REPO):

                git_url = expand_git_url(name, DEFAULT_URL_ABBREVIATIONS_GIT_REPO)
                full_path = await ensure_repo_cloned(git_url, update=True)
            else:
                full_path = os.path.realpath(os.path.expanduser(name))

            if not os.path.isdir(full_path):
                return None

            context = self._bring.add_context_from_folder(full_path)
            _ctx_name = context.full_name

        else:
            _ctx_name = name

        @click.command(_ctx_name)
        @click.pass_context
        async def command(ctx, **kwargs):

            print()

            _pkgs = await context.get_pkgs()

            if not _pkgs:
                print("  No packages")
            else:
                table_str = await create_pkg_info_table_string(_pkgs.values())
                click.echo(table_str)
            print()

        ctx_info = await context.get_info()
        command.short_help = ctx_info.get("slug", "n/a")

        return command
