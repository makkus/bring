# -*- coding: utf-8 -*-
import os
import sys

from appdirs import AppDirs

from bring.system_info import get_current_system_info

bring_app_dirs = AppDirs("bring", "frkl")

if not hasattr(sys, "frozen"):
    BRING_MODULE_BASE_FOLDER = os.path.dirname(__file__)
    """Marker to indicate the base folder for the `bring` module."""
else:
    BRING_MODULE_BASE_FOLDER = os.path.join(sys._MEIPASS, "bring")
    """Marker to indicate the base folder for the `bring` module."""

BRING_RESOURCES_FOLDER = os.path.join(BRING_MODULE_BASE_FOLDER, "resources")

BRING_DOWNLOAD_CACHE = os.path.join(bring_app_dirs.user_cache_dir, "downloads")

BRING_WORKSPACE_FOLDER = os.path.join(bring_app_dirs.user_cache_dir, "workspace")

BRING_PKG_CACHE = os.path.join(bring_app_dirs.user_cache_dir, "pkgs")
DEFAULT_ARTEFACT_METADATA = {"type": "auto"}


BRINGISTRY_CONFIG = {
    # "name": "bringistry",
    # "tingistry_class": "bringistry",
    "ting_types": [
        {"name": "bring.types.pkg", "ting_class": "pkg_ting"},
        {"name": "bring.types.pkg_list", "ting_class": "pkg_tings"},
        {
            "name": "bring.transform.profiles.executables",
            "ting_class": "transform_profile",
            "ting_init": {
                "transformers_config": [
                    {"type": "rename"},
                    {"type": "file_filter", "include": []},
                    {
                        "type": "set_mode",
                        "set_executable": True,
                        # "set_readable": True
                    },
                ]
            },
        },
    ],
    "tings": [{"ting_type": "bring.types.pkg_list", "ting_name": "bring.pkgs"}],
    "preload_modules": [
        "bring",
        "bring.bring",
        "bring.pkg_resolvers",
        "bring.pkg_resolvers.git_repo",
        "bring.pkg_resolvers.template_url",
        "bring.pkg_resolvers.github_release",
        "bring.artefact_handlers.archive",
        "bring.artefact_handlers.file",
        "bring.artefact_handlers.folder",
        "bring.transform",
    ],
}

DEFAULT_CONTEXTS = {
    "executables": {
        "index": ["/home/markus/projects/tings/bring/repos/executables"],
        "default_transform_profile": "executables",
        "max_metadata_age": "24h",
        "defaults": get_current_system_info(),
    }
}
