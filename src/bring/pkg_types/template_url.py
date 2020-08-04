# -*- coding: utf-8 -*-
import copy
import itertools
import os
from typing import Any, Dict, Iterable, List, Mapping, Union

from bring.pkg_types import PkgType, PkgVersion
from frkl.common.downloads.cache import calculate_cache_location_for_url
from frkl.common.jinja_templating import process_string_template


class TemplateUrlResolver(PkgType):
    """A package type to resolve packages whose artifacts are published with static urls that can be templated.

    All values of all template variables are combined with each of the other template variables to create a matrix of possible combinations.
    In some cases some of those combinations are not valid, and lead to a url that does not resolve to a file to download. At this time,
    there is nothing that can be done about it and the user will see an error message.

    Examples:
        - binaries.kubectl
        - binaries.mitmproxy
    """

    _plugin_name: str = "template_url"
    _plugin_supports: str = "template_url"

    def __init__(self, **config: Any):
        super().__init__(**config)

    def _name(self):

        return "template-url"

    # def _supports(self) -> List[str]:
    #
    #     return ["template-url"]

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
        self, source_details: Mapping[str, Any]
    ) -> Mapping[str, Any]:

        vars = source_details["template_vars"]

        keys, values = zip(*vars.items())

        versions = [dict(zip(keys, v)) for v in itertools.product(*values)]

        _version_list: List[PkgVersion] = []
        for version in versions:
            url = process_string_template(source_details["url"], copy.copy(version))
            target_file_name = os.path.basename(url)

            _vd: Dict[str, Any] = {}
            _vd["vars"] = version
            _vd["metadata"] = {"url": url}
            _vd["steps"] = [
                {"type": "download", "url": url, "target_file_name": target_file_name}
            ]
            _version_list.append(PkgVersion(**_vd))

        return {"versions": _version_list}

    def get_artefact_mogrify(
        self, source_details: Mapping[str, Any], version: PkgVersion
    ) -> Union[Mapping, Iterable]:

        url: str = version.metadata.get("url")  # type: ignore

        match = False
        for ext in [".zip", "tar.gz", "tar.bz2"]:
            if url.endswith(ext):
                match = True
                break

        if match:
            return {"type": "extract"}
        else:
            return {"type": "file"}

    def _get_unique_source_type_id(self, source_details: Mapping[str, Any]) -> str:

        id = calculate_cache_location_for_url(source_details["url"], sep="_")
        return id

    # def get_download_url(self, version: Dict[str, str], source_detail: Dict[str, Any]):
    #
    #     url_template = source_detail["url"]
    #
    #     url = replace_string(url_template, version)
    #
    #     return url
