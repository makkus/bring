# -*- coding: utf-8 -*-
import copy
import os
import subprocess
from pathlib import Path
from typing import Optional

from bring.defaults import bring_app_dirs as project_dirs
from deepdiff import DeepHash
from pydoc_markdown.main import RenderSession


CACHE_DIR = os.path.join(project_dirs.user_cache_dir, "doc_gen")
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

os_env_vars = copy.copy(os.environ)
os_env_vars["CONSOLE_WIDTH"] = "100"


def define_env(env):
    """
    This is the hook for defining variables, macros and filters

    - variables: the dictionary that contains the environment variables
    - macro: a decorator function, to declare a macro.
    """

    # env.variables["baz"] = "John Doe"

    @env.macro
    def cli(
        *command,
        print_command: bool = True,
        code_block: bool = True,
        max_height: Optional[int] = None,
    ):

        hashes = DeepHash(command)
        hash_str = hashes[command]

        cache_file: Path = Path(os.path.join(CACHE_DIR, hash_str))
        if cache_file.is_file():
            stdout = cache_file.read_text()
        else:
            try:
                result = subprocess.check_output(command, env=os_env_vars)
                stdout = result.decode()
                cache_file.write_text(stdout)
            except subprocess.CalledProcessError as e:
                print("stdout:")
                print(e.stdout)
                print("stderr:")
                print(e.stderr)
                raise e

        if print_command:
            stdout = f"> {' '.join(command)}\n{stdout}"
        if code_block:
            stdout = "``` console\n" + stdout + "\n```\n"

        if max_height is not None and max_height > 0:
            stdout = f"<div style='max-height:{max_height}px;overflow:auto'>\n{stdout}\n</div>"

        return stdout

    @env.macro
    def inline_file_as_codeblock(path, format: str = ""):
        f = Path(path)
        return f"```{format}\n{f.read_text()}\n```"


def build_api_docs(*args, **kwargs):

    root_dir = os.path.join(os.path.dirname(__file__), "..", "..")
    config = os.path.join(root_dir, "pydoc-markdown.yml")
    session = RenderSession(config)
    pydocmd = session.load()
    session.render(pydocmd)
