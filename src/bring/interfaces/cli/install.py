# -*- coding: utf-8 -*-
import os
from typing import Dict, Union

import asyncclick as click
from asyncclick import Command
from bring.bring import Bring
from bring.bring_list import BringList
from bring.interfaces.cli.utils import log, print_pkg_list_help
from bring.pkg import PkgTing
from bring.utils.pkgs import explain_version
from frtls.args.arg import Arg, RecordArg
from frtls.async_helpers import wrap_async_task
from frtls.cli.group import FrklBaseCommand
from frtls.cli.terminal import create_terminal


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
        self._bring: Bring = bring
        kwargs["help"] = INSTALL_HELP

        super(BringInstallGroup, self).__init__(
            name=name,
            invoke_without_command=True,
            no_args_is_help=True,
            chain=False,
            result_callback=None,
            arg_hive=bring.arg_hive,
            subcommand_metavar="PKG",
            **kwargs,
        )

    def format_commands(self, ctx, formatter):
        """Extra format methods for multi methods that adds all the commands
        after the options.
        """

        wrap_async_task(print_pkg_list_help, bring=self._bring, formatter=formatter)

    def get_group_options(self) -> Union[Arg, Dict]:

        return {
            # "context": {
            #     "doc": "The context that contains the package.",
            #     "type": "string",
            #     # "multiple": False,
            #     "required": False,
            # },
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
            "explain": {
                "doc": "Don't perform installation, only explain steps.",
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

        # context_name = self._group_params.get("context", None)

        target = self._group_params.get("target")
        strategy = self._group_params.get("strategy")
        # merge = self._group_params.get("merge")
        explain = self._group_params.get("explain")

        # write_metadata = self._group_params.get("write_metadata")

        load_details = not ctx.obj.get("list_install_commands", False)

        if not load_details:
            return None

        if os.path.isfile(name):

            bring_list = await BringList.from_file(name)

            @click.command()
            @click.pass_context
            async def command(ctx):

                await bring_list.install(bring=self._bring)

            return command

        else:

            pkg = await self._bring.get_pkg(name=name, raise_exception=True)

            command = PkgInstallTingCommand(
                name,
                pkg=pkg,
                target=target,
                strategy=strategy,
                explain=explain,
                terminal=self._terminal,
                load_details=load_details,
            )

            return command


class PkgInstallTingCommand(Command):
    def __init__(
        self,
        name: str,
        pkg: PkgTing,
        target: str,
        strategy: str,
        explain: bool = False,
        load_details: bool = False,
        terminal=None,
        **kwargs,
    ):

        self._pkg: PkgTing = pkg

        self._target = target
        self._strategy = strategy

        self._explain: bool = explain

        if terminal is None:
            terminal = create_terminal()
        self._terminal = terminal

        try:
            if load_details:
                val_names = ["info", "args"]
            else:
                val_names = ["info"]
            vals = wrap_async_task(
                self._pkg.get_values, *val_names, _raise_exception=True
            )
            info = vals["info"]
            slug = info.get("slug", "n/a")
            if slug.endswith("."):
                slug = slug[0:-1]
            short_help = f"{slug} (from: {self._pkg.bring_context.name})"

            kwargs["short_help"] = short_help
            desc = info.get("desc", None)
            help = f"Install the '{self._pkg.name}' package."
            if desc:
                help = f"{help}\n\n{desc}"

            if load_details:
                args: RecordArg = vals["args"]
                params = args.to_cli_options(
                    add_defaults=False, remove_required_when_default=True
                )
                kwargs["params"] = params

            kwargs["help"] = help
        except (Exception) as e:
            log.debug(f"Can't create PkgInstallTingCommand object: {e}", exc_info=True)
            raise e

        super().__init__(name=name, callback=self.install, **kwargs)

    async def install(self, **kwargs):

        _vars = {}
        for k, v in kwargs.items():
            if v is not None:
                _vars[k] = v

        if self._explain:
            click.echo()

            explanation = await explain_version(
                pkg=self._pkg, target=self._target, **_vars
            )
            click.echo(explanation)
        else:

            path = await self._pkg.create_version_folder(
                vars=_vars, target=self._target
            )
            print(path)
