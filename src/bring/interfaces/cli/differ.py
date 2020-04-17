# -*- coding: utf-8 -*-
import asyncclick as click
from dictdiffer import diff
from frtls.formats.input_formats import SmartInput
from ruamel.yaml import YAML


@click.group()
@click.pass_context
def dev(ctx):
    """Helper tasks for development.

    """

    pass


@dev.command()
@click.argument("path", nargs=1)
# @click.option("--context", "-c", help="the context of the package", required=False)
@click.pass_context
async def differ(ctx, path):
    """Clear the bring cache dir in the relevant locaiont (e.g. '~/.cache/bring' on Linux)."""

    si = SmartInput(path)
    content = await si.content_async()

    yaml = YAML()
    dict_content_orig = list(yaml.load_all(content))

    print(dict_content_orig)
    new_content = click.edit(content)

    dict_content_new = list(yaml.load_all(new_content))

    dict_diff = diff(dict_content_orig, dict_content_new)
    dict_diff = list(dict_diff)
    print(dict_diff)

    # print(new_content)
    # bring: Bring = ctx.obj["bring"]
    #
    # _ctx_name = await ensure_context(bring, name=context)
    # bring_context: BringContextTing = bring.get_context(_ctx_name)
    #
    # pkg = await bring_context.get_pkg(pkg_name)
    # vals = await pkg.get_values("metadata")
    #
    # import pp  # type: ignore
    #
    # pp(vals)
