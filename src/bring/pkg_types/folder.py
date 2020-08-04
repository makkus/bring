# -*- coding: utf-8 -*-
import os
from typing import Any, Iterable, Mapping, MutableMapping

from bring.pkg_types import PkgType, PkgVersion
from pydriller import GitRepository


class Folder(PkgType):
    """A package type to represent a local folder.

    This is mostly used in local development, documentation still to be done...
    """

    _plugin_name: str = "folder"
    _plugin_supports: Iterable[str] = "folder"

    def __init__(self, **config: Any):

        super().__init__(**config)

    def _name(self):

        return "folder"

    def get_args(self) -> Mapping[str, Mapping[str, Any]]:

        return {
            "path": {
                "type": "string",
                "required": True,
                "doc": "The path to the local folder that represents the package.",
            }
        }

    # def _supports(self) -> Iterable[str]:
    #     return ["folder"]

    def _get_unique_source_type_id(self, source_details: Mapping) -> str:

        return source_details["path"]

    async def _process_pkg_versions(self, source_details: Mapping) -> Mapping[str, Any]:

        return {
            "versions": [
                PkgVersion(
                    vars={},
                    steps=[
                        {
                            "type": "folder",
                            "folder_path": os.path.abspath(source_details["path"]),
                        }
                    ],
                )
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
