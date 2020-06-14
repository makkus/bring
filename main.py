# -*- coding: utf-8 -*-
import os
import subprocess
from pathlib import Path
from typing import Iterable, Optional

from bring.config.bring_config import BringConfig
from bring.defaults import BRINGISTRY_INIT, BRING_APP_DIRS
from bring.pkg_types import PkgType
from bring.utils.doc import create_pkg_type_markdown_string
from deepdiff import DeepHash
from frtls.async_helpers import wrap_async_task
from frtls.dicts import get_seeded_dict
from frtls.files import ensure_folder
from frtls.types.utils import load_modules
from tings.tingistry import Tingistries


CACHE_DIR = os.path.join(BRING_APP_DIRS.user_cache_dir, "doc_gen")
ensure_folder(CACHE_DIR)

os_env_vars = get_seeded_dict(os.environ, {"BRING_CONSOLE_WIDTH": "100"})

modules: Iterable[str] = BRINGISTRY_INIT["modules"]  # type: ignore
load_modules(*modules)
tingistry = Tingistries.create("bring")
freckles = None

bring_config = BringConfig(name="doc")
bring = bring_config.get_bring()


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
            result = subprocess.check_output(command, env=os_env_vars)
            stdout = result.decode()
            cache_file.write_text(stdout)

        if print_command:
            stdout = f"> {' '.join(command)}\n{stdout}"
        if code_block:
            stdout = "``` console\n" + stdout + "\n```\n"

        if max_height is not None and max_height > 0:
            stdout = f"<div style='max-height:{max_height}px;overflow:auto'>\n{stdout}\n</div>"

        return stdout

    @env.macro
    def pkg_type_plugins():

        pm = bring.typistry.get_plugin_manager(PkgType)

        result = []
        for plugin_name in pm.plugin_names:
            doc = pm.get_plugin_doc(plugin_name)
            desc_string = wrap_async_task(
                create_pkg_type_markdown_string,
                bring=bring,
                plugin_doc=doc,
                header_level=4,
                add_description_header=False,
            )

            plugin_string = f"## ``{plugin_name}``\n\n{desc_string}\n\n"
            short_help = doc.get_short_help(default=None)
            if short_help:
                plugin_string += short_help + "\n\n"
            result.append(plugin_string)

        return "\n".join(result)
