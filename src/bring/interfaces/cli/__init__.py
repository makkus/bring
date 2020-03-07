# -*- coding: utf-8 -*-
import sys
from typing import Iterable

import asyncclick as click
import uvloop
from blessings import Terminal
from bring.bring import Bring
from bring.defaults import BRING_TASKS_BASE_TOPIC
from bring.interfaces.cli.command_group import BringCommandGroup
from frtls import APP_DETAILS
from frtls.cli.exceptions import handle_exc_async
from frtls.cli.logging import logzero_option_async
from frtls.tasks.task_watcher import TaskWatchManager


APP_DETAILS.APP_NAME = "bring"


click.anyio_backend = "asyncio"

uvloop.install()

bring_obj: Bring = Bring("bring")
terminal = Terminal()


@click.command(name="bring", cls=BringCommandGroup, bring=bring_obj, terminal=terminal)
@click.option(
    "--task-output",
    multiple=True,
    required=False,
    type=str,
    help=f"output plugin(s) for running tasks. available: {', '.join(['simple', 'terminal'])}",
)
@logzero_option_async()
@click.pass_context
@handle_exc_async
async def cli_bring(ctx, task_output: Iterable[str]):

    ctx.obj = {}
    ctx.obj["bring"] = bring_obj
    watch_mgmt = TaskWatchManager(typistry=bring_obj.typistry)

    ctx.obj["watch_mgmt"] = watch_mgmt

    if not task_output:
        task_output = ["terminal"]
    for to in task_output:
        watch_mgmt.add_watcher(
            {"type": to, "base_topics": [BRING_TASKS_BASE_TOPIC], "terminal": terminal}
        )

    await bring_obj.init()

    if ctx.invoked_subcommand:
        return

    # print_formatted_text('Hello world')


def cli(*args, **kwargs):
    return cli_bring(*args, **kwargs)


if __name__ == "__main__":
    sys.exit(cli(_anyio_backend="asyncio"))  # pragma: no cover
