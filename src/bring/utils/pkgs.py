# -*- coding: utf-8 -*-
from typing import Any, Dict, Iterable, List, Mapping, Optional

from anyio import create_task_group
from blessed import Terminal
from bring.pkg import PkgTing
from frtls.formats.output_formats import create_two_column_table
from sortedcontainers import SortedDict


async def get_values_for_pkgs(
    pkgs: Iterable[PkgTing], *value_names: str
) -> Mapping[PkgTing, Mapping[str, Any]]:

    result: Dict[PkgTing, Mapping] = {}

    async def get_values(_pkg):

        result[_pkg] = await _pkg.get_values(*value_names)

    async with create_task_group() as tg:
        for pkg in pkgs:
            await tg.spawn(get_values, pkg)

    return result


async def create_pkg_info_table_string(
    pkgs: Iterable[PkgTing], header: bool = False, terminal: Optional[Terminal] = None
) -> str:

    if terminal is None:
        terminal = Terminal()

    pkg_vals = await get_values_for_pkgs(pkgs, "info")
    data = SortedDict()
    for pkg in sorted(pkg_vals.keys()):
        pkg_name = pkg.name
        slug = pkg_vals[pkg]["info"].get("slug", "n/a")
        data[pkg_name] = slug

    if header:
        _header: Optional[List[str]] = ["pkg", "desc"]
    else:
        _header = None
    table_str = create_two_column_table(data, header=_header, terminal=terminal)

    return table_str
