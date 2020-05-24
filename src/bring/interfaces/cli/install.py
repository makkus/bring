# -*- coding: utf-8 -*-
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
            callback=self.install_info,
            chain=False,
            result_callback=None,
            add_help_option=False,
            arg_hive=bring.arg_hive,
            subcommand_metavar="PROCESSOR",
            **kwargs,
        )

    @click.pass_context
    async def install_info(ctx, self, **kwargs):

        if ctx.invoked_subcommand is not None:
            return

        help = self.get_help(ctx)
        click.echo(help)

    def format_commands(self, ctx, formatter):
        """Extra format methods for multi methods that adds all the commands
        after the options.
        """

        wrap_async_task(print_pkg_list_help, bring=self._bring, formatter=formatter)

    def get_group_options(self) -> Union[Arg, Dict]:

        # target = wrap_async_task(self.get_bring_target)
        # target_args = target.requires()

        default_args = {
            "explain": {
                "doc": "Don't perform installation, only explain steps.",
                "type": "boolean",
                "default": False,
                "required": False,
                "cli": {"is_flag": True},
            },
            "help": {
                "doc": "Show this message and exit.",
                "type": "boolean",
                "default": False,
                "required": False,
                "cli": {"is_flag": True},
            },
            "target": {
                "doc": "The target directory to install the files into.",
                "type": "string",
                "required": False,
            },
            "merge_strategy": {
                "doc": "Strategy on how to deal with existing files, options",
                "type": "merge_strategy",
                "required": False,
            },
        }

        return default_args

    async def _list_commands(self, ctx):

        return []

    async def _get_command(self, ctx, name):

        # explain = self._group_params.get("explain")
        load_details = not ctx.obj.get("list_install_commands", False)
        target = self._group_params_parsed.get("target", None)
        merge_strategy = self._group_params_parsed.get("merge_strategy")

        install_args = {}
        if merge_strategy:
            install_args["merge_strategy"] = merge_strategy
        if target:
            install_args["target"] = target

        if not load_details:
            return None

        pkg = await self._bring.get_pkg(name, raise_exception=True)
        processor = self._bring.create_processor("install_pkg")

        profile_defaults = await self._bring.get_defaults()
        index_defaults = await pkg.bring_index.get_index_defaults()
        processor.add_constants(_constants_name="bring profile", **profile_defaults)
        processor.add_constants(_constants_name="index defaults", **index_defaults)
        processor.add_constants(_constants_name="install args", **install_args)
        processor.add_constants(
            _constants_name="pkg", pkg_name=pkg.name, pkg_index=pkg.bring_index.id
        )

        @click.command()
        @click.pass_context
        async def command(ctx, **kwargs):

            result = await processor.process()
            print(result)

        args = await processor.get_user_input_args()
        command.params = args.to_cli_options()

        return command


class PkgBringInsCommand(Command):
    def __init__(
        self,
        name: str,
        pkg_assembly: PkgAssembly,
        bring: Bring,
        target: str,
        merge_strategy: str,
        explain: bool = False,
        load_details: bool = False,
        **kwargs,
    ):

        self._pkg_assembly: PkgAssembly = pkg_assembly
        self._bring = bring

        self._target = target
        self._merge_strategy = merge_strategy

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
        merge_strategy: str,
        explain: bool = False,
        load_details: bool = False,
        **kwargs,
    ):

        self._bring: Bring = bring
        self._pkg: PkgTing = wrap_async_task(
            self._bring.get_pkg, name=name, raise_exception=True
        )

        self._target = target
        self._merge_strategy = merge_strategy

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

            print(kwargs)
            target = await self._bring.create_target("local_folder", path="/tmp/markus")

            pkg: PkgTing = await self._bring.get_pkg(self.name, raise_exception=True)

            proc = target.create_processor("install")
            result = await target.apply(
                proc, pkg_name=pkg.name, pkg_index=pkg.bring_index.id
            )
            # result = await self._bring.process("install", pkg_name=self.name)
            # path = await self._pkg.create_version_folder(
            #     vars=_vars, target=self._target
            # )
            print(result)
