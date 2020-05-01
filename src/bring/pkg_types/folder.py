# -*- coding: utf-8 -*-
import os
from typing import Any, Iterable, Mapping, MutableMapping

from bring.pkg_index import BringIndexTing
from bring.pkg_types import SimplePkgType
from pydriller import GitRepository


class Folder(SimplePkgType):

    _plugin_name: str = "folder"

    def __init__(self, **config: Any):

        super().__init__(**config)

    def _name(self):

        return "folder"

    def get_args(self) -> Mapping[str, Any]:

        return {
            "path": {
                "type": "string",
                "required": True,
                "doc": "The path to the local folder that represents the package.",
            }
        }

    def _supports(self) -> Iterable[str]:
        return ["folder"]

    def get_unique_source_id(
        self, source_details: Mapping, bring_index: BringIndexTing
    ) -> str:

        return source_details["path"]

    async def _process_pkg_versions(
        self, source_details: Mapping, bring_index: BringIndexTing
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
