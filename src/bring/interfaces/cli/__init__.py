# -*- coding: utf-8 -*-
import sys
from typing import Iterable

import asyncclick as click
import uvloop
from blessings import Terminal
from bring.bring import Bring
from bring.defaults import BRING_TASKS_BASE_TOPIC
from bring.interfaces.cli.command_group import BringCommandGroup
from frtls.cli.exceptions import handle_exc_async
from frtls.cli.logging import logzero_option_async
from frtls.tasks.task_watcher import TaskWatchManager


click.anyio_backend = "asyncio"

uvloop.install()

bring_obj: Bring = Bring("bring")

terminal = Terminal()
watch_mgmt = TaskWatchManager(typistry=bring_obj.typistry)


@click.command(name="bring", cls=BringCommandGroup, bring=bring_obj, terminal=terminal)
@click.option(
    "--task-output",
    multiple=True,
    required=False,
    type=str,
    help=f"output plugin(s) for running tasks. available: {', '.join(watch_mgmt.available_plugins)}",
)
@logzero_option_async()
@click.pass_context
@handle_exc_async
async def cli_func(ctx, task_output: Iterable[str]):

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


def cli(*args):

    return cli_func(*args)


if __name__ == "__main__":
    cli()

if getattr(sys, "frozen", False):
    cli(*sys.argv[1:])
