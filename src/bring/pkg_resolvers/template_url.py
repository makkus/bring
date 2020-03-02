# -*- coding: utf-8 -*-
import copy
import itertools
import os
from typing import Any, Iterable, List, Mapping, Optional, Union

from bring.context import BringContextTing
from bring.pkg_resolvers import SimplePkgResolver
from frtls.templating import replace_string


class TemplateUrlResolver(SimplePkgResolver):

    _plugin_name: str = "template_url"

    def __init__(self, config: Optional[Mapping[str, Any]] = None):
        super().__init__(config=config)

    def _name(self):

        return "template-url"

    def _supports(self) -> List[str]:

        return ["template-url"]

    async def _process_pkg_versions(
        self, source_details: Mapping[str, Any], bring_context: BringContextTing
    ) -> Mapping[str, Any]:

        vars = source_details["template_vars"]

        keys, values = zip(*vars.items())

        versions = [dict(zip(keys, v)) for v in itertools.product(*values)]

        for version in versions:
            url = replace_string(source_details["url"], copy.copy(version))
            target_file_name = os.path.basename(url)
            version["_meta"] = {"url": url}
            version["_mogrify"] = [
                {"type": "download", "url": url, "target_file_name": target_file_name}
            ]

        return {"versions": versions}

    def get_artefact_mogrify(
        self, source_details: Mapping[str, Any], version: Mapping[str, Any]
    ) -> Union[Mapping, Iterable]:

        url: str = version["_meta"].get("url")

        match = False
        for ext in [".zip", "tar.gz", "tar.bz2"]:
            if url.endswith(ext):
                match = True
                break

        if match:
            return {"type": "archive"}
        else:
            return {"type": "file"}

    def get_unique_source_id(
        self, source_details: Mapping[str, Any], bring_context: BringContextTing
    ) -> str:

        return source_details["url"]

    # def get_download_url(self, version: Dict[str, str], source_detail: Dict[str, Any]):
    #
    #     url_template = source_detail["url"]
    #
    #     url = replace_string(url_template, version)
    #
    #     return url
