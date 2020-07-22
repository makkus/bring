# -*- coding: utf-8 -*-
import collections
import logging
from typing import Any, Dict, Mapping, Optional, Union

from freckles.core.frecklet import Frecklet
from frkl.common.strings import generate_valid_identifier
from tings.ting import SimpleTing, TingMeta
from tings.tingistry import Tingistries, Tingistry


log = logging.getLogger("freckles")

DEFAULT_FRECKLES_PROTOTYPE_NAME = "internal.prototings.freckles"
DEFAULT_FRECKLES_TING_NAME = "freckles"


class Freckles(SimpleTing):
    @classmethod
    def get_default(cls, tingistry: Optional[Tingistry] = None) -> "Freckles":

        if tingistry is None:
            try:
                tingistry = Tingistries().get_tingistry("freckles")
            except KeyError:
                tingistry = Tingistries().create("freckles")

        if DEFAULT_FRECKLES_PROTOTYPE_NAME not in tingistry.ting_names:
            tingistry.register_prototing(DEFAULT_FRECKLES_PROTOTYPE_NAME, Freckles)

        if DEFAULT_FRECKLES_TING_NAME not in tingistry.ting_names:
            ting: Freckles = tingistry.create_ting(  # type: ignore
                DEFAULT_FRECKLES_PROTOTYPE_NAME, DEFAULT_FRECKLES_TING_NAME
            )
        else:
            ting = tingistry.get_ting(DEFAULT_FRECKLES_TING_NAME)  # type: ignore
            if not isinstance(ting, Freckles):
                raise TypeError(
                    f"Invalid type for registered default freckles object: {type(ting)}"
                )
        return ting

    def __init__(self, name: str, meta: TingMeta):

        super().__init__(name=name, meta=meta)

    def requires(self) -> Mapping[str, Union[str, Mapping[str, Any]]]:

        return {
            "frecklet_types": {
                "type": "dict",
                "required": False,
                "doc": "a dictionary of frecklet types, with the type name as key, and the registered ting name as value",
            }
        }

    def provides(self) -> Mapping[str, Union[str, Mapping[str, Any]]]:

        return {
            "frecklet_types": {
                "type": "dict",
                "required": True,
                "doc": "a dictionary of frecklet types, with the type name as key, and the registered ting name as value",
            }
        }

    async def retrieve(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        result = {}
        if "frecklet_types" in value_names:
            ft = requirements.get("frecklet_types", None)
            if ft is None:
                ft = {}
            result["frecklet_types"] = ft

        return result

    async def add_frecklet_types(self, **frecklet_types: str):

        orig = await self.get_value("frecklet_types")
        updated = dict(orig)
        updated.update(frecklet_types)

        if updated != orig:
            self.set_input(frecklet_types=updated)

    async def create_frecklet(
        self, frecklet_config: Union[str, Mapping[str, Any]]
    ) -> Frecklet:

        frecklet_types: Mapping[str, str] = await self.get_value("frecklet_types")

        if isinstance(frecklet_config, str):
            _frecklet_data: Dict[str, Any] = {"type": frecklet_config}
        elif isinstance(frecklet_config, collections.abc.Mapping):
            _frecklet_data = dict(frecklet_config)
        else:
            raise TypeError(
                f"Can't create frecklet, invalid input type '{type(frecklet_config)}': {frecklet_config}"
            )

        _frecklet_type = _frecklet_data.pop("type", None)
        if _frecklet_type is None:
            raise ValueError(
                f"Can't create frecklet, no frecklet type provided in config: {_frecklet_data}"
            )

        _frecklet_id = _frecklet_data.pop("id", None)
        if _frecklet_id is None:
            _frecklet_id = generate_valid_identifier(
                prefix=f"{_frecklet_type}_", length_without_prefix=6
            )

        ting_name = f"{self.full_name}.frecklets.{_frecklet_id}"

        prototing_name = frecklet_types.get(_frecklet_type, None)
        if prototing_name is None:
            raise ValueError(
                f"Can't create frecklet: frecklet type '{_frecklet_type}' not registered. Registered types: {', '.join(frecklet_types.keys())}"
            )

        frecklet: Frecklet = self.tingistry.create_ting(  # type: ignore
            prototing=prototing_name, ting_name=ting_name
        )  # type: ignore
        frecklet.set_input(**_frecklet_data)

        return frecklet
