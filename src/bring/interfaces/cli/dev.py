# -*- coding: utf-8 -*-
import logging

import asyncclick as click
from bring.bring import Bring
from frkl.tasks.task import Task


log = logging.getLogger("bring")


@click.group()
@click.pass_context
def dev(ctx):
    """Helper tasks for development.

    """

    pass


@dev.command()
@click.argument("pkg_name", nargs=1)
@click.pass_context
async def details(ctx, pkg_name):
    """Clear the bring cache dir in the relevant locaiont (e.g. '~/.cache/bring' on Linux)."""

    bring: Bring = ctx.obj["bring"]

    frecklet_config = {"type": "install_pkg"}

    frecklet = await bring.freckles.create_frecklet(frecklet_config)

    # args = await frecklet.add_input_set(
    #     pkg_name="fd", pkg_index="binaries", target="/tmp/theresa"
    # )

    # args = await frecklet.add_input_set()

    task: Task = await frecklet.get_value("task")

    import pp

    pp(task.__dict__)
    result = await task.run_async()
    import pp

    pp(result.explanation_data)
