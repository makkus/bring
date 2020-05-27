# -*- coding: utf-8 -*-
import logging
from typing import Any, Dict, Iterable, List, Mapping, Optional, Union

from anyio import create_task_group
from bring.pkg_index.pkg import PkgTing
from colorama import Fore, Style
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
    pkgs: Iterable[PkgTing], header: bool = False
) -> str:

    pkg_vals: Mapping[
        PkgTing, Mapping[str, Any]
    ] = await get_values_for_pkgs(  # type: ignore
        pkgs, "info"
    )  # type: ignore
    table = create_info_table_string(info_dicts=pkg_vals, header=header)
    return table


def create_info_table_string(
    info_dicts: Mapping[PkgTing, Mapping[str, Any]], header: bool = False
):

    data = SortedDict()
    for pkg in sorted(info_dicts.keys()):
        pkg_name = pkg.name
        p = info_dicts[pkg]
        if isinstance(p, TingTaskException):
            slug = f"{Fore.RED}{p}{Style.RESET_ALL}"
        else:
            slug = p["info"].get("slug", "n/a")
        data[pkg_name] = slug

    if header:
        _header: Optional[List[str]] = ["pkg", "desc"]
    else:
        _header = None
    table_str = create_two_column_table(data, header=_header)

    return table_str


# class PkgVersionExplanation(object):
#     def __init__(
#         self,
#         pkg: PkgTing,
#         target: Optional[str] = None,
#         extra_mogrifiers: Optional[Iterable[Union[str, Mapping[str, Any]]]] = None,
#         _box_style: Optional[Box] = None,
#         **vars: Any,
#     ):
#
#         self._pkg: PkgTing = pkg
#         self._target: Optional[str] = target
#         self._vars: Mapping[str, Any] = vars
#         self._extra_mogrifiers: Optional[
#             Iterable[Union[str, Mapping[str, Any]]]
#         ] = extra_mogrifiers
#
#         if _box_style is None:
#             _box_style = box.ROUNDED
#
#         self._box_style: Box = _box_style
#
#         self._data: Optional[Mapping[str, Any]] = None
#
#     async def get_explain_data(self):
#
#         if self._data is None:
#             self._data = await explain_version_data(
#                 pkg=self._pkg,
#                 # target=self._target,
#                 extra_mogrifiers=self._extra_mogrifiers,
#                 **self._vars,
#             )
#         return self._data
#
#     async def get_explained_vars(self):
#
#         data = await self.get_explain_data()
#
#         vars = {}
#         aliases = data["vars"]["alias_replaced"]
#         explained = data["vars"]["explained"]
#
#         for k, v in explained.items():
#             vars[k] = {"source": v["source"]}
#             val = v["value"]
#             if k in aliases.keys() and aliases[k] != val:
#                 vars[k]["alias"] = v["value"]
#                 vars[k]["value"] = aliases[k]
#             else:
#                 vars[k]["value"] = v["value"]
#
#         return vars
#
#     def __console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
#
#         vars = wrap_async_task(self.get_explained_vars)
#         vars_str = "[title]Variables[/title]\n\n"
#
#         for k, v in sorted(vars.items()):
#             vars_str += f"  [key]{k}[/key]\n"
#
#             vars_str += (
#                 f"    [key2]value[/key2]: [bold green]{v['value']}[/bold green]\n"
#             )
#
#             source = v["source"]
#             if source == "pkg":
#                 origin = "[deep_sky_blue4]pkg default[/deep_sky_blue4]"
#             elif source == "index":
#                 origin = "[dark_red]index default[/dark_red]"
#             elif source == "user":
#                 origin = "[dark_orange]user input[/dark_orange]"
#             vars_str += f"    [key2]origin[/key2]: {origin}\n"
#
#             if "alias" in v.keys():
#                 vars_str += f"    [key2]from alias[/key2]: {v['alias']}\n"
#
#         yield Panel(vars_str, box=self._box_style)
#
#         tasks_str = "[title]Tasks[/title]\n\n"
#         for task in self._data["steps"]:  # type: ignore
#
#             tasks_str += f"  ⮞ {task}\n"
#
#         yield Panel(tasks_str, box=self._box_style)
#
#
# async def explain_version_data(
#     pkg: PkgTing,
#     # target: Optional[str] = None,
#     extra_mogrifiers: Optional[Iterable[Union[str, Mapping[str, Any]]]] = None,
#     **vars,
# ) -> Mapping[str, Any]:
#
#     result: Dict[str, Any] = {}
#
#     metadata = await pkg.get_value("metadata")
#     vars_replaced = replace_var_aliases(vars=vars, metadata=metadata)
#     vars_explained = await pkg.explain_full_vars(**vars)
#
#     result["vars"] = {
#         "provided": vars,
#         "alias_replaced": vars_replaced,
#         "explained": vars_explained,
#     }
#
#     version = find_version(vars=vars, metadata=metadata, var_aliases_replaced=False)
#
#     result["version"] = version
#
#     steps = []
#     tm = await pkg.create_transmogrificator(
#         vars=vars, extra_mogrifiers=extra_mogrifiers
#     )
#     for msg in tm.explain_steps():
#         steps.append(msg)
#
#     result["steps"] = steps
#
#     return result
