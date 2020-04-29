# -*- coding: utf-8 -*-
import os
from typing import Any, Mapping

from bring.mogrify import SimpleMogrifier
from bring.utils.git import ensure_repo_cloned
from frtls.subprocesses.git import GitProcess


class GitCloneMogrifier(SimpleMogrifier):

    _plugin_name: str = "git_clone"

    def requires(self) -> Mapping[str, str]:

        return {"url": "string", "version": "string"}

    def get_msg(self) -> str:

        vals = self.input_values
        url = vals.get("url", "[dynamic url]")
        version = vals.get("version", None)

        result = f"cloning git repository '{url}'"
        if version is not None:
            result = result + f" (version: {version})"

        return result

    def provides(self) -> Mapping[str, str]:

        return {"folder_path": "string"}

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        url = requirements["url"]
        version = requirements["version"]

        cache_path = await ensure_repo_cloned(url=url, update=True)

        temp_path = self.create_temp_dir("git_repo_")
        target_folder = os.path.join(temp_path, os.path.basename(url))

        clone_cmd = GitProcess("clone", cache_path, target_folder)
        await clone_cmd.run()
        checkout_cmd = GitProcess("checkout", version, working_dir=target_folder)
        await checkout_cmd.run()

        return {"folder_path": target_folder}
