# -*- coding: utf-8 -*-
import os
import sys
from typing import Dict, Mapping, Optional, Union

import asyncclick as click
from bring.bring import Bring
from bring.interfaces.cli.utils import print_pkg_list_help
from bring.pkg import PKG_INPUT_TYPE
from freckles.core.explanation import FreckletInputExplanation
from frkl.args.arg import Arg
from frkl.args.cli.click_commands import FrklBaseCommand
from frkl.common.async_utils import wrap_async_task
from frkl.common.cli.exceptions import handle_exc_async
from frkl.common.formats.auto import AutoInput
from frkl.common.strings import generate_valid_identifier
from frkl.events.app_events import ExceptionEvent, ResultEvent
from frkl.tasks.explain import TaskExplanation
from frkl.tasks.task import Task


INSTALL_HELP = """Install one or several packages.

Either provide the name of one of the available packages, or the path to a file containing a list of packages to install.

TODO: more documentation and links, also explain target and target config
"""


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
            subcommand_metavar="PACKAGE",
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

        install_args = {}
        if target:
            install_args["target"] = target
        if target_config:
            install_args["target_config"] = target_config

        if not load_details:
            return None

        input_type: Optional[PKG_INPUT_TYPE] = None
        pkg_data: Optional[str] = None

        if isinstance(name, str):
            try:
                if os.path.isfile(os.path.expanduser(name)):
                    # load file
                    full_path = os.path.abspath(os.path.expanduser(name))
                    ai = AutoInput(full_path)
                    content = await ai.get_content_async()

                    if isinstance(content, Mapping) and "source" in content.keys():
                        input_type = PKG_INPUT_TYPE.pkg_desc
                        pkg_data = content

                    # doing that here to not accidently use a file
                    _pkg = await self._bring.get_pkg(name)
                    if _pkg:
                        pkg_data = name
                        input_type = PKG_INPUT_TYPE.pkg_name

                else:
                    if input_type is None:
                        pkg_data = await self._bring.get_full_package_name(name)
                        if pkg_data is not None:
                            input_type = PKG_INPUT_TYPE.pkg_name

            except Exception:
                pass

        else:
            raise NotImplementedError()

        md = {"origin": "user input"}

        if input_type is None:

            install_args["data"] = content
            frecklet_config = {
                "id": generate_valid_identifier(full_path, sep="_"),
                "type": "install_assembly",
            }

            frecklet = await self._bring.freckles.create_frecklet(frecklet_config)
            await frecklet.add_input_set(_default_metadata=md, **install_args)
        else:

            # install file from index

            install_args["pkg"] = pkg_data

            frecklet_config = {"type": "install_pkg"}

            frecklet = await self._bring.freckles.create_frecklet(frecklet_config)
            await frecklet.add_input_set(_default_metadata=md, **install_args)

        args = frecklet.get_current_required_args()
        if args:
            args_renderer = args.create_arg_renderer(
                "cli", add_defaults=False, remove_required=True
            )
        else:
            args_renderer = None

        if explain:

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

                task: Task = await frecklet.get_value("task")
                await task.initialize_tasklets()

                exp = TaskExplanation(task, indent=2)
                self._bring.add_app_event(exp)

        else:

            @click.command()
            @click.pass_context
            @handle_exc_async
            async def command(ctx, **kwargs):

                # TODO: check whether there is any input?
                if args_renderer:
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

                try:
                    result = await frecklet.frecklecute()
                    merge_result = result.get_result_value("merge_result")

                    res = ResultEvent(merge_result)
                    self._bring.add_app_event(res)
                except Exception as e:

                    ee = ExceptionEvent(e)
                    self._bring.add_app_event(ee)
                    sys.exit(1)

        if args_renderer:
            command.params = args_renderer.rendered_arg
        else:
            command.params = []

        return command
