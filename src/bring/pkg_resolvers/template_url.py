# -*- coding: utf-8 -*-
import itertools
from typing import List, Dict, Any

from bring.pkg_resolvers import HttpDownloadPkgResolver
from frtls.templating import replace_string


class TemplateUrlResolver(HttpDownloadPkgResolver):
    def __init__(self):
        super().__init__()

    def _name(self):

        return "template-url"

    def _supports(self) -> List[str]:

        return ["template-url"]

    async def _retrieve_versions(
        self, source_details: Dict, update=True
    ) -> List[Dict[str, str]]:

        vars = source_details["vars"]

        keys, values = zip(*vars.items())

        versions = [dict(zip(keys, v)) for v in itertools.product(*values)]
        return versions

    def get_unique_source_id(self, source_details: Dict) -> str:

        return source_details["url"]

    def get_download_url(self, version: Dict[str, str], source_detail: Dict[str, Any]):

        url_template = source_detail["url"]

        url = replace_string(url_template, version)

        return url
