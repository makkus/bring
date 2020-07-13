# -*- coding: utf-8 -*-
import os
from typing import Dict, Union

import asyncclick as click
from bring.bring import Bring
from bring.interfaces.cli import console
from bring.interfaces.cli.utils import print_pkg_list_help
from frtls.args.arg import Arg
from frtls.async_helpers import wrap_async_task
from frtls.cli.exceptions import handle_exc_async
from frtls.cli.group import FrklBaseCommand
from frtls.types.utils import generate_valid_identifier


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
                "multiple": False,
            },
            "target_config": {
                "doc": "The target configuration.",
                "type": "dict",
                "required": False,
                "multiple": False,
            },
            "force": {
                "doc": "Overwrite potentially existing files.",
                "type": "boolean",
                "required": False,
                "cli": {"is_flag": True},
            },
            "update": {
                "doc": "Replace a potentially existing file that was installed by bring.",
                "type": "boolean",
                "required": False,
                "cli": {"is_flag": True},
            },
            # "merge_strategy": {
            #     "doc": "Strategy on how to deal with existing files, options",
            #     "type": "merge_strategy",
            #     "required": False,
            # },
        }

        return default_args

    async def _list_commands(self, ctx):

        return []

    async def _get_command(self, ctx, name):

        explain = self._group_params.get("explain")
        load_details = not ctx.obj.get("list_install_commands", False)
        target = self._group_params_parsed.get("target", None)
        target_config = self._group_params_parsed.get("target_config", None)

        # force = self._group_params_parsed.get("force", False)
        # update = self._group_params_parsed.get("update", False)

        # merge_strategy = self._group_params_parsed.get("merge_strategy")
        #
        # merge_strategy["config"]["force"] = force
        # merge_strategy["config"]["update"] = update

        install_args = {}
        if target:
            install_args["target"] = target
        if target_config:
            install_args["target_config"] = target_config

        # install_args["merge_strategy"] = merge_strategy
        # if target:
        #     install_args["target"] = {"target": target, "write_metadata": True}
        # else:
        #     install_args["target"] = {"target": None, "write_metadata": True}

        if not load_details:
            return None

        if not name.endswith(".br"):

            pkg = await self._bring.get_pkg(name, raise_exception=True)
            install_args["pkg_name"] = pkg.name
            install_args["pkg_index"] = pkg.bring_index.id

            frecklet_config = {"type": "install_pkg"}

            frecklet = await self._bring.freckles.create_frecklet(frecklet_config)
            frecklet.input_sets.add_constants(_id="install_params", **install_args)

        else:
            full_path = os.path.abspath(os.path.expanduser(name))

            install_args["path"] = full_path
            install_args["pkgs"] = [
                "binaries.fd",
                "binaries.${helm_name}",
                "binaries.k3d",
                "binaries.ytop",
            ]
            frecklet_config = {
                "id": generate_valid_identifier(full_path, sep="_"),
                "type": "install_assembly",
            }

            frecklet = await self._bring.freckles.create_frecklet(frecklet_config)
            frecklet.input_sets.add_constants(_id="install_param", **install_args)

        args = await frecklet.input_args

        args_user = {}
        for name, arg in args.childs.items():
            if name == "target":
                continue
            args_user[name] = arg

        record_args_user = self._arg_hive.create_record_arg(args_user)
        args_renderer = record_args_user.create_arg_renderer(
            "cli", add_defaults=False, remove_required=True
        )

        if explain:

            @click.command()
            @click.pass_context
            @handle_exc_async
            async def command(ctx, **kwargs):

                console.line()
                arg_value = args_renderer.create_arg_value(kwargs)
                frecklet.input_sets.add_input_values(
                    _id="cli_input", **arg_value.processed_input
                )

                explanation = frecklet.explain()
                console.print(explanation, overflow="ellipsis")

        else:

            @click.command()
            @click.pass_context
            @handle_exc_async
            async def command(ctx, **kwargs):

                arg_value = args_renderer.create_arg_value(kwargs)
                frecklet.input_sets.add_input_values(
                    _id="cli_input", **arg_value.processed_input
                )

                console.line()
                msg = await frecklet.get_msg()
                console.print(f"[title]Task[/title]: {msg}")
                console.line()
                console.print("[title]Variables[/title]")

                pi = frecklet.input_sets.explain()
                console.print(pi)

                result = await frecklet.get_frecklet_result()
                if isinstance(result.data, Exception):
                    console.print(f"[title]Error[/title]: {result.data}")
                else:
                    console.print("[title]Result[/title]")
                    console.line()
                    target = result.data["target"]
                    console.print(f"  - installed pkg into: [value]{target}[/value]")

        command.params = args_renderer.rendered_arg

        return command
