# -*- coding: utf-8 -*-
import logging
from typing import Any, Dict, List, Mapping, MutableMapping, Optional

import arrow
from bring.display.args import create_table_from_pkg_args
from bring.interfaces.cli import bring_code_theme, bring_style
from bring.pkg_index import BringIndexTing, PkgTing
from frtls.async_helpers import wrap_async_task
from frtls.doc import Doc
from frtls.formats.output_formats import serialize
from rich import box
from rich.console import Console, ConsoleOptions, RenderGroup, RenderResult
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table


log = logging.getLogger("bring")


class IndexInfoDisplay(object):
    def __init__(
        self,
        index: BringIndexTing,
        update: bool = False,
        display_full: bool = False,
        display_config: bool = False,
        display_packages: bool = False,
    ):

        self._index: BringIndexTing = index
        self._update: bool = update
        self._display_full: bool = display_full
        self._display_config: bool = display_config
        self._display_packages: bool = display_packages

        self._base_metadata: Optional[Mapping[str, Any]] = None
        self._info: Optional[Mapping[str, Any]] = None

    @property
    def update(self) -> bool:
        return self._update

    @update.setter
    def update(self, update: bool) -> None:
        self._update = update

    @property
    def display_full(self) -> bool:
        return self._display_full

    @display_full.setter
    def display_full(self, display_full: bool):
        self._display_full = display_full

    @property
    def display_config(self) -> bool:
        return self._display_config

    @display_config.setter
    def display_config(self, display_config: bool) -> None:
        self._display_config = display_config

    @property
    def display_packages(self) -> bool:
        return self._display_packages

    @display_packages.setter
    def display_packages(self, display_packages: bool) -> None:
        self._display_packages = display_packages

    @property
    def base_metadata(self) -> Mapping[str, Any]:

        if self._base_metadata is None:
            self._base_metadata = wrap_async_task(
                self._index.get_value, "info", _raise_exception=True
            )
        return self._base_metadata

    @property
    def slug(self) -> str:

        slug = self.base_metadata.get("slug", "n/a")
        if slug.endswith("."):
            slug = slug[0:-1]
        return slug

    @property
    def short_help(self) -> str:

        short_help = self.slug
        return short_help

    @property
    def desc(self) -> Optional[str]:

        desc = self.base_metadata.get("desc", None)
        return desc

    @property
    def info(self) -> Mapping[str, Any]:

        if self._info is None:
            self._info = wrap_async_task(self.retrieve_info)

        return self._info

    async def retrieve_info(self) -> Mapping[str, Any]:

        args: Dict[str, Any] = {"include_metadata": True}
        if self.update:
            args["retrieve_config"] = {"metadata_max_age": 0}

        info: MutableMapping[str, Any] = await self._index.get_values(
            resolve=True
        )  # type: ignore

        # age = arrow.get(info["metadata_timestamp"])

        # info["metadata_age"] = age.humanize()

        return info

    def __console__(self, console: Console, options: ConsoleOptions) -> RenderResult:

        all: List[Any] = []

        info_data = wrap_async_task(self.retrieve_info)

        _info_data = info_data["info"]
        if info_data["labels"]:
            _info_data["labels"] = info_data["labels"]
        if info_data["tags"]:
            _info_data["tags"] = info_data["tags"]

        # args = info_data["args"]
        # aliases = info_data["aliases"]
        # version_list = info_data["version_list"]

        display_title: bool = True
        display_metadata: bool = True
        display_config: bool = False
        display_packages: bool = False
        # display_args: bool = True
        # arg_allowed_items: int = 0
        # display_version_list: bool = False

        desc_section = Doc(_info_data, short_help_key="slug", help_key="desc")

        if self._display_config:
            display_config = True

        if self._display_packages:
            display_packages = True

        if self._display_full:
            display_title = True
            display_config = True
            display_packages = True
            display_metadata = True
            # display_args = True
            # arg_allowed_items = 10000
            # display_version_list = True

        if display_title:

            md_ts = arrow.get(info_data["metadata_timestamp"]).humanize()
            title = f"Index: '[bold dark_red]{self._index.name}[/bold dark_red]' (metadata snapshot: {md_ts})"

            all.append(title)
            all.append("")
            help_str = desc_section.get_help(use_short_help=True, default=None)
            if help_str:
                all.append(help_str)
                all.append("")

        if display_metadata:
            if desc_section.metadata:
                all.append(desc_section)
                all.append("")

        if display_config:
            config = info_data["config"]
            _config = {}
            for k, v in config.items():
                if k.startswith("_"):
                    continue
                _config[k] = v

            if _config:
                config = []
                config.append("[bold]Config[/bold]")
                config.append("")

                config_yaml_string = serialize(
                    _config, format="yaml", indent=4, strip=True
                )
                config_markdown_string = f"``` yaml\n{config_yaml_string}\n```"
                config_markdown = Markdown(
                    config_markdown_string,
                    style=bring_style,
                    code_theme=bring_code_theme,
                    justify="left",
                )
                config.append(config_markdown)
                config.append("")

                all.append(Panel(RenderGroup(*config)))

        if display_packages:

            pkg_infos = wrap_async_task(self._index.get_all_pkg_values, "info")

            title = "[bold]Packages[/bold]"

            table = Table(box=box.SIMPLE, show_header=False)
            table.add_column("Name", no_wrap=True, style="bold deep_sky_blue4")
            table.add_column("Description", no_wrap=False, style="italic")
            for pkg, vals in sorted(pkg_infos.items()):
                slug = vals["info"].get("slug", "n/a")
                table.add_row(pkg, slug)

            all.append(Panel(RenderGroup(title, table)))

        yield Panel(RenderGroup(*all), box=box.SIMPLE)


