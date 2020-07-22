# -*- coding: utf-8 -*-
import os
from typing import Any, Dict, Mapping

from bring.mogrify import SimpleMogrifier
from frkl.common.formats.serialize import serialize
from frkl.common.subprocesses import AsyncSubprocess


class HelmTemplateMogrifier(SimpleMogrifier):

    _plugin_name: str = "helm_template"

    _requires = {
        "folder_path": "string",
        "name": "string",
        "values": "dict?",
        "namespace": "string?",
    }
    _provides = {"folder_path": "string"}

    def get_msg(self) -> str:

        return "creating kubernetes manifests"

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        path: str = requirements["folder_path"]
        name: str = requirements["name"]
        values: Dict[str, Any] = requirements.get("values", {})
        namespace: str = requirements.get("namespace", "default")

        target_path = self.create_temp_dir(prefix="helm_template_")

        val_args = []
        if values:
            values_file = os.path.join(target_path, "_vals.yaml")
            serialize(
                values,
                format="yaml",
                target={"target": values_file, "target_opts": {"force": False}},
            )
            val_args.append("--values")
            val_args.append(values_file)

        helm_template = AsyncSubprocess(
            "helm",
            "template",
            name,
            path,
            "--namespace",
            namespace,
            "--output-dir",
            target_path,
            *val_args
        )
        await helm_template.run(wait=True)

        return {"folder_path": target_path}
