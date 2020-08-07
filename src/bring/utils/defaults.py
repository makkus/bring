# -*- coding: utf-8 -*-
from abc import ABCMeta, abstractmethod
from typing import Any, Dict, List, Mapping, Tuple

from bring.utils.system_info import get_current_system_info
from frkl.common.dicts import get_seeded_dict
from frkl.common.exceptions import FrklException
from frkl.types.plugins import PluginFactory
from frkl.types.typistry import Typistry


class DefaultsProducer(metaclass=ABCMeta):
    @abstractmethod
    def get_values(self, **config) -> Mapping[str, Any]:
        pass


class SystemInfoProducer(DefaultsProducer):

    _plugin_name = "system_info"

    def get_values(self, **config) -> Mapping[str, Any]:

        return get_current_system_info()


def get_defaults_producer_factory(typistry: Typistry) -> PluginFactory:

    factory = typistry.register_plugin_factory(
        "defaults_producers",
        DefaultsProducer,
        singleton=True,
        allow_config_override=False,
        use_existing=True,
    )
    return factory


def calculate_defaults(typistry: Typistry, data: Mapping[str, Any]):

    pf = get_defaults_producer_factory(typistry)

    producers: List[Tuple] = []
    values: Dict[str, Any] = {}

    for k, v in data.items():
        if k.startswith("_"):
            pn = f"{k[1:]}"
            if pn in pf.plugin_names:
                producers.append((pn, v))
        else:
            values[k] = v

    result = []

    for item in producers:

        plugin: DefaultsProducer = pf.get_singleton(item[0])  # type: ignore
        val = item[1]
        if val is False or (isinstance(val, str) and val.lower() == "false"):
            continue

        if not isinstance(val, (bool, Mapping)):
            raise FrklException(
                msg=f"Can't calculate '{item[0]}' defaults for: {val}",
                reason="Value must be a boolean, or a dictionary.",
            )

        if isinstance(val, Mapping):
            result.append(plugin.get_values(**val))
        else:
            result.append(plugin.get_values())

    result.append(values)

    r = get_seeded_dict(*result, merge_strategy="merge")
    return r