class PkgInfoDisplay(object):
    def __init__(
        self,
        pkg: PkgTing,
        update: bool = False,
        display_full: bool = False,
        display_args: bool = False,
    ):

        self._pkg: PkgTing = pkg
        self._update: bool = update
        self._display_full: bool = display_full
        self._display_args: bool = display_args

        self._base_metadata: Optional[Mapping[str, Any]] = None
        self._info: Optional[Mapping[str, Any]] = None

    @property
    def update(self) -> bool:

        return self._update

    @update.setter
    def update(self, update: bool) -> None:

        self._update = update

    @property
    def display_full(self) -> bool:

        return self._display_full

    @display_full.setter
    def display_full(self, display_full: bool) -> None:

        self._display_full = display_full

    @property
    def display_args(self) -> bool:

        return self._display_args

    @display_args.setter
    def display_args(self, display_args: bool) -> None:

        self._display_args = display_args

    @property
    def base_metadata(self) -> Mapping[str, Any]:

        if self._base_metadata is None:
            self._base_metadata = wrap_async_task(
                self._pkg.get_value, "info", _raise_exception=True
            )
        return self._base_metadata

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

    @property
    def info(self) -> Mapping[str, Any]:

        if self._info is None:
            self._info = wrap_async_task(self.retrieve_info)

        return self._info

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
        result["metadata_timestamp"] = str(age)
        result["metadata_age"] = age.humanize()
        result["args"] = metadata["pkg_args"]
        result["aliases"] = metadata["aliases"]
        result["version_list"] = metadata["version_list"]

        return result

    def __console__(self, console: Console, options: ConsoleOptions) -> RenderResult:

        all: List[Any] = []

        info_data = wrap_async_task(self.retrieve_info)

        _info_data = info_data["info"]
        _info_data["labels"] = info_data["labels"]
        _info_data["tags"] = info_data["tags"]

        args = info_data["args"]
        aliases = info_data["aliases"]
        # version_list = info_data["version_list"]

        display_title: bool = True
        display_metadata: bool = True
        display_args: bool = True
        arg_allowed_items: int = 0
        display_version_list: bool = False

        if self._display_args:
            display_title = False
            display_metadata = False
            arg_allowed_items = 10000
            display_version_list = False

        if self._display_full:
            display_title = True
            display_metadata = True
            display_args = True
            arg_allowed_items = 10000
            display_version_list = True

        if display_title:

            md_ts = arrow.get(info_data["metadata_timestamp"]).humanize()
            title = f"Package: '[bold dark_red]{self._pkg.bring_index.name}[/bold dark_red].[bold blue]{self._pkg.name}[/bold blue]' (metadata snapshot: {md_ts})"

            all.append(title)
            all.append("")

        if display_metadata:
            desc_section = Doc(_info_data, short_help_key="slug", help_key="desc")
            all.append(desc_section)
            all.append("")

        if display_args:
            if self._display_full or not self._display_args:
                title_str = "[title]Arguments[/title]"
                all.append(title_str)

            table = create_table_from_pkg_args(
                args=args, aliases=aliases, limit_allowed=arg_allowed_items
            )
            all.append(table)
            # all.append(Panel(RenderGroup(*arg_section), box=box.SIMPLE))

        if display_version_list:
            log.debug("version list display not implemented yet")
            # for version in version_list:
            #     print(version)

        yield Panel(RenderGroup(*all), box=box.SIMPLE)
