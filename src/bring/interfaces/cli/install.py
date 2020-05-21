# -*- coding: utf-8 -*-
import os
from typing import Dict, Optional, Union

import asyncclick as click
from asyncclick import Command
from bring.assembly import PkgAssembly
from bring.assembly.utils import PkgAssemblyExplanation
from bring.bring import Bring
from bring.interfaces.cli import console
from bring.interfaces.cli.utils import log, print_pkg_list_help
from bring.pkg_index.pkg import PkgTing
from bring.utils.pkgs import PkgVersionExplanation
from frtls.args.arg import Arg, RecordArg
from frtls.async_helpers import wrap_async_task
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
            # "index": {
            #     "doc": "The index that contains the package.",
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

        # pkg_index = self._group_params.get("index")
        # if pkg_index is None:
        #     return []
        #
        # ctx.obj["list_install_commands"] = True
        #
        # pkgs = await self._bring.get_all_pkgs(indexes=[pkg_index])
        #
        # result = SortedSet()
        # for pkg in pkgs:
        #     result.add(pkg.name)
        #
        # return result

    async def _get_command(self, ctx, name):

        # index_name = self._group_params.get("index", None)

        target = self._group_params.get("target")
        strategy = self._group_params.get("strategy")
        # merge = self._group_params.get("merge")
        explain = self._group_params.get("explain")

        # write_metadata = self._group_params.get("write_metadata")

        load_details = not ctx.obj.get("list_install_commands", False)

        if not load_details:
            return None

        if os.path.isfile(name):

            pkg_assembly = await PkgAssembly.from_file(name)

            command = PkgBringInsCommand(
                name,
                pkg_assembly=pkg_assembly,
                bring=self._bring,
                target=target,
                strategy=strategy,
                explain=explain,
                load_details=load_details,
            )

            return command

        else:

            # pkg = await self._bring.get_pkg(name=name, raise_exception=True)

            command = PkgInstallTingCommand(
                name,
                bring=self._bring,
                target=target,
                strategy=strategy,
                explain=explain,
                load_details=load_details,
            )

            return command


class PkgBringInsCommand(Command):
    def __init__(
        self,
        name: str,
        pkg_assembly: PkgAssembly,
        bring: Bring,
        target: str,
        strategy: str,
        explain: bool = False,
        load_details: bool = False,
        **kwargs,
    ):

        self._pkg_assembly: PkgAssembly = pkg_assembly
        self._bring = bring

        self._target = target
        self._strategy = strategy

        self._explain: bool = explain

        self._args: Optional[RecordArg] = None

        try:
            doc = self._pkg_assembly.doc

            if load_details:
                arg_map = self._pkg_assembly.args
                self._args = self._bring.arg_hive.create_record_arg(arg_map)
                params = self._args.to_cli_options(
                    add_defaults=False, remove_required_when_default=True
                )
                kwargs["params"] = params

                kwargs["help"] = doc.get_help(use_short_help=True)

            kwargs["short_help"] = doc.get_short_help(use_help=True)
        except (Exception) as e:
            log.debug(f"Can't create PkgInstallTingCommand object: {e}", exc_info=True)
            raise e

        super().__init__(name=name, callback=self.install, **kwargs)

    async def install(self, **kwargs):

        _vars = self._args.from_cli_input(_remove_none_values=True, **kwargs)

        if self._explain:
            click.echo()

            explanation = PkgAssemblyExplanation(
                bring=self._bring,
                pkg_assembly=self._pkg_assembly,
                target=self._target,
                **_vars,
            )
            console.print(explanation)

        else:

            path = await self._pkg_assembly.install(bring=self._bring, vars=_vars)
            print(path)


class PkgInstallTingCommand(Command):
    def __init__(
        self,
        name: str,
        bring: Bring,
        target: str,
        strategy: str,
        explain: bool = False,
        load_details: bool = False,
        **kwargs,
    ):

        self._bring: Bring = bring
        self._pkg: PkgTing = wrap_async_task(
            self._bring.get_pkg, name=name, raise_exception=True
        )

        self._target = target
        self._strategy = strategy

        self._explain: bool = explain

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
            short_help = f"{slug} (from: {self._pkg.bring_index.name})"

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

            explanation = PkgVersionExplanation(
                pkg=self._pkg, target=self._target, **_vars
            )

            console.print(explanation)
            # explanation = await explain_version(
            #     pkg=self._pkg, target=self._target, **_vars
            # )
            # click.echo(explanation)
        else:

            target = await self._bring.create_target("local_folder", path="/tmp/markus")

            pkg: PkgTing = await self._bring.get_pkg(self.name, raise_exception=True)

            result = await target.apply(
                "install", pkg_name=pkg.name, pkg_index=pkg.bring_index.id
            )
            # result = await self._bring.process("install", pkg_name=self.name)
            # path = await self._pkg.create_version_folder(
            #     vars=_vars, target=self._target
            # )
            print(result)
