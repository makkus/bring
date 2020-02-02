# -*- coding: utf-8 -*-
from typing import List, Any, Dict, Union

from bring.pkg_resolvers import PkgResolver


class GithubRelease(PkgResolver):
    def get_supported_source_types(self) -> List[str]:

        return ["github-release"]

    async def get_versions(self, source_details: Union[str, Dict]) -> Dict[str, Any]:

        return {}
