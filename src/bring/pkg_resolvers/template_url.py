# -*- coding: utf-8 -*-
import itertools
from typing import Any, Dict, List, Mapping, Optional

from bring.context import BringContextTing
from bring.pkg_resolvers import HttpDownloadPkgResolver
from frtls.templating import replace_string


class TemplateUrlResolver(HttpDownloadPkgResolver):

    _plugin_name: str = "template_url"

    def __init__(self, config: Optional[Mapping[str, Any]] = None):
        super().__init__(config=config)

    def _name(self):

        return "template-url"

    def _supports(self) -> List[str]:

        return ["template-url"]

    async def _process_pkg_versions(
        self, source_details: Dict, bring_context: BringContextTing
    ) -> Mapping[str, Any]:

        vars = source_details["vars"]

        keys, values = zip(*vars.items())

        versions = [dict(zip(keys, v)) for v in itertools.product(*values)]
        return {"versions": versions}

    def get_unique_source_id(
        self, source_details: Dict, bring_context: BringContextTing
    ) -> str:

        return source_details["url"]

    def get_download_url(self, version: Dict[str, str], source_detail: Dict[str, Any]):

        url_template = source_detail["url"]

        url = replace_string(url_template, version)

        return url
