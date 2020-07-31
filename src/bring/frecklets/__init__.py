# -*- coding: utf-8 -*-
import collections
from typing import Any, Mapping, MutableMapping, Optional, Union

from bring.bring import Bring
from bring.defaults import BRING_RESULTS_FOLDER, BRING_WORKSPACE_FOLDER
from freckles.core.frecklet import Frecklet
from frkl.common.filesystem import create_temp_dir
from tings.ting import TingMeta


def parse_target_data(
    target: Optional[Union[str]] = None,
    target_config: Optional[Mapping] = None,
    temp_folder_prefix: Optional[str] = None,
):

    if (
        not target
        or target.lower() == TEMP_DIR_MARKER
        or BRING_RESULTS_FOLDER in target
        or BRING_WORKSPACE_FOLDER in target
    ):
        _target_path: str = create_temp_dir(
            prefix=temp_folder_prefix, parent_dir=BRING_RESULTS_FOLDER
        )
        _target_msg: str = "new temporary folder"
        _is_temp: bool = True
    else:
        _target_path = target
        _target_msg = f"folder '{_target_path}'"
        _is_temp = False

    if not isinstance(_target_path, str):
        raise TypeError(f"Invalid type for 'target' value: {type(target)}")

    if target_config is None:
        _target_data: MutableMapping[str, Any] = {}
    else:
        if not isinstance(target_config, collections.abc.Mapping):
            raise TypeError(
                f"Invalid type for target_config value '{type(target_config)}'"
            )
        _target_data = dict(target_config)

    if "write_metadata" not in _target_data.keys():
        if _is_temp:
            _target_data["write_metadata"] = False
        else:
            _target_data["write_metadata"] = True

    if _target_data["write_metadata"] is None:
        if _is_temp:
            _target_data["write_metadata"] = False
        else:
            _target_data["write_metadata"] = True

    return {
        "target_config": _target_data,
        "target_path": _target_path,
        "target_msg": _target_msg,
        "is_temp": _is_temp,
    }


class BringFrecklet(Frecklet):
    def __init__(self, name: str, meta: TingMeta, init_values: Mapping[str, Any]):

        self._bring: Bring = init_values["bring"]
        super().__init__(name=name, meta=meta, init_values=init_values)

    @property
    def bring(self) -> Bring:

        return self._bring  # type: ignore


TEMP_DIR_MARKER = "__temp__"
