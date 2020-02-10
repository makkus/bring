# -*- coding: utf-8 -*-
import platform


def get_current_system_info():

    result = {}

    result["arch"] = platform.machine().lower()
    result["node"] = platform.node().lower()
    result["os"] = platform.system().lower()

    return result
