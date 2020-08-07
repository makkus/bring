# -*- coding: utf-8 -*-
from frkl.common.doc import Doc
from frkl.explain.explanation import Explanation
from frkl.types.plugins import PluginManager


class PluginDocManagement(object):
    def __init__(self, plugin_manager: PluginManager):

        self._plugin_manager: PluginManager = plugin_manager

    def plugin_doc(self, plugin_name) -> Doc:

        return self._plugin_manager.get_plugin_doc(plugin_name=plugin_name)


class PkgTypeExplanation(Explanation):
    def __init__(self, plugin_manager: PluginManager):

        self._plugin_manager: PluginManager = plugin_manager

    def get_plugin(self, name):

        return self._plugin_manager.get_plugin(name)
