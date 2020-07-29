# -*- coding: utf-8 -*-
import os
import sys
from typing import Dict, Union

import asyncclick as click
from bring.bring import Bring
from bring.interfaces.cli import console
from bring.interfaces.cli.utils import print_pkg_list_help
from freckles.core.explanation import FreckletInputExplanation
from frkl.args.arg import Arg
from frkl.args.cli.click_commands import FrklBaseCommand
from frkl.common.async_utils import wrap_async_task
from frkl.common.cli.exceptions import handle_exc_async
from frkl.common.strings import generate_valid_identifier
from frkl.events.app_events import ExceptionEvent, ResultEvent
from frkl.tasks.explain import TaskExplanation
from frkl.tasks.task import Task


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

        md = {"origin": "user input"}
        if not name.endswith(".br"):

            pkg = await self._bring.get_pkg(name, raise_exception=True)
            install_args["pkg_name"] = pkg.name
            install_args["pkg_index"] = pkg.bring_index.id

            frecklet_config = {"type": "install_pkg"}

            frecklet = await self._bring.freckles.create_frecklet(frecklet_config)
            await frecklet.add_input_set(_default_metadata=md, **install_args)

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
            frecklet.add_input_set(_default_metadata=md, **install_args)

        args = frecklet.get_current_required_args()
        args_renderer = args.create_arg_renderer(
            "cli", add_defaults=False, remove_required=True
        )

        if explain:

            @click.command()
            @click.pass_context
            @handle_exc_async
            async def command(ctx, **kwargs):

                arg_value = args_renderer.create_arg_value(kwargs)

                await frecklet.add_input_set(**arg_value.processed_input)

                console.line()
                msg = frecklet.get_msg()
                self._bring.add_app_event(f"[title]Task[/title]: {msg}\n")

                # console.print("[title]Variables[/title]")

                expl = FreckletInputExplanation(
                    data=frecklet.current_frecklet_input_details
                )
                self._bring.add_app_event(expl)

                task: Task = await frecklet.get_value("task")
                await task.initialize_tasklets()
                # console.print("[title]Steps[/title]")
                # console.line()
                exp = TaskExplanation(task, indent=2)
                self._bring.add_app_event(exp)
                # console.print(exp)
                # console.line()

        else:

            @click.command()
            @click.pass_context
            @handle_exc_async
            async def command(ctx, **kwargs):

                arg_value = args_renderer.create_arg_value(kwargs)

                md = {"origin": "user input"}
                await frecklet.add_input_set(
                    _default_metadata=md, **arg_value.processed_input
                )

                msg = frecklet.get_msg()
                self._bring.add_app_event(f"[title]Task[/title]: {msg}\n")

                expl = FreckletInputExplanation(
                    data=frecklet.current_frecklet_input_details
                )
                self._bring.add_app_event(expl)
                # console.print(expl)

                try:
                    result = await frecklet.frecklecute()
                    re = ResultEvent(result)
                    self._bring.add_app_event(re)
                except Exception as e:
                    ee = ExceptionEvent(e)
                    self._bring.add_app_event(ee)
                    sys.exit(1)

        command.params = args_renderer.rendered_arg

        return command
