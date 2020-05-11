# -*- coding: utf-8 -*-
from typing import TYPE_CHECKING, Any, Dict, Mapping, Optional

from frtls.dicts import dict_merge
from tings.ting import SimpleTing, TingMeta
from tings.ting.inheriting import InheriTing


if TYPE_CHECKING:
    pass


class ConfigTing(InheriTing, SimpleTing):
    """Represents a config profile.

    Config profiles can inherit from other profiles, overwriting one or several of the parent key/value pairs.
    """

    def __init__(
        self,
        name: str,
        meta: TingMeta,
        parent_key: str = "parent",
        info_key: str = "info",
    ):

        self._parent_key = parent_key
        self._info_key = info_key

        super().__init__(name=name, meta=meta)

    def provides(self) -> Dict[str, str]:

        return {
            self._parent_key: "string?",
            self._info_key: "string?",
            "config": "dict",
        }

    def requires(self) -> Dict[str, str]:

        return {"ting_dict": "dict"}

    async def retrieve(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        config_dict: Dict = dict(requirements["ting_dict"])

        parent = config_dict.pop(self._parent_key, None)
        info = config_dict.pop(self._info_key, {})

        result = {}
        if "config" in value_names:
            if "config" in requirements.keys():
                # still valid cache
                config = requirements["config"]
                result["config"] = config
            else:
                config = await self._get_config(config_dict, parent)
                result["config"] = config

        if self._info_key in value_names:
            result[self._info_key] = info
        if self._parent_key in value_names:
            result[self._parent_key] = parent

        return result

    async def _get_config(
        self, raw_config: Dict, parent: Optional[str] = None
    ) -> Dict[str, Any]:

        if not parent:
            return raw_config
        else:
            parent_vals = await self._get_values_from_ting(
                f"{self.namespace}.{parent}", "config"
            )
            config = parent_vals["config"]
            dict_merge(config, raw_config, copy_dct=False)
            return config
