# -*- coding: utf-8 -*-
import platform
from typing import Any, Mapping


def get_current_system_info() -> Mapping[str, Any]:

    result = {}

    result["arch"] = platform.machine().lower()
    result["node"] = platform.node().lower()
    result["os"] = platform.system().lower()

    return result
