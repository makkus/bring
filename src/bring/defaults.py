# -*- coding: utf-8 -*-
import os
import sys

from appdirs import AppDirs

bring_app_dirs = AppDirs("bring", "frkl")

if not hasattr(sys, "frozen"):
    BRING_MODULE_BASE_FOLDER = os.path.dirname(__file__)
    """Marker to indicate the base folder for the `bring` module."""
else:
    BRING_MODULE_BASE_FOLDER = os.path.join(sys._MEIPASS, "bring")
    """Marker to indicate the base folder for the `bring` module."""

BRING_RESOURCES_FOLDER = os.path.join(BRING_MODULE_BASE_FOLDER, "resources")

BRING_DOWNLOAD_CACHE = os.path.join(bring_app_dirs.user_cache_dir, "downloads")

BRING_PKG_CACHE = os.path.join(bring_app_dirs.user_cache_dir, "pkgs")
DEFAULT_ARTEFACT_METADATA = {"type": "auto"}
BRINGISTRY_CONFIG = {
    "name": "bringistry",
    "tingistry_class": "bringistry",
    "ting_types": [
        {"name": "bring.bring_pkg_metadata", "ting_class": "bring_pkg_details"},
        {
            "name": "bring.bring_pkgs",
            "ting_class": "seed_tings",
            "ting_init": {
                "ting_type": "bring.bring_pkg_metadata",
                "child_name_strategy": "basename_no_ext",
            },
        },
        {
            "name": "bring.bring_input",
            "ting_class": "ting_ting",
            "ting_init": {"ting_types": ["text_file", "dict"]},
        },
        {
            "name": "bring.bring_file_watcher",
            "ting_class": "file_watch_source",
            "ting_init": {"matchers": [{"type": "extension", "regex": ".bring$"}]},
        },
        {
            "name": "bring.bring_file_source",
            "ting_class": "ting_watch_source",
            "ting_init": {
                "source_ting_type": "bring.bring_file_watcher",
                "seed_ting_type": "bring.bring_input",
            },
        },
        {"name": "bring.bring_dict_source", "ting_class": "dict_source"},
    ],
    "preload_modules": [
        "bring",
        "bring.pkg_resolvers",
        "bring.pkg_resolvers.git_repo",
        "bring.pkg_resolvers.github_release",
        "bring.artefact_handlers.archive",
        "bring.artefact_handlers.file",
        "bring.artefact_handlers.folder",
        "bring.file_sets.default",
    ],
    "tingistry_init": {"paths": []},
}
