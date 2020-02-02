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
