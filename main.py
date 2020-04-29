# -*- coding: utf-8 -*-
import subprocess
from typing import Optional


def define_env(env):
    """
    This is the hook for defining variables, macros and filters

    - variables: the dictionary that contains the environment variables
    - macro: a decorator function, to declare a macro.
    """

    env.variables["baz"] = "John Doe"

    @env.macro
    def cli(
        *command,
        print_command: bool = True,
        code_block: bool = True,
        max_height: Optional[int] = None,
    ):
        result = subprocess.check_output(command)

        stdout = result.decode()

        if print_command:
            stdout = f"> {' '.join(command)}\n{stdout}"
        if code_block:
            stdout = "``` console\n" + stdout + "\n```\n"

        if max_height is not None and max_height > 0:
            stdout = f"<div style='max-height:{max_height}px;overflow:auto'>\n{stdout}\n</div>"

        return stdout
