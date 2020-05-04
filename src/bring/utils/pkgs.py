# -*- coding: utf-8 -*-
import logging
from typing import Any, Dict, Iterable, List, Mapping, Optional, Union

from anyio import create_task_group
from blessed import Terminal
from bring.pkg_index.pkg import PkgTing
from bring.utils import find_version, replace_var_aliases
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
            result[_pkg] = await _pkg.get_values(
                *value_names, raise_exception=True
            )  # type: ignore
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
            slug = p["info"].get("slug", "n/a")
        data[pkg_name] = slug

    if header:
        _header: Optional[List[str]] = ["pkg", "desc"]
    else:
        _header = None
    table_str = create_two_column_table(data, header=_header, terminal=terminal)

    return table_str


async def explain_version(pkg: PkgTing, target: Optional[str] = None, **vars) -> str:

    data = await explain_version_data(pkg=pkg, target=target, **vars)

    vars = {}
    aliases = data["vars"]["alias_replaced"]
    explained = data["vars"]["explained"]

    for k, v in explained.items():
        vars[k] = {"source": v["source"]}
        val = v["value"]
        if k in aliases.keys() and aliases[k] != val:
            vars[k]["alias"] = v["value"]
            vars[k]["value"] = aliases[k]
        else:
            vars[k]["value"] = v["value"]

    result = "vars:\n"
    for k, v in sorted(vars.items()):
        result = result + f"  {k}:\n"
        result = result + f"    value: {v['value']}\n"
        source = v["source"]
        if source == "pkg":
            origin = "pkg default"
        elif source == "index":
            origin = "index default"
        elif source == "user":
            origin = "user input"
        else:
            raise Exception(f"Invalid source name '{source}'. This is a bug.")
        result = result + f"    origin: {origin}\n"
        if "alias" in v.keys():
            result = result + f"    from alias: {v['alias']}\n"

    result = result + "\nsteps:\n"
    for step in data["steps"]:
        result = result + f"  - {step}\n"

    return result


async def explain_version_data(
    pkg: PkgTing, target: Optional[str] = None, **vars
) -> Mapping[str, Any]:

    result: Dict[str, Any] = {}

    metadata = await pkg.get_value("metadata")
    vars_replaced = replace_var_aliases(vars=vars, metadata=metadata)
    vars_explained = await pkg.explain_full_vars(**vars)

    result["vars"] = {
        "provided": vars,
        "alias_replaced": vars_replaced,
        "explained": vars_explained,
    }

    version = find_version(vars=vars, metadata=metadata, var_aliases_replaced=False)

    result["version"] = version

    steps = []
    tm = await pkg.create_version_folder_transmogrificator(vars=vars, target=target)
    for msg in tm.explain_steps():
        steps.append(msg)

    result["steps"] = steps

    return result
