# -*- coding: utf-8 -*-
import logging
import os
from typing import Any, Mapping, Optional

from bring.mogrify import MogrifierException, SimpleMogrifier
from frkl.common.filesystem import ensure_folder
from frkl.common.subprocesses import GitProcess


log = logging.getLogger("bring")


class GitArchiveMogrifier(SimpleMogrifier):

    _plugin_name: str = "git_archive"

    _requires: Mapping[str, str] = {
        "url": "string",
        "version": "string",
        "files": "list",
    }
    _provides: Mapping[str, str] = {"file_path": "string"}

    def get_msg(self) -> str:

        vals = self.user_input
        url = vals.get("url", "[dynamic url]")
        version = vals.get("version", None)

        result = f"retrieving files from git repo '{url}'"
        if version is not None:
            result = result + f" (version: {version})"

        return result

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        url = requirements["url"]
        version = requirements.get("version", "master")
        files = requirements["files"]
        if isinstance(files, str):
            files = [files]

        temp_path = self.create_temp_dir("git_archive_")
        target_folder = os.path.join(temp_path, os.path.basename(url))

        target_file = os.path.join(target_folder, "archive.zip")

        ensure_folder(target_folder)

        args = [
            "archive",
            "--format=zip",
            "-o",
            target_file,
            f"--remote={url}",
            version,
        ] + files

        archive_cmd = GitProcess(*args, working_dir=target_folder)

        await archive_cmd.run(wait=True, raise_exception=False)

        success = await archive_cmd.success

        if not success:
            stderr = await archive_cmd.stderr
            solution: Optional[str] = None
            if url.startswith("http"):
                solution = f"You use a http url, there is a good chance the remote server does not support that. Try a url using the git or ssh protocol instead of your current one: {url}"

            raise MogrifierException(
                mogrifier=self,
                msg="Error running 'git archive' command.",
                reason=stderr,
                solution=solution,
            )

        return {"file_path": target_file}
