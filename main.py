# -*- coding: utf-8 -*-
import subprocess


def define_env(env):
    """
    This is the hook for defining variables, macros and filters

    - variables: the dictionary that contains the environment variables
    - macro: a decorator function, to declare a macro.
    """

    env.variables["baz"] = "John Doe"

    @env.macro
    def cli(*command, print_command: bool = True, code_block: bool = True):
        result = subprocess.check_output(command)

        stdout = result.decode()

        if print_command:
            stdout = f"> {' '.join(command)}\n\n{stdout}"
        if code_block:
            stdout = f"``` console\n{stdout}\n```\n"

        return stdout
