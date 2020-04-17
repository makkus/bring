# -*- coding: utf-8 -*-
from typing import Dict, Union

from bring.bring import Bring
from bring.interfaces.cli.pkg_command import PkgInstallTingCommand
from bring.utils.contexts import ensure_context
from frtls.args.arg import Arg
from frtls.cli.group import FrklBaseCommand


INSTALL_HELP = """Install one or several packages."""


class BringInstallGroup(FrklBaseCommand):
    def __init__(
        self,
        bring: Bring,
        name: str = None,
        **kwargs
        # print_version_callback=None,
        # invoke_without_command=False,
    ):
        """Install"""

        # self.print_version_callback = print_version_callback
        self._bring = bring
        kwargs["help"] = INSTALL_HELP

        super(BringInstallGroup, self).__init__(
            name=name,
            invoke_without_command=True,
            no_args_is_help=True,
            chain=False,
            result_callback=None,
            arg_hive=bring.arg_hive,
            subcommand_metavar="PKG",
            **kwargs
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
            },
            "target": {
                "doc": "The target directory to install the files into.",
                "type": "string",
                "required": False,
            },
            # "merge": {
            #     "doc": "Whether to merge the resulting files (if applicable).",
            #     "type": "boolean",
            #     "required": False,
            #     "default": True,
            #     "cli": {"param_decls": ["--merge/--no-merge"]},
            # },
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

    async def _list_commands(self, ctx):

        return []

        # pkg_context = self._group_params.get("context")
        # if pkg_context is None:
        #     return []
        #
        # ctx.obj["list_install_commands"] = True
        #
        # pkgs = await self._bring.get_all_pkgs(contexts=[pkg_context])
        #
        # result = SortedSet()
        # for pkg in pkgs:
        #     result.add(pkg.name)
        #
        # return result

    async def _get_command(self, ctx, name):

        context_name = self._group_params.get("context", None)

        _ctx_name = await ensure_context(self._bring, name=context_name)
        self._bring.get_context(_ctx_name)

        target = self._group_params.get("target")
        strategy = self._group_params.get("strategy")
        # merge = self._group_params.get("merge")

        # write_metadata = self._group_params.get("write_metadata")

        load_details = not ctx.obj.get("list_install_commands", False)

        pkg = await self._bring.get_pkg(
            name, context_name=_ctx_name, raise_exception=True
        )

        command = PkgInstallTingCommand(
            name,
            pkg=pkg,
            target=target,
            strategy=strategy,
            terminal=self._terminal,
            load_details=load_details,
        )

        return command
