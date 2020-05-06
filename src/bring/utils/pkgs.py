# -*- coding: utf-8 -*-
import logging
from typing import Any, Dict, Iterable, List, Mapping, Optional, Union

import arrow
from anyio import create_task_group
from bring.pkg_index.pkg import PkgTing
from bring.utils import find_version, replace_var_aliases
from colorama import Fore, Style
from frtls.async_helpers import wrap_async_task
from frtls.doc import Doc
from frtls.formats.output_formats import create_two_column_table, serialize
from rich import box
from rich.box import Box
from rich.console import Console, ConsoleOptions, RenderGroup, RenderResult
from rich.panel import Panel
from rich.table import Table
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
    table_str = create_two_column_table(data, header=_header)

    return table_str


class PkgVersionExplanation(object):
    def __init__(
        self,
        pkg: PkgTing,
        target: Optional[str] = None,
        extra_mogrifiers: Optional[Iterable[Union[str, Mapping[str, Any]]]] = None,
        _box_style: Optional[Box] = None,
        **vars: Any,
    ):

        self._pkg: PkgTing = pkg
        self._target: Optional[str] = target
        self._vars: Mapping[str, Any] = vars
        self._extra_mogrifiers: Optional[
            Iterable[Union[str, Mapping[str, Any]]]
        ] = extra_mogrifiers

        if _box_style is None:
            _box_style = box.ROUNDED

        self._box_style: Box = _box_style

        self._data: Optional[Mapping[str, Any]] = None

    async def get_explain_data(self):

        if self._data is None:
            self._data = await explain_version_data(
                pkg=self._pkg,
                target=self._target,
                extra_mogrifiers=self._extra_mogrifiers,
                **self._vars,
            )
        return self._data

    async def get_explained_vars(self):

        data = await self.get_explain_data()

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

        return vars

    def __console__(self, console: Console, options: ConsoleOptions) -> RenderResult:

        vars = wrap_async_task(self.get_explained_vars)
        vars_str = "[title]Variables[/title]\n\n"

        for k, v in sorted(vars.items()):
            vars_str += f"  [key]{k}[/key]\n"

            vars_str += (
                f"    [key2]value[/key2]: [bold green]{v['value']}[/bold green]\n"
            )

            source = v["source"]
            if source == "pkg":
                origin = "[deep_sky_blue4]pkg default[/deep_sky_blue4]"
            elif source == "index":
                origin = "[dark_red]index default[/dark_red]"
            elif source == "user":
                origin = "[dark_orange]user input[/dark_orange]"
            vars_str += f"    [key2]origin[/key2]: {origin}\n"

            if "alias" in v.keys():
                vars_str += f"    [key2]from alias[/key2]: {v['alias']}\n"

        yield Panel(vars_str, box=self._box_style)

        tasks_str = "[title]Tasks[/title]\n\n"
        for task in self._data["steps"]:  # type: ignore

            tasks_str += f"  ⮞ {task}\n"

        yield Panel(tasks_str, box=self._box_style)


