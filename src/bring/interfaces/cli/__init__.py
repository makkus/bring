# -*- coding: utf-8 -*-

import sys
from typing import Any, Iterable, List, Mapping, Union

import asyncclick as click
from blessed import Terminal
from bring.bring import Bring
from bring.defaults import BRINGISTRY_CONFIG, BRING_TASKS_BASE_TOPIC
from bring.interfaces.cli.command_group import BringCommandGroup
from frtls.cli.exceptions import handle_exc_async
from frtls.cli.logging import logzero_option_async
from frtls.tasks.task_watcher import TaskWatchManager
from frtls.types.utils import load_modules
from tings.tingistry import Tingistries


try:
    import uvloop

    uvloop.install()
except Exception:
    pass

click.anyio_backend = "asyncio"


modules: Iterable[str] = BRINGISTRY_CONFIG["modules"]  # type: ignore
load_modules(*modules)

tingistry = Tingistries.create("bring")

bring_obj: Bring = tingistry.create_singleting("bring.mgmt", Bring)
terminal = Terminal()

CONTEXT_SETTINGS = dict(
    # default_map={},
    max_content_width=terminal.width,
    help_option_names=["-h", "--help"],
)


@click.command(
    name="bring",
    cls=BringCommandGroup,
    bring=bring_obj,
    terminal=terminal,
    context_settings=CONTEXT_SETTINGS,
)
@click.option(
    "--config", "-c", help="the config profile to use", type=str, default="default"
)
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
async def cli_bring(ctx, task_output: Iterable[str], config: str):

    if config != "default":
        bring_obj.set_config(config)

    ctx.obj = {}
    ctx.obj["bring"] = bring_obj
    if not task_output:
        task_output = ["terminal"]

    watchers: List[Union[str, Mapping[str, Any]]] = []
    for to in task_output:
        watchers.append(
            {"type": to, "base_topics": [BRING_TASKS_BASE_TOPIC], "terminal": terminal}
        )

    watch_mgmt = TaskWatchManager(typistry=bring_obj.typistry, watchers=watchers)

    ctx.obj["watch_mgmt"] = watch_mgmt

    # await bring_obj.init()

    if ctx.invoked_subcommand:
        return

    # print_formatted_text('Hello world')


def cli(*args, **kwargs):
    return cli_bring(*args, **kwargs)


if __name__ == "__main__":
    sys.exit(cli(_anyio_backend="asyncio"))  # pragma: no cover
