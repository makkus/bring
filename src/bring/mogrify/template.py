# -*- coding: utf-8 -*-
import logging
import os
from typing import Any, Mapping

from anyio import aopen
from bring.mogrify import SimpleMogrifier
from bring.utils.paths import find_matches
from frtls.files import ensure_folder
from frtls.templating import get_global_jinja_env, process_string_template
from jinja2 import Environment


log = logging.getLogger("bring")


class TemplateMogrifier(SimpleMogrifier):

    _plugin_name: str = "template"
    _requires: Mapping[str, str] = {
        "repl_dict": "dict",
        "folder_path": "string",
        "include": "list?",
        "flatten": "boolean?",
        "template_type": "string?",
    }
    _provides: Mapping[str, str] = {"folder_path": "string"}

    def get_msg(self) -> str:

        vals = self.user_input
        incl = vals.get("include", None)

        result = "processing template(s)"

        if incl:
            result += f" matching: {', '.join(incl)}"

        return result

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        repl_dict = requirements["repl_dict"]
        folder_path = requirements["folder_path"]
        include = requirements.get("include", None)
        flatten = requirements.get("flatten", False)
        template_type = requirements.get("template_type", "jinja")

        if isinstance(template_type, str):
            template_type = {"type": "jinja", "delimiter_profile": template_type}

        if template_type.get("type", "jinja") != "jinja":
            raise NotImplementedError("Only jinja templating supported so far.")

        delimiter_profile = template_type.get("delimiter_profile", "default")

        jinja_env = get_global_jinja_env(delimiter_profile=delimiter_profile)

        matches = find_matches(path=folder_path, include_patterns=include)
        matches = list(matches)

        target = self.create_temp_dir("template_")
        for m in matches:
            file_path = os.path.join(folder_path, m)

            if flatten:
                target_file = os.path.join(target, os.path.basename(m))
            else:
                target_file = os.path.join(target, m)
                ensure_folder(os.path.dirname(target_file))

            await self.process_template(
                source=file_path,
                target=target_file,
                repl_dict=repl_dict,
                jinja_env=jinja_env,
            )

        return {"folder_path": target}

    async def process_template(
        self,
        source: str,
        target: str,
        repl_dict: Mapping[str, Any],
        jinja_env: Environment,
    ):

        async with await aopen(source, "r") as f:
            content = await f.read()

        # checking after reading, because that's where we can be sure no file will suddenly appear
        if os.path.exists(target):
            log.warning(
                f"Ignoring duplicate templated file '{target}', consider setting 'flatten' to 'false'."
            )
        else:
            try:
                result = process_string_template(
                    template_string=content,
                    replacement_dict=repl_dict,
                    jinja_env=jinja_env,
                )
                async with await aopen(target, "w") as f:
                    await f.write(result)
            except Exception as e:
                log.debug(f"Error processing template '{source}': {e}", exc_info=True)
                raise e
