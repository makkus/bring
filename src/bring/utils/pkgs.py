# -*- coding: utf-8 -*-
import logging
from typing import Any, Dict, Iterable, List, Mapping, Optional, Union

from anyio import create_task_group
from blessed import Terminal
from bring.pkg import PkgTing
from colorama import Fore, Style
from frtls.cli.terminal import create_terminal
from frtls.formats.output_formats import create_two_column_table
from sortedcontainers import SortedDict
from tings.exceptions import TingTaskException


log = logging.getLogger("bring")


async def get_values_for_pkgs(
    pkgs: Iterable[PkgTing], *value_names: str, skip_pkgs_with_error: bool = False
) -> Mapping[PkgTing, Union[Mapping[str, Any], TingTaskException]]:

    result: Dict[PkgTing, Union[Mapping[str, Any], TingTaskException]] = {}

    async def get_values(_pkg: PkgTing):
        try:
            result[_pkg] = await _pkg.get_values(*value_names, raise_exception=True)
        except TingTaskException as e:
            log.debug(
                f"Can't retrieve values for pkg '{_pkg.name}': {e}", exc_info=True
            )
            if not skip_pkgs_with_error:
                result[_pkg] = e

    async with create_task_group() as tg:
        for pkg in pkgs:
            await tg.spawn(get_values, pkg)

    return result


async def create_pkg_info_table_string(
    pkgs: Iterable[PkgTing], header: bool = False, terminal: Optional[Terminal] = None
) -> str:

    if terminal is None:
        terminal = create_terminal()

    pkg_vals = await get_values_for_pkgs(pkgs, "info")
    data = SortedDict()
    for pkg in sorted(pkg_vals.keys()):
        pkg_name = pkg.name
        p = pkg_vals[pkg]
        if isinstance(p, TingTaskException):
            slug = f"{Fore.RED}{p}{Style.RESET_ALL}"
        else:
            slug = pkg_vals[pkg]["info"].get("slug", "n/a")
        data[pkg_name] = slug

    if header:
        _header: Optional[List[str]] = ["pkg", "desc"]
    else:
        _header = None
    table_str = create_two_column_table(data, header=_header, terminal=terminal)

    return table_str
