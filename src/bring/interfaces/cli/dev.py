# -*- coding: utf-8 -*-
import logging

import asyncclick as click
from bring.bring import Bring
from bring.context import BringContextTing
from bring.utils.contexts import ensure_context


log = logging.getLogger("bring")


@click.group()
@click.pass_context
def dev(ctx):
    """Helper tasks for development.

    """

    pass


@dev.command()
@click.argument("pkg_name", nargs=1)
@click.option("--context", "-c", help="the context of the package", required=False)
@click.pass_context
async def details(ctx, pkg_name, context):
    """Clear the bring cache dir in the relevant locaiont (e.g. '~/.cache/bring' on Linux)."""

    bring: Bring = ctx.obj["bring"]

    _ctx_name = await ensure_context(bring, name=context)
    bring_context: BringContextTing = bring.get_context(_ctx_name)

    pkg = await bring_context.get_pkg(pkg_name)
    vals = await pkg.get_values("metadata")

    import pp  # type: ignore

    pp(vals)
