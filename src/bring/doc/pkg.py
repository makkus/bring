# -*- coding: utf-8 -*-
from typing import Any, Dict, Mapping, Optional

import arrow
from bring.pkg_index.pkg import PkgTing
from frkl.common.async_utils import wrap_async_task
from frkl.common.doc import Doc
from frkl.explain.explanations.doc import InfoExplanation


class PkgInfoDisplay(InfoExplanation):
    def __init__(
        self,
        data: PkgTing,
        update: bool = False,
        full_info: bool = False,
        display_full_args: bool = False,
    ):

        self._update: bool = update
        self._display_full: bool = full_info
        self._display_full_args: bool = display_full_args

        self._base_metadata: Optional[Mapping[str, Any]] = None

        super().__init__(
            data=data,
            name=data.pkg_id,
            short_help_key="slug",
            help_key="desc",
            only_slug=False,
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
    def display_full_args(self) -> bool:

        return self._display_full_args

    @display_full_args.setter
    def display_full_args(self, display_full_args: bool) -> None:

        self._display_full_args = display_full_args

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

        short_help = f"{self.slug} (from: {self.data.bring_index.name})"
        return short_help

    @property
    def desc(self) -> Optional[str]:

        desc = self.base_metadata.get("desc", None)
        return desc

    # @property
    # def info(self) -> Mapping[str, Any]:
    #
    #     if self._info is None:
    #         self._info = wrap_async_task(self.retrieve_info)
    #
    #     return self._info

    async def get_info(self) -> Doc:

        args: Dict[str, Any] = {"include_metadata": True}
        if self.update:
            args["retrieve_config"] = {"metadata_max_age": 0}

        info = await self.data.get_info(**args)

        metadata = info["metadata"]
        age = arrow.get(metadata["metadata_timestamp"])

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

        # aliases = metadata["aliases"]

        # arg_allowed_items: int = 10000

        # args_table = create_table_from_pkg_args(
        #     args=metadata["vars"],
        #     aliases=aliases,
        #     limit_allowed=arg_allowed_items,
        #     show_headers=False,
        #     minimal=not self._display_full_args,
        # )
        #
        # result["args"] = args_table

        # result["args"] = metadata["pkg_args"]
        # result["aliases"] = aliases
        # result["version_list"] = metadata["version_list"]

        doc = Doc(result, short_help_key=self._short_help_key, help_key=self._help_key)

        return doc
