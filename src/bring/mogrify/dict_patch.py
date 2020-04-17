# -*- coding: utf-8 -*-
import logging
import os
from typing import Any, Mapping, Optional

from bring.mogrify import SimpleMogrifier
from dictdiffer import patch
from frtls.exceptions import FrklException
from frtls.formats.input_formats import SmartInput
from ruamel.yaml import YAML


log = logging.getLogger("bring")


class YamlPatchMogrifier(SimpleMogrifier):

    _plugin_name = "yaml_patch"

    def __init__(self, name: str, meta: Optional[Mapping[str, Any]] = None) -> None:

        super().__init__(name=name, meta=meta)

    def get_msg(self) -> Optional[str]:

        return "patching dict"

    def requires(self) -> Mapping[str, str]:

        return {"folder_path": "string", "patch_map": "dict"}

    def provides(self) -> Mapping[str, str]:

        return {"folder_path": "string"}

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        path: str = requirements["folder_path"]
        patch_map: Mapping = requirements["patch_map"]

        for file, patch_set in patch_map.items():

            target_file = os.path.join(path, file)
            if not os.path.exists(target_file):
                raise FrklException(
                    msg=f"Can't patch file '{file}'.", reason="File does not exists."
                )
            if not os.path.isfile(target_file):
                raise FrklException(
                    msg=f"Can't patch file '{file}'.", reason="Not a file."
                )

            await self.patch(target_file, patch_set)

        return {"folder_path": path}

    async def patch(self, full_path: str, patch_set: Mapping) -> None:

        si = SmartInput(full_path)
        content = await si.content_async()
        yaml = YAML()
        dict_content = yaml.load_all(content)
        new_content = patch(patch_set, list(dict_content))

        with open(full_path, "w") as f:
            yaml.dump_all(new_content, f)
