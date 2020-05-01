# -*- coding: utf-8 -*-
import logging
from typing import List, Tuple

from anyio import create_task_group
from asyncclick import HelpFormatter
from asyncclick.utils import make_default_short_help
from bring.bring import Bring
from bring.config.bring_config import BringConfig
from bring.pkg_index import BringIndexTing
from frtls.async_helpers import wrap_async_task


log = logging.getLogger("bring")


class BringHelpFormatter(HelpFormatter):
    def __init__(self, **kwargs):

        # ignore width/max_width
        super().__init__(width=10, max_width=10)


async def create_config_list_for_help(
    bring_config: BringConfig
) -> List[Tuple[str, str]]:

    pass


async def print_config_list_for_help(bring_config: BringConfig, formatter):

    pass


async def create_index_list_for_help(bring: Bring) -> List[Tuple[str, str]]:

    indexes = await bring.indexes

    infos = {}

    async def add_index(_index_name: str, _index: BringIndexTing):

        info = await _index.get_info()
        infos[_index_name] = info

    async with create_task_group() as tg:
        for index_name, index in indexes.items():
            await tg.spawn(add_index, index_name, index)

    result = []
    for ctx_name in sorted(infos.keys()):
        info = infos[ctx_name]
        short_help = info.get("slug", "n/a")
        if short_help.endswith("."):
            short_help = short_help[0:-1]
        result.append((ctx_name, short_help))

    return result


async def print_index_list_for_help(bring: Bring, formatter):

    index_list = await create_index_list_for_help(bring=bring)

    if len(index_list):
        limit = formatter.width - 6 - max(len(cmd[0]) for cmd in index_list)

        rows = []
        for subcommand, help in index_list:
            _help = make_default_short_help(help, max_length=limit)
            rows.append((subcommand, _help))

        if rows:
            with formatter.section("Indexes"):
                formatter.write_dl(rows)


async def create_pkg_list_for_help(
    bring: Bring, indicate_optional_index: bool = True
) -> List[Tuple[str, str]]:
    """Extra format methods for multi methods that adds all the commands
    after the options.
    """

    default_index_name = wrap_async_task(bring.config.get_default_index_name)

    pkgs = await bring.get_pkg_property_map("info", "index_name")

    short_help_map = []

    for pkg_name in sorted(pkgs.keys()):
        details = pkgs[pkg_name]
        info = details["info"]
        index_name = details["index_name"]
        short_help = info.get("slug", "n/a")
        if short_help.endswith("."):
            short_help = short_help[0:-1]

        if index_name == default_index_name:
            tokens = pkg_name.split(".")
            # _name = tokens[1]
            _name = f"[{tokens[0]}.]{tokens[1]}"
        else:
            _name = pkg_name

        short_help_map.append((_name, short_help))

    return short_help_map


async def print_pkg_list_help(bring: Bring, formatter) -> None:

    short_help_map = await create_pkg_list_for_help(bring=bring)
    # allow for 3 times the default spacing
    if len(short_help_map):
        limit = formatter.width - 6 - max(len(cmd[0]) for cmd in short_help_map)

        rows = []
        for subcommand, help in short_help_map:
            _help = make_default_short_help(help, max_length=limit)
            rows.append((subcommand, _help))

        if rows:
            with formatter.section("Packages"):
                formatter.write_dl(rows)
