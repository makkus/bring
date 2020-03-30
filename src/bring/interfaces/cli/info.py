# -*- coding: utf-8 -*-
import os
from typing import Dict, Union

from bring.bring import Bring
from bring.interfaces.cli.pkg_command import PkgInfoTingCommand
from bring.utils.git import ensure_repo_cloned
from frtls.args.arg import Arg
from frtls.cli.group import FrklBaseCommand
from frtls.defaults import DEFAULT_URL_ABBREVIATIONS_GIT_REPO
from frtls.strings import expand_git_url, is_url_or_abbrev


class BringInfoPkgsGroup(FrklBaseCommand):
    def __init__(self, bring: Bring, name=None, **kwargs):

        self._bring: Bring = bring

        super(BringInfoPkgsGroup, self).__init__(
            name=name,
            invoke_without_command=False,
            no_args_is_help=False,
            chain=False,
            result_callback=None,
            # callback=self.all_info,
            arg_hive=bring.arg_hive,
            subcommand_metavar="PKG",
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
                with formatter.section("Packages"):
                    formatter.write_dl(rows)

    def get_common_options(self) -> Union[Arg, Dict]:

        return {
            "context": {
                "doc": "The context that contains the package.",
                "type": "string",
                # "multiple": False,
                "required": False,
            }
        }

    # @click.pass_context
    # async def all_info(ctx, self, *args, **kwargs):
    #
    #     if ctx.invoked_subcommand:  # type: ignore
    #         return
    #
    #     print()
    #     print(f"{self.terminal.bold}Available contexts:{self.terminal.normal}")
    #     print()
    #     all: Iterable[PkgTing] = await self._bring.get_all_pkgs()
    #     pkgs: MutableMapping[BringContextTing, PkgTing] = SortedDict()
    #
    #     for pkg in all:
    #         pkgs.setdefault(pkg.bring_context, []).append(pkg)
    #
    #     for c in self._bring.contexts.values():
    #         if c not in pkgs.keys():
    #             pkgs[c] = []
    #
    #     for _context, _pkgs in pkgs.items():
    #         print(f"{self._terminal.bold}{_context.name}{self._terminal.normal}")
    #         print()
    #         if not _pkgs:
    #             print("    No packages")
    #         else:
    #             print("  Packages:")
    #             print()
    #             for p in sorted(_pkgs):
    #                 print(f"    - {p.name}")
    #         print()

    async def _list_commands(self, ctx):

        return []

    async def _get_command(self, ctx, name):

        context_name = self._group_params.get("context", None)

        context = self._bring.get_context(context_name, raise_exception=False)

        if context is None:

            if is_url_or_abbrev(context_name, DEFAULT_URL_ABBREVIATIONS_GIT_REPO):

                git_url = expand_git_url(
                    context_name, DEFAULT_URL_ABBREVIATIONS_GIT_REPO
                )
                full_path = await ensure_repo_cloned(git_url, update=True)
            else:
                full_path = os.path.realpath(os.path.expanduser(context_name))

            if not os.path.isdir(full_path):
                return None

            alias = full_path.replace(os.path.sep, ".")[1:]
            alias = alias.replace("..", ".")
            self._bring.add_context_from_folder(full_path, alias=alias)
            _ctx_name = alias

        else:
            _ctx_name = context_name

        load_details = not ctx.obj.get("list_install_commands", False)

        pkg = await self._bring.find_pkg(name, contexts=[_ctx_name])

        command = PkgInfoTingCommand(
            name=name, pkg=pkg, load_details=load_details, terminal=self._terminal
        )
        return command
