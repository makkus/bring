# -*- coding: utf-8 -*-
import copy
import itertools
import os
from typing import Any, Iterable, List, Mapping, Union

from bring.context import BringContextTing
from bring.pkg_types import SimplePkgType
from frtls.templating import process_string_template


class TemplateUrlResolver(SimplePkgType):

    _plugin_name: str = "template_url"

    def __init__(self, **config: Any):
        super().__init__(**config)

    def _name(self):

        return "template-url"

    def _supports(self) -> List[str]:

        return ["template-url"]

    def get_args(self) -> Mapping[str, Any]:

        return {
            "template_vars": {
                "type": "dict",
                "required": True,
                "doc": "A map with the possible template var names as keys, and all allowed values for each key as value.",
            },
            "url": {
                "type": "string",
                "required": True,
                "doc": "The templated url string, using '{{' and '}}' as template markers.",
            },
        }

    async def _process_pkg_versions(
        self, source_details: Mapping[str, Any], bring_context: BringContextTing
    ) -> Mapping[str, Any]:

        vars = source_details["template_vars"]

        keys, values = zip(*vars.items())

        versions = [dict(zip(keys, v)) for v in itertools.product(*values)]

        for version in versions:
            url = process_string_template(source_details["url"], copy.copy(version))
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
            return {"type": "extract"}
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
