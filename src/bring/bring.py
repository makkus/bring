# -*- coding: utf-8 -*-

"""Main module."""
import os
from typing import List, Dict, Any

import requests

from frutils.downloads import download_cached_text_file
from frutils.formats import SmartInput
from frutils.templating import replace_strings_in_obj, get_global_jinja_env
from tings import Tings, TingFindersPlugting, TingSpec
from tings.defaults import TINGS_INPUT_KEY
from tings.properties import TingProperty
from tings.ting import TingCallbackInput


class BringTings(Tings):
    def __init__(self, base_paths):

        self._base_paths = base_paths
        src = SmartInput(
            input_value="/home/markus/projects/new/bring/src/bring/resources/bring.tings",
            force_content="dict",
        )
        finder_conf = src.content.get("finder", "plugin-finder")

        pt = TingFindersPlugting()
        self._finder = pt.create_obj(init_data=finder_conf)

        spec = src.content.get("spec")
        spec = TingSpec.from_dict(spec)

        repl = {"base_paths": base_paths}

        find_data = src.content.get("find_data")
        self._find_data = replace_strings_in_obj(
            find_data,
            replacement_dict=repl,
            jinja_env=get_global_jinja_env(delimiter_profile="frkl", env_type="native"),
        )

        super(BringTings, self).__init__(ting_spec=spec)
        self.add_index("alias")
        self.add_index("id")

        self._finder.register_tings(self, find_data=self._find_data)

    @property
    def finder(self):
        return self._finder

    def bring_pkgs(self):

        result = []
        for ting in self.tings:
            if ting.alias == "_bring":
                continue
            result.append(ting)
        return result


class BringParents(TingProperty):
    def __init__(self, id_property, alias_property, target_property):

        self._id_property = id_property
        self._target_property = target_property
        self._alias_property = alias_property

    def provides(self) -> List[str]:
        return [self._target_property]

    def requires(self) -> List[str]:

        return [self._id_property, self._alias_property, TINGS_INPUT_KEY]

    def get_value(self, requirements: Dict[str, Any], property_name):

        id = requirements[self._id_property]
        alias = requirements[self._alias_property]

        if alias == "_bring":
            return None

        tings_wrapper: TingCallbackInput = requirements[TINGS_INPUT_KEY]
        tings = tings_wrapper(f"id")

        tokens = id.split(os.path.sep)

        current = []
        chain = []
        for token in tokens:
            meta_alias = os.path.join(*current, "_bring")

            if meta_alias in tings.keys():
                meta_data = tings_wrapper(f"id.{meta_alias}")
                chain.append(meta_data.data)
            current.append(token)

        return chain


class LookupData(TingProperty):
    def __init__(
        self, source_property, lookup_key="lookup", target_property="lookup_data"
    ):

        self._source_property = source_property
        self._lookup_key = lookup_key
        self._target_property = target_property

    def provides(self) -> List[str]:

        return [self._target_property]

    def requires(self) -> List[str]:

        return [self._source_property]

    def get_value(self, requirements: Dict[str, Any], property_name):

        source_dict = requirements[self._source_property]

        lookup_data = source_dict.get(self._lookup_key, [])

        url = "https://api.github.com/repos/sharkdp/bat/releases"

        download_cached_text_file(cache_base=BRING_DOWNLOAD_CACHE)
