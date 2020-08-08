# -*- coding: utf-8 -*-
from typing import Any, Iterable, Mapping, Optional

from bring.doc.args import create_table_from_pkg_args
from bring.pkg_types import PkgMetadata
from frkl.common.doc import Doc
from frkl.explain.explanation import Explanation
from frkl.explain.explanations.utils import doc_to_table_rows
from rich import box
from rich.console import Console, ConsoleOptions, RenderResult
from rich.table import Table


class PkgExplanation(Explanation):
    def __init__(
        self,
        pkg_name: str,
        pkg_metadata: PkgMetadata,
        info: Optional[Mapping[str, Any]] = None,
        tags: Optional[Iterable[str]] = None,
        labels: Optional[Mapping[str, Any]] = None,
        **config,
    ):

        self._pkg_name: str = pkg_name
        self._pkg_metadata: PkgMetadata = pkg_metadata
        self._info: Doc = Doc(info, short_help_key="slug", help_key="desc")
        self._limit_args: int = 1000000
        if tags is None:
            tags = []
        self._tags: Iterable[str] = tags
        if labels is None:
            labels = {}
        self._labels: Mapping[str, Any] = labels

        super().__init__(**config)

    async def create_explanation_data(self) -> Mapping[str, Any]:

        return {
            "metadata": self._pkg_metadata.to_dict(),
            "info": self._info.exploded_dict(),
            "tags": self._tags,
            "labels": self._labels,
        }

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:

        if self.config_value("show_title", True):
            short_help = self._info.get_short_help(default=None)
            if short_help:
                short_help = f" [value]({short_help})[/value]"
            else:
                short_help = ""
            yield f" [title]Package [underline]{self._pkg_name}[/underline][/title]{short_help}"

        metadata_rows = doc_to_table_rows(self._info)
        if metadata_rows:
            table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2, 0, 0))
            table.add_column("Property", style="key2", no_wrap=True)
            table.add_column("Value", style="value")

            for row in metadata_rows:
                table.add_row("", "")
                table.add_row(*row)

            yield table

        yield ""
        yield " [title]Variables[/title]"

        args_table = create_table_from_pkg_args(
            args=self._pkg_metadata.vars["args"],
            aliases=self._pkg_metadata.aliases,
            show_headers=False,
            limit_allowed=self._limit_args,
        )
        yield args_table

        # if self.config_value("show_versions", True):


# class PkgInfoDisplay(InfoExplanation):
#     def __init__(
#         self,
#         data: PkgTing,
#         update: bool = False,
#         full_info: bool = False,
#         display_full_args: bool = False,
#     ):
#
#         self._update: bool = update
#         self._display_full: bool = full_info
#         self._display_full_args: bool = display_full_args
#
#         self._base_metadata: Optional[Mapping[str, Any]] = None
#
#         super().__init__(
#             data=data,
#             name=data.pkg_id,
#             short_help_key="slug",
#             help_key="desc",
#             only_slug=False,
#         )
#
#     @property
#     def update(self) -> bool:
#
#         return self._update
#
#     @update.setter
#     def update(self, update: bool) -> None:
#
#         self._update = update
#
#     @property
#     def display_full(self) -> bool:
#
#         return self._display_full
#
#     @display_full.setter
#     def display_full(self, display_full: bool) -> None:
#
#         self._display_full = display_full
#
#     @property
#     def display_full_args(self) -> bool:
#
#         return self._display_full_args
#
#     @display_full_args.setter
#     def display_full_args(self, display_full_args: bool) -> None:
#
#         self._display_full_args = display_full_args
#
#     @property
#     def base_metadata(self) -> Mapping[str, Any]:
#
#         if self._base_metadata is None:
#             self._base_metadata = wrap_async_task(
#                 self.data.get_value, "info", _raise_exception=True
#             )
#         return self._base_metadata
#
#     @property
#     def slug(self) -> str:
#
#         slug = self.base_metadata.get("slug", "n/a")
#         if slug.endswith("."):
#             slug = slug[0:-1]
#         return slug
#
#     @property
#     def short_help(self) -> str:
#
#         short_help = f"{self.slug} (from: {self.data.bring_index.name})"
#         return short_help
#
#     @property
#     def desc(self) -> Optional[str]:
#
#         desc = self.base_metadata.get("desc", None)
#         return desc
#
#     # @property
#     # def info(self) -> Mapping[str, Any]:
#     #
#     #     if self._info is None:
#     #         self._info = wrap_async_task(self.retrieve_info)
#     #
#     #     return self._info
#
#     async def get_info(self) -> Doc:
#
#         args: Dict[str, Any] = {"include_metadata": True}
#         if self.update:
#             args["retrieve_config"] = {"metadata_max_age": 0}
#
#         info = await self.data.get_info(**args)
#
#         metadata = info["metadata"]
#         age = arrow.get(metadata["metadata_timestamp"])
#
#         source = info["source"]
#
#         result = dict(info["info"])
#         result = {}
#         result["slug"] = info["info"].get("slug", "-- description --")
#         desc = info["info"].get("desc", None)
#         if desc:
#             result["desc"] = desc
#         result["pkg_type"] = source["type"]
#         # result["info"] = info["info"]
#         if info["labels"]:
#             result["labels"] = info["labels"]
#         if info["tags"]:
#             result["tags"] = info["tags"]
#         result["metadata_timestamp"] = age.humanize()
#
#         # aliases = metadata["aliases"]
#
#         # arg_allowed_items: int = 10000
#
#         # args_table = create_table_from_pkg_args(
#         #     args=metadata["vars"],
#         #     aliases=aliases,
#         #     limit_allowed=arg_allowed_items,
#         #     show_headers=False,
#         #     minimal=not self._display_full_args,
#         # )
#         #
#         # result["args"] = args_table
#
#         # result["args"] = metadata["pkg_args"]
#         # result["aliases"] = aliases
#         # result["version_list"] = metadata["version_list"]
#
#         doc = Doc(result, short_help_key=self._short_help_key, help_key=self._help_key)
#
#         return doc
