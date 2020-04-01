# -*- coding: utf-8 -*-
import os
import sys
from typing import Any, Dict

from appdirs import AppDirs


BRING_APP_DIRS = AppDirs("bring", "frkl")

if not hasattr(sys, "frozen"):
    BRING_MODULE_BASE_FOLDER = os.path.dirname(__file__)
    """Marker to indicate the base folder for the `bring` module."""
else:
    BRING_MODULE_BASE_FOLDER = os.path.join(sys._MEIPASS, "bring")  # type: ignore
    """Marker to indicate the base folder for the `bring` module."""

BRING_CONTEXTS_FOLDER = os.path.join(BRING_APP_DIRS.user_config_dir, "contexts")

BRING_RESOURCES_FOLDER = os.path.join(BRING_MODULE_BASE_FOLDER, "resources")
BRING_DEFAULT_CONTEXTS_FOLDER = os.path.join(BRING_RESOURCES_FOLDER, "default_contexts")

BRING_DOWNLOAD_CACHE = os.path.join(BRING_APP_DIRS.user_cache_dir, "downloads")
BRING_CONTEXT_FILES_CACHE = os.path.join(BRING_DOWNLOAD_CACHE, "contexts")

BRING_GIT_CHECKOUT_CACHE = os.path.join(BRING_APP_DIRS.user_cache_dir, "git_checkouts")

BRING_WORKSPACE_FOLDER = os.path.join(BRING_APP_DIRS.user_cache_dir, "workspace")

BRING_PKG_CACHE = os.path.join(BRING_APP_DIRS.user_cache_dir, "pkgs")
DEFAULT_CONTEXT_NAME = "binaries"

BRINGISTRY_PRELOAD_MODULES = [
    "bring.bring",
    "bring.pkg",
    "bring.pkgs",
    "bring.pkg_resolvers.*",
    "bring.mogrify.*",
    "bring.context",
    "bring.config",
]

BRING_CONTEXT_NAMESPACE = "bring.contexts"

BRING_DEFAULT_CONFIG = {
    "contexts": [
        {
            "name": "binaries",
            "type": "index",
            "indexes": [
                "https://gitlab.com/tingistries/binaries/-/raw/master/binaries.bx"
            ],
            "defaults": {"target": "~/.local/bring"},
        },
        {
            "name": "install-manifests",
            "type": "index",
            "indexes": [
                "https://gitlab.com/tingistries/install-manifests/-/raw/master/install-manifests.bx"
            ],
        },
    ],
    "default_context": "binaries",
    "task_log": "terminal",
}

BRINGISTRY_CONFIG = {
    "prototings": [
        {"prototing_name": "bring.types.dynamic_pkg", "ting_class": "dynamic_pkg_ting"},
        {"prototing_name": "bring.types.static_pkg", "ting_class": "static_pkg_ting"},
        {
            "ting_name": "bring.config_profiles",
            "prototing_name": "internal.singletings.config_profiles",
            "ting_class": "folder_config_profiles_ting",
            "prototing_factory": "singleting",
            "default_config": BRING_DEFAULT_CONFIG,
            "config_path": BRING_APP_DIRS.user_config_dir,
            "config_file_ext": "config",
        },
        # {
        #     "ting_name": BRING_CONTEXT_NAMESPACE,
        #     "prototing_name": "internal.singletings.context_list",
        #     "ting_class": "subscrip_tings",
        #     "prototing_factory": "singleting",
        #     "prototing": "bring_dynamic_context_ting",
        #     "subscription_namespace": "bring.contexts.dynamic",
        # },
        {
            "prototing_name": "bring.types.config_file_context_maker",
            "ting_class": "text_file_ting_maker",
            "prototing": "bring_dynamic_context_ting",
            "ting_name_strategy": "basename_no_ext",
            "ting_target_namespace": BRING_CONTEXT_NAMESPACE,
            "file_matchers": [{"type": "extension", "regex": ".*\\.context$"}],
        },
        {
            "prototing_name": "bring.types.contexts.default_context",
            "ting_class": "bring_static_context_ting",
        }
        # {
        #     "prototing_name": "bring.types.static_context_maker",
        #     "ting_class": "smart_input_dict_ting_maker",
        #     "prototing": "bring_static_context_ting",
        #     "ting_target_namespace": "bring.contexts.static"
        # }
    ],
    "tings": [],
    "modules": BRINGISTRY_PRELOAD_MODULES,
    "classes": [
        "bring.pkg_resolvers.PkgResolver",
        "bring.mogrify.Mogrifier",
        "frtls.tasks.task_watcher.TaskWatcher",
    ],
}

# DEFAULT_CONTEXTS = {
#     "binaries": {
#         "index": ["/home/markus/projects/tings/bring/repos/binaries"],
#         "default_transform_profile": "binaries",
#         "metadata_max_age": 3600 * 24,
#         "defaults": get_current_system_info(),
#     }
# }


PKG_RESOLVER_DEFAULTS: Dict[str, Any] = {"metadata_max_age": 3600 * 24}

BRING_METADATA_FOLDER_NAME = ".bring"
BRING_ALLOWED_MARKER_NAME = "bring_allowed"

BRING_TASKS_BASE_TOPIC = "bring.tasks"
