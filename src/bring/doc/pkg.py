# -*- coding: utf-8 -*-
from typing import Any, Dict, List, Mapping, Optional

import arrow
from bring.doc.args import create_table_from_pkg_args
from bring.doc.index import log
from bring.pkg_index.pkg import PkgTing
from frtls.async_helpers import wrap_async_task
from frtls.doc.doc import Doc
from frtls.doc.explanation.info import InfoExplanation
from rich import box
from rich.console import Console, ConsoleOptions, RenderGroup, RenderResult
from rich.panel import Panel


class PkgInfoDisplay(InfoExplanation):
    def __init__(
        self,
        pkg: PkgTing,
        update: bool = False,
        full_info: bool = False,
        display_args: bool = False,
    ):

        self._pkg: PkgTing = pkg
        self._update: bool = update
        self._display_full: bool = full_info
        self._display_args: bool = display_args

        self._base_metadata: Optional[Mapping[str, Any]] = None
        self._info: Optional[Mapping[str, Any]] = None

        super().__init__(
            name=pkg.pkg_id,
            info_data=pkg,
            short_help_key="slug",
            help_key="desc",
            full_info=full_info,
        )

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

    async def create_info(self) -> Doc:

        args: Dict[str, Any] = {"include_metadata": True}
        if self.update:
            args["retrieve_config"] = {"metadata_max_age": 0}

        info = await self._pkg.get_info(**args)

        metadata = info["metadata"]
        age = arrow.get(metadata["timestamp"])

        source = info["source"]

        result = dict(info["info"])
        result = {}
        result["slug"] = info["info"].get("slug", "-- description --")
        desc = info["info"].get("desc", None)
        if desc:
            result["desc"] = desc
        result["pkg_type"] = source["type"]
        # result["info"] = info["info"]
        if info["labels"]:
            result["labels"] = info["labels"]
        if info["tags"]:
            result["tags"] = info["tags"]
        result["metadata_timestamp"] = age.humanize()
        args = metadata["pkg_args"]
        aliases = metadata["aliases"]

        arg_allowed_items: int = 0
        if self._display_args:
            arg_allowed_items = 10000

        args_table = create_table_from_pkg_args(
            args=metadata["pkg_args"],
            aliases=aliases,
            limit_allowed=arg_allowed_items,
            show_headers=False,
        )
        result["args"] = args_table
        # result["args"] = metadata["pkg_args"]
        # result["aliases"] = aliases
        # result["version_list"] = metadata["version_list"]

        doc = Doc(result, short_help_key=self._short_help_key, help_key=self._help_key)

        return doc

    def __rich_console2__(
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
