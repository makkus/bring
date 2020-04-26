# -*- coding: utf-8 -*-

import sys

import asyncclick as click
from bring.interfaces.cli.command_group import BringCommandGroup


try:
    import uvloop

    uvloop.install()
except Exception:
    pass

click.anyio_backend = "asyncio"


cli = BringCommandGroup()


# @click.command(
#     name="bring",
#     cls=BringCommandGroup,
#     bring=bring_obj,
#     terminal=terminal,
#     context_settings=CONTEXT_SETTINGS,
# )
# @click.option(
#     "--config", "-c", help="the config profile to use", type=str, default="default"
# )
# @click.option(
#     "--task-log",
#     multiple=True,
#     required=False,
#     type=str,
#     help=f"whether (and how) to log running tasks. available: {', '.join(['simple', 'tree'])}",
# )
# @logzero_option_async()
# @click.pass_context
# @handle_exc_async
# async def cli_bring(ctx, task_log: Iterable[str], config: str):
#
#     if config != "default":
#         bring_obj.set_config(config)
#
#     ctx.obj = {}
#     ctx.obj["bring"] = bring_obj
#     if not task_log:
#         bring_config: Mapping[str, Any] = await bring_obj.get_config_dict()
#         task_log = bring_config.get("task_log", [])
#
#         if isinstance(task_log, str):
#             task_log = [task_log]
#
#     watchers: List[Union[str, Mapping[str, Any]]] = []
#     for to in task_log:
#         watchers.append(
#             {"type": to, "base_topics": [BRING_TASKS_BASE_TOPIC], "terminal": terminal}
#         )
#
#     watch_mgmt = TaskWatchManager(typistry=bring_obj.typistry, watchers=watchers)
#
#     ctx.obj["watch_mgmt"] = watch_mgmt
#
#     # await bring_obj.init()
#
#     if ctx.invoked_subcommand:
#         return

# print_formatted_text('Hello world')


# def cli(*args, **kwargs):
#     return cli_bring(*args, **kwargs)


if __name__ == "__main__":
    sys.exit(cli(_anyio_backend="asyncio"))  # pragma: no cover
