# -*- coding: utf-8 -*-
import os
import sys
from typing import Any, Dict, Mapping

from appdirs import AppDirs
from frtls.templating.jinja import get_global_jinja_env


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

BRING_BACKUP_FOLDER = os.path.join(BRING_APP_DIRS.user_data_dir, "backup")

DEFAULT_CONTEXT_NAME = "binaries"

BRINGISTRY_PRELOAD_MODULES = [
    "bring.bring",
    "bring.pkg_types.*",
    "bring.mogrify.*",
    "bring.plugins.*",
    "bring.plugins.templating.*",
    "bring.pkg_index.*",
    "bring.config",
    "frtls.tasks.watchers.*",
    "freckles.core.*",
    "freckles.frecklets.*",
]

BRING_CONTEXT_NAMESPACE = "bring.indexes"
BRING_CONFIG_PROFILES_NAME = "bring.config_profiles"

# BRING_DEFAULT_INDEXES = [
#     {
#         "id": "binaries",
#         "type": "index_file",
#         "uri": "https://gitlab.com/bring-indexes/binaries/-/raw/master/binaries.br.idx",
#         # "defaults": {"target": "~/.local/bring", "vars": {}},
#         # "add_sysinfo_to_default_vars": True,
#         "info": {"slug": "Single file, compiled applications."},
#     },
#     {
#         "id": "scripts",
#         "type": "index_file",
#         "uri": "https://gitlab.com/bring-indexes/scripts/-/raw/master/scripts.br.idx",
#         # "defaults": {"target": "~/.local/bring", "vars": {}},
#         # "add_sysinfo_to_default_vars": True,
#         "info": {"slug": "Shell scripts."},
#     },
#     {
#         "id": "collections",
#         "type": "index_file",
#         "uri": "https://gitlab.com/bring-indexes/collections/-/raw/master/collections.br.idx",
#         "info": {"slug": "Miscellaneous collections of files."},
#     },
#     {
#         "id": "kubernetes",
#         "type": "index_file",
#         "uri": "https://gitlab.com/bring-indexes/kube-install-manifests/-/raw/master/kube-install-manifests.br.idx",
#         "info": {"slug": "Install manifests for Kubernetes apps."},
#     },
# ]

BRING_DEFAULT_INDEX_CONFIG: Mapping[str, Mapping[str, Any]] = {
    "binaries": {
        "info": {
            "slug": "Single file, compiled applications.",
            "desc": """This index contains single-file binaries that don't require any dependencies to be installed in order to work.

By default, those binaries will be installed into '$HOME/.local/bring', using the default 'bring' merge strategy (save metadata about each installed file, more information can be found [here](https://bring.frkl.io/docs/reference/merging/).""",
        }
    },
    "scripts": {"info": {"slug": "Single file scripts."}},
    "collections": {
        "info": {"slug": "Miscellaneous collections of sets of related files."}
    },
    "kubernetes": {"info": {"slug": "Install manifests for Kubernetes apps."}},
}

BRING_DEFAULT_INDEX_ALIASES = {
    "binaries": "gitlab.bring-indexes.binaries",
    "scripts": "gitlab.bring-indexes.scripts",
    "collections": "gitlab.bring-indexes.collections",
    "kubernetes": "gitlab.bring-indexes.kube-install-manifests",
}

BRING_CORE_CONFIG = {
    # "indexes": ["binaries", "scripts", "collections", "kube-install-manifests"],
    # "default_index": "binaries",
    "task_log": [],
    "defaults": {},
    "output": "default",
    # "add_sysinfo_to_default_vars": False,
}

BRING_DEFAULT_CONFIG = {
    "info": {"slug": "default config for bring"},
    "defaults": {"_system_info": True},
    "indexes": [
        {
            "id": "binaries",
            "defaults": {"target": "~/.local/bring", "_system_info": True},
        },
        {
            "id": "scripts",
            "defaults": {"target": "~/.local/bring", "_system_info": True},
        },
        "kubernetes",
        "collections",
    ],
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


BRING_ALLOWED_MARKER_NAME = "bring_allowed"

BRING_TASKS_BASE_TOPIC = "bring.tasks"

BRING_NO_METADATA_TIMESTAMP_MARKER = "unknown_metadata_timestamp"

BRING_TEMP_FOLDER_MARKER = "__temp__"

BRING_INS_JINJA_ENV = get_global_jinja_env(delimiter_profile="frkl", env_type="native")

BRING_AUTO_ARG = {"type": "string", "required": True}
DEFAULT_ARGS_DICT = {
    "os": {"doc": "The operating system to run on.", "type": "string"},
    "arch": {"doc": "The architecture of the underlying system.", "type": "string"},
    "version": {"doc": "The version of the package.", "default": "latest"},
}
BRING_METADATA_FOLDER_NAME = ".bring"
BRING_METADATA_FILE_NAME = "meta.json"
BRING_METADATA_REL_PATH = os.path.join(
    BRING_METADATA_FOLDER_NAME, BRING_METADATA_FILE_NAME
)

DEFAULT_FOLDER_INDEX_NAME = "this.br.idx"