async def explain_version_data(
    pkg: PkgTing,
    target: Optional[str] = None,
    extra_mogrifiers: Optional[Iterable[Union[str, Mapping[str, Any]]]] = None,
    **vars,
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
    tm = await pkg.create_version_folder_transmogrificator(
        vars=vars, target=target, extra_mogrifiers=extra_mogrifiers
    )
    for msg in tm.explain_steps():
        steps.append(msg)

    result["steps"] = steps

    return result


class PkgInfoDisplay(object):
    def __init__(self, pkg: PkgTing, update: bool = False, only_args: bool = False):

        self._pkg: PkgTing = pkg
        self._update: bool = update
        self._only_args: bool = only_args

        self._info: Optional[Mapping[str, Any]] = None

    @property
    def update(self) -> bool:

        return self._update

    @update.setter
    def update(self, update: bool) -> None:

        self._update = update

    @property
    def display_only_args(self) -> bool:

        return self._only_args

    @display_only_args.setter
    def display_only_args(self, only_args: bool) -> None:

        self._only_args = only_args

    @property
    def base_metadata(self) -> Mapping[str, Any]:

        if self._info is None:
            self._info = wrap_async_task(
                self._pkg.get_value, "info", _raise_exception=True
            )
        return self._info

    @property
    def slug(self) -> str:

        slug = self.base_metadata.get("slug", "n/a")
        if slug.endswith("."):
            slug = slug[0:-1]
        return slug

    @property
    def short_help(self) -> str:

        short_help = f"{self.slug} (from: {self._pkg.bring_index.name})"
        return short_help

    @property
    def desc(self) -> Optional[str]:

        desc = self.base_metadata.get("desc", None)
        return desc

    async def retrieve_info(self) -> Mapping[str, Any]:

        args: Dict[str, Any] = {"include_metadata": True}
        if self.update:
            args["retrieve_config"] = {"metadata_max_age": 0}

        info = await self._pkg.get_info(**args)

        metadata = info["metadata"]
        age = arrow.get(metadata["timestamp"])

        result = {}
        result["info"] = info["info"]
        result["labels"] = info["labels"]
        result["tags"] = info["tags"]
        result["metadata snapshot"] = age.humanize()
        result["args"] = metadata["pkg_args"]
        result["aliases"] = metadata["aliases"]
        result["version list"] = metadata["version_list"]

        return result

    def __console__(self, console: Console, options: ConsoleOptions) -> RenderResult:

        base_info: List[Any] = []

        info = wrap_async_task(self.retrieve_info)

        if not self.display_only_args:

            package_str = f"[title]Package[/title]: [bold dark_red]{self._pkg.bring_index.name}[/bold dark_red].[bold blue]{self._pkg.name}[/bold blue] (metadata snapshot: {info['metadata snapshot']})"
            base_info.append(package_str)

            base_metadata_str = "\n" + serialize(info["info"], format="yaml", indent=2)
            base_info.append(base_metadata_str)
            if info["labels"]:
                base_info.append("[title]Labels[/title]")
                labels_str = "\n" + serialize(info["labels"], format="yaml", indent=2)
                base_info.append(labels_str)
            if info["tags"]:
                base_info.append("[title]Tags[/title]")
                labels_str = "\n" + serialize(info["tags"], format="yaml", indent=2)
                base_info.append(labels_str)

            base_info.append("[title]Arguments[/title]")
        else:
            title_str = f"[title]Arguments for[/title]: [bold dark_red]{self._pkg.bring_index.name}[/bold dark_red].[bold blue]{self._pkg.name}[/bold blue] (metadata snapshot: {info['metadata snapshot']})"
            base_info.append(title_str)

        table = Table(box=box.SIMPLE)
        table.add_column("Name", no_wrap=True, style="bold dark_orange")
        table.add_column("Description", no_wrap=False, style="italic")
        table.add_column("Type", no_wrap=True)
        table.add_column("Required", no_wrap=True)
        table.add_column("Default", no_wrap=True, style="green")
        table.add_column("Allowed", no_wrap=True)
        table.add_column("Alias", no_wrap=True)

        for k, v in sorted(info["args"].items()):

            aliases = info["aliases"].get(k, {})
            aliases_reverse: Dict[str, List[str]] = {}
            allowed_no_alias = []

            allowed = v["allowed"]
            if k != "version":
                allowed = sorted(allowed)
            for a in allowed:
                if a in aliases.keys():
                    aliases_reverse.setdefault(aliases[a], []).append(a)
                else:
                    allowed_no_alias.append(a)

            if v["default"] is not None:
                default = v["default"]
            else:
                default = ""

            if allowed_no_alias:
                allowed_first = allowed_no_alias[0]
            else:
                allowed_first = ""
            doc = Doc(v.get("doc", {}))
            if info.get("required", True):
                req = "yes"
            else:
                req = "no"

            if (
                allowed_first in aliases_reverse.keys()
                and aliases_reverse[allowed_first]
            ):
                alias = aliases_reverse[allowed_first][0]
            else:
                alias = ""

            table.add_row(
                k,
                doc.get_short_help(use_help=True),
                v["type"],
                req,
                default,
                allowed_first,
                alias,
            )
            if (
                allowed_first in aliases_reverse.keys()
                and len(aliases_reverse[allowed_first]) > 1
            ):
                for alias in aliases_reverse[allowed_first][1:]:
                    table.add_row("", "", "", "", "", "", alias)

            if len(allowed_no_alias) > 1:
                for item in allowed_no_alias[1:]:
                    if item in aliases_reverse.keys() and aliases_reverse[item]:
                        alias = aliases_reverse[item][0]
                    else:
                        alias = ""
                    table.add_row("", "", "", "", "", item, alias)

                    if (
                        item in aliases_reverse.keys()
                        and len(aliases_reverse[item]) > 1
                    ):
                        for alias in aliases_reverse[item][1:]:
                            table.add_row("", "", "", "", "", "", alias)

            table.add_row("", "", "", "", "", "", "")
        base_info.append(table)

        base_info_panel = Panel(RenderGroup(*base_info), box=box.SIMPLE)
        yield base_info_panel
