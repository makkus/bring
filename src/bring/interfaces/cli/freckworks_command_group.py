# -*- coding: utf-8 -*-
import os
from typing import Any, List, Mapping, Optional, Union

import asyncclick as click
from asyncclick import Option
from bring.defaults import BRING_TASKS_BASE_TOPIC
from bring.interfaces.cli import bring_obj
from freckworks.core.config import (
    FolderFreckworksProjectConfig,
    FreckworksProjectConfig,
)
from freckworks.core.freckworks import FreckworksProject
from freckworks.defaults import FRECKWORKS_BASE_TOPIC, FRECKWORKS_PRELOAD_MODULES
from freckworks.interfaces.cli.project import FreckworksProjectCommandGroup
from frtls.cli.exceptions import handle_exc_async
from frtls.cli.group import FrklBaseCommand
from frtls.cli.logging import logzero_option_obj_async
from frtls.cli.terminal import create_terminal
from frtls.tasks.task_watcher import TaskWatchManager
from frtls.types.utils import load_modules
from tings.tingistry import Tingistries


COMMAND_GROUP_HELP = """freckworks, devops little helper"""


class FreckworksCommandGroup(FrklBaseCommand):
    def __init__(self, name=None, **kwargs):

        load_modules(FRECKWORKS_PRELOAD_MODULES)
        terminal = create_terminal()

        tingistry = Tingistries.create("freckworks")
        tingistry.register_prototing(
            "freckworks.proto.project_config",
            FolderFreckworksProjectConfig,
            terminal=terminal,
        )

        self._project_config: FreckworksProjectConfig = tingistry.create_ting(
            "freckworks.proto.project_config", "freckworks.projects.default_project"
        )

        self._project: Optional[FreckworksProject] = None

        kwargs["help"] = COMMAND_GROUP_HELP
        logzero_option = logzero_option_obj_async()

        task_log_option = Option(
            param_decls=["--task-log"],
            multiple=True,
            required=False,
            type=str,
            help=f"running tasks output plugin(s), available: {', '.join(['tree', 'simple'])} ",
        )
        kwargs["params"] = [logzero_option, task_log_option]

        super(FreckworksCommandGroup, self).__init__(
            name=name,
            invoke_without_command=False,
            no_args_is_help=True,
            chain=False,
            result_callback=None,
            callback=self.command,
            # callback=None,
            # arg_hive=bring.arg_hive,
            **kwargs,
        )

    @click.pass_context
    @handle_exc_async
    async def command(ctx, self, task_log):

        if not task_log:
            task_log = ["tree"]

        watchers: List[Union[str, Mapping[str, Any]]] = []
        for to in task_log:
            watchers.append(
                {
                    "type": to,
                    "base_topics": [BRING_TASKS_BASE_TOPIC, FRECKWORKS_BASE_TOPIC],
                    "terminal": self._terminal,
                }
            )

        watch_mgmt = TaskWatchManager(typistry=bring_obj.typistry, watchers=watchers)

        ctx.obj["watch_mgmt"] = watch_mgmt

    async def get_project(self) -> FreckworksProject:

        if self._project is None:
            self._project = await self._project_config.get_value("project")

        return self._project

    async def _list_commands(self, ctx):

        result = ["project"]

        if "DEBUG" in os.environ.keys():
            result.append("dev")

        return result

    async def _get_command(self, ctx, name):

        command = None
        if name == "project":
            project = await self.get_project()
            command = FreckworksProjectCommandGroup(
                name="project", project=project, terminal=self._terminal
            )

        return command
