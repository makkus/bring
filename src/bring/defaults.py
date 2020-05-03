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

# BRING_CONTEXTS_FOLDER = os.path.join(BRING_APP_DIRS.user_config_dir, "indexes")

BRING_RESOURCES_FOLDER = os.path.join(BRING_MODULE_BASE_FOLDER, "resources")
# BRING_DEFAULT_CONTEXTS_FOLDER = os.path.join(BRING_RESOURCES_FOLDER, "default_indexes")

BRING_DOWNLOAD_CACHE = os.path.join(BRING_APP_DIRS.user_cache_dir, "downloads")
BRING_INDEX_FILES_CACHE = os.path.join(BRING_DOWNLOAD_CACHE, "indexes")

BRING_GIT_CHECKOUT_CACHE = os.path.join(BRING_APP_DIRS.user_cache_dir, "git_checkouts")

BRING_WORKSPACE_FOLDER = os.path.join(BRING_APP_DIRS.user_cache_dir, "workspace")
BRING_RESULTS_FOLDER = os.path.join(BRING_WORKSPACE_FOLDER, "results")

BRING_PKG_CACHE = os.path.join(BRING_APP_DIRS.user_cache_dir, "pkgs")
BRING_PLUGIN_CACHE = os.path.join(BRING_APP_DIRS.user_cache_dir, "plugins")
DEFAULT_CONTEXT_NAME = "binaries"

BRINGISTRY_PRELOAD_MODULES = [
    "bring.bring",
    "bring.pkg",
    "bring.pkgs",
    "bring.pkg_types.*",
    "bring.mogrify.*",
    "bring.plugins.*",
    "bring.plugins.templating.*",
    "bring.pkg_index",
    "bring.config",
]

BRING_CONTEXT_NAMESPACE = "bring.indexes"
BRING_CONFIG_PROFILES_NAME = "bring.config_profiles"

BRING_DEFAULT_CONTEXTS = {
    "binaries": {
        "type": "index",
        "indexes": [
            "https://gitlab.com/tingistries/binaries/-/raw/master/binaries.br.idx"
        ],
        "defaults": {"target": "~/.local/bring", "vars": {}},
        "add_sysinfo_to_default_vars": True,
        "info": {"slug": "Single file, compiled applications."},
    },
    "scripts": {
        "type": "index",
        "indexes": [
            "https://gitlab.com/tingistries/scripts/-/raw/master/scripts.br.idx"
        ],
        "defaults": {"target": "~/.local/bring", "vars": {}},
        "add_sysinfo_to_default_vars": True,
        "info": {"slug": "Shell scripts."},
    },
    "collections": {
        "type": "index",
        "indexes": [
            "https://gitlab.com/tingistries/collections/-/raw/master/collections.br.idx"
        ],
        "info": {"slug": "Miscellaneous collections of files."},
    },
    "kube-install-manifests": {
        "type": "index",
        "indexes": [
            "https://gitlab.com/tingistries/kube-install-manifests/-/raw/master/kube-install-manifests.br.idx"
        ],
        "info": {"slug": "Install manifests for Kubernetes apps."},
    },
}

BRING_DEFAULT_CONFIG = {
    "indexes": ["binaries", "scripts", "collections", "kube-install-manifests"],
    # "default_index": "binaries",
    "task_log": [],
    "defaults": {"vars": {}},
    "output": "default",
    "add_sysinfo_to_default_vars": False,
}

BRING_DEFAULT_CONFIG_PROFILE = {
    "ting_name": "bring.config_profiles",
    "prototing_name": "internal.singletings.config_profiles",
    "ting_class": "folder_config_profiles_ting",
    "prototing_factory": "singleting",
    # "default_config": BRING_DEFAULT_CONFIG,
    "config_path": BRING_APP_DIRS.user_config_dir,
    "config_file_ext": "config",
}

BRINGISTRY_INIT = {
    "prototings": [
        {"prototing_name": "bring.types.dynamic_pkg", "ting_class": "dynamic_pkg_ting"},
        {"prototing_name": "bring.types.static_pkg", "ting_class": "static_pkg_ting"},
        # {
        #     "ting_name": BRING_CONTEXT_NAMESPACE,
        #     "prototing_name": "internal.singletings.index_list",
        #     "ting_class": "subscrip_tings",
        #     "prototing_factory": "singleting",
        #     "prototing": "bring_dynamic_index_ting",
        #     "subscription_namespace": "bring.indexes.dynamic",
        # },
        {
            "prototing_name": "bring.types.config_file_index_maker",
            "ting_class": "text_file_ting_maker",
            "prototing": "bring_dynamic_index_ting",
            "ting_name_strategy": "basename_no_ext",
            "ting_target_namespace": BRING_CONTEXT_NAMESPACE,
            "file_matchers": [{"type": "extension", "regex": ".*\\.index$"}],
        },
        {
            "prototing_name": "bring.types.indexes.default_index",
            "ting_class": "bring_static_index_ting",
        }
        # {
        #     "prototing_name": "bring.types.static_index_maker",
        #     "ting_class": "smart_input_dict_ting_maker",
        #     "prototing": "bring_static_index_ting",
        #     "ting_target_namespace": "bring.indexes.static"
        # }
    ],
    "tings": [],
    "modules": BRINGISTRY_PRELOAD_MODULES,
    "classes": [
        "bring.pkg_types.PkgType",
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

BRING_NO_METADATA_TIMESTAMP_MARKER = "unknown_metadata_timestamp"
