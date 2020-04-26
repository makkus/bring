# -*- coding: utf-8 -*-
import os
from typing import Any, Iterable, Mapping, MutableMapping, Optional

from bring.context import BringContextTing
from bring.pkg_resolvers import SimplePkgResolver
from pydriller import GitRepository


class Folder(SimplePkgResolver):

    _plugin_name: str = "folder"

    def __init__(self, config: Optional[Mapping[str, Any]] = None):

        super().__init__(config=config)

    def _name(self):

        return "folder"

    def _supports(self) -> Iterable[str]:
        return ["folder"]

    def get_unique_source_id(
        self, source_details: Mapping, bring_context: BringContextTing
    ) -> str:

        return source_details["path"]

    async def _process_pkg_versions(
        self, source_details: Mapping, bring_context: BringContextTing
    ) -> Mapping[str, Any]:

        return {
            "versions": [
                {
                    "_mogrify": [
                        {
                            "type": "folder",
                            "folder_path": os.path.abspath(source_details["path"]),
                        }
                    ]
                }
            ]
        }

    async def _update_commits(
        self,
        git_repo: GitRepository,
        current_commits: MutableMapping,
        checkout_point: str,
    ) -> None:

        for c in git_repo.get_list_commits(branch=checkout_point):
            if c.hash not in current_commits.keys():
                current_commits[c.hash] = c
