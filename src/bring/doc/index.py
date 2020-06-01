# -*- coding: utf-8 -*-
import logging
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Union

import arrow
from bring.doc.args import create_table_from_pkg_args
from bring.interfaces.cli import bring_code_theme
from bring.pkg_index.index import BringIndexTing
from bring.pkg_index.pkg import PkgTing
from frtls.async_helpers import wrap_async_task
from frtls.doc.doc import Doc
from frtls.doc.explanation.info import InfoExplanation
from frtls.doc.utils import create_dict_element
from rich import box
from rich.console import Console, ConsoleOptions, RenderGroup, RenderResult
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table


log = logging.getLogger("bring")


class IndexExplanation(InfoExplanation):
    def __init__(
        self,
        name: str,
        index: BringIndexTing,
        update: bool = False,
        full_info: bool = False,
        display_packages: bool = True,
    ):

        super().__init__(
            name=name,
            info_data=index,
            short_help_key="slug",
            help_key="desc",
            full_info=full_info,
        )
        self._index: BringIndexTing = index
        self._update: bool = update
        self._display_packages: bool = display_packages

        self._base_metadata: Optional[Mapping[str, Any]] = None
        # self._info: Optional[Mapping[str, Any]] = None

    async def create_info(self) -> Doc:

        args: Dict[str, Any] = {"include_metadata": True}
        if self.update:
            args["retrieve_config"] = {"metadata_max_age": 0}

        info: MutableMapping[str, Any] = await self._index.get_values(
            resolve=True
        )  # type: ignore

        metadata_timestamp = info["metadata_timestamp"]
        t = arrow.get(metadata_timestamp)

        doc_dict = dict(info["info"])
        doc_dict["metadata_timestamp"] = t.humanize()
        if info["labels"]:
            doc_dict["labels"] = info["labels"]
        if info["tags"]:
            doc_dict["tags"] = info["tags"]

        doc_dict["uri"] = info["uri"]
        defaults = info["defaults"]
        if defaults:
            defaults_markdown: Union[str, Syntax] = create_dict_element(
                _theme=bring_code_theme, **defaults
            )
        else:
            defaults_markdown = "  -- no defaults --"
        doc_dict["defaults"] = defaults_markdown

        doc_dict["index_type"] = info["index_type"]
        config = info["index_type_config"]
        if not config:
            _config: Union[str, Syntax] = "  -- no config --"
        else:
            _config = create_dict_element(_theme=bring_code_theme, **config)
        doc_dict["config"] = _config

        if self.display_packages:

            pkg_infos = wrap_async_task(self._index.get_all_pkg_values, "info")

            table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2, 0, 0))
            table.add_column("Name", no_wrap=True, style="bold deep_sky_blue4")
            table.add_column("Description", no_wrap=False, style="italic")
            for pkg, vals in sorted(pkg_infos.items()):
                slug = vals["info"].get("slug", "n/a")
                table.add_row(pkg, slug)

            doc_dict["packages"] = table

        doc = Doc(
            doc_dict, short_help_key=self._short_help_key, help_key=self._help_key
        )

        return doc

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

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:

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
