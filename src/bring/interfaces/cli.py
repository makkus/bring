# -*- coding: utf-8 -*-
import click
from click import File, Path
from pathlib import Path as PPath
from click_aliases import ClickAliasedGroup

from bring.bring import BringTings
from frutils.cli.exceptions import handle_exc
from frutils.cli.logging import logzero_option
from frutils.formats import SmartInput
from frutils.templating import replace_strings_in_obj, get_global_jinja_env
from tings import create_tings
from tings.interfaces.cli import TingWatcher


@click.group(cls=ClickAliasedGroup)
@click.option("--base-path", "-p", help="A path where to look for '*.bring' files.", multiple=True, type=Path(exists=True, file_okay=True, dir_okay=True, readable=True, allow_dash=False))
@logzero_option()
@click.pass_context
def cli(ctx, base_path):

    if not base_path:
        base_paths = [PPath.cwd().as_posix()]
    else:
        base_paths = []
        for p in base_path:
          base_paths.append(PPath(p).as_posix())

    ctx.obj = {}
    ctx.obj["base_paths"] = base_paths

    bt = BringTings(base_paths=base_paths)
    ctx.obj["bring_tings"] = bt


@cli.command(name="list", aliases=["l", "li"])
@click.pass_context
@handle_exc
def list_packages(ctx):

    bt = ctx.obj["bring_tings"]
    import pp
    t = bt.get_index("alias")["bat"]
    # print(t._ting_get_requirement_values_for_property_("bring_data"))

    # print(t._ting_retrieve_property_values_("bring_data"))
    print(t.lookup_data)
    # for t in bt.bring_pkgs():
    #     print(t.alias)
    #     t.data
    #     print(t.bring_data)

        # print(t.bring_data)
        # pp(t.bring_data)

@cli.command(name="watch")
@click.option("--property", "-p", multiple=True)
@click.pass_context
def watch(ctx, property):

    bt = ctx.obj["bring_tings"]

    tw = TingWatcher(tings=bt, finder=bt.finder, index="id", properties=property)
    tw.watch()

@cli.command(name="install", aliases=["in"])
@click.pass_context
@handle_exc
def install(ctx):

    print("HH")



if __name__ == "__main__":
    cli()
