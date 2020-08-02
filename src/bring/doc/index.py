# -*- coding: utf-8 -*-
import logging
from typing import Any, Dict, Mapping, MutableMapping, Optional, Union

import arrow
from bring.interfaces.cli import bring_code_theme
from bring.pkg_index.index import BringIndexTing
from frkl.common.async_utils import wrap_async_task
from frkl.common.cli.output_utils import create_dict_element
from frkl.common.doc import Doc
from frkl.explain.explanations.doc import InfoExplanation
from rich import box
from rich.syntax import Syntax
from rich.table import Table


log = logging.getLogger("bring")


class IndexExplanation(InfoExplanation):
    def __init__(
        self,
        data: BringIndexTing,
        name: Optional[str],
        update: bool = False,
        full_info: bool = False,
        display_packages: bool = True,
    ):

        super().__init__(
            data=data,
            name=name,
            short_help_key="slug",
            help_key="desc",
            only_slug=False,
        )
        self._update: bool = update
        self._display_packages: bool = display_packages

        self._base_metadata: Optional[Mapping[str, Any]] = None
        # self._info: Optional[Mapping[str, Any]] = None

    async def get_info(self) -> Doc:

        args: Dict[str, Any] = {"include_metadata": True}
        if self.update:
            args["retrieve_config"] = {"metadata_max_age": 0}

        info: MutableMapping[str, Any] = await self.data.get_values(  # type: ignore
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

            pkg_infos = wrap_async_task(self.data.get_all_pkg_values, "info")

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
                self.data.get_value, "info", _raise_exception=True
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
