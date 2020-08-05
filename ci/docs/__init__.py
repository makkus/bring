# -*- coding: utf-8 -*-
import copy
import os
import subprocess
from pathlib import Path
from typing import Optional

from bring.defaults import bring_app_dirs as project_dirs
from frkl.common.downloads.cache import calculate_cache_location_for_url
from frkl.explain.explanations.exception import ExceptionExplanation
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

    def get_cache_key(key: str, *command: str):

        hash_obj = [key] + list(command)
        return calculate_cache_location_for_url("_".join(hash_obj), sep="_")

        # hashes = DeepHash(hash_obj)
        # hash_str = str(hashes[hash_obj])

    def read_cache(key: str, *command: str) -> Optional[str]:

        if os.environ.get("USE_DOCS_CACHE", "false").lower() != "true":
            return None

        hash_str = get_cache_key(key, *command)

        cache_file: Path = Path(os.path.join(CACHE_DIR, hash_str))
        text = None
        if cache_file.is_file():
            text = cache_file.read_text()

        return text

    def write_cache(key: str, *command: str, text: str) -> None:

        if os.environ.get("USE_DOCS_CACHE", "false").lower() != "true":
            return

        hash_str = get_cache_key(key, *command)

        cache_file: Path = Path(os.path.join(CACHE_DIR, hash_str))
        cache_file.write_text(text)

    @env.macro
    def cli(
        *command,
        print_command: bool = True,
        code_block: bool = True,
        max_height: Optional[int] = None,
    ):

        stdout = read_cache("cli", *command)
        if not stdout:

            try:
                env_vars = copy.copy(os_env_vars)
                env_vars["EXPORT_HTML"] = "false"
                result = subprocess.check_output(command, env=env_vars)
                stdout = result.decode()
                write_cache("cli", *command, text=stdout)
            except subprocess.CalledProcessError as e:
                print(f"Error with command: {' '.join(command)}")
                print("stdout:")
                print(e.stdout)
                print("stderr:")
                print(e.stderr)
                ex = ExceptionExplanation(e)
                ex_str = "\n".join(ex.create_exception_text())
                stdout = "```\n" + ex_str + "\n```\n"
                return stdout

        if print_command:
            stdout = f"> {' '.join(command)}\n{stdout}"
        if code_block:
            stdout = "``` console\n" + stdout + "\n```\n"

        if max_height is not None and max_height > 0:
            stdout = f"<div style='max-height:{max_height}px;overflow:auto'>\n{stdout}\n</div>"

        return stdout

    @env.macro
    def cli_html(
        *command, print_command: bool = True, max_height: Optional[int] = None,
    ):

        html_output = read_cache("cli_html", *command)
        if not html_output:
            try:
                env_vars = copy.copy(os_env_vars)
                env_vars["EXPORT_HTML"] = "true"
                result = subprocess.check_output(command, env=env_vars)
                stdout = result.decode()
                output = []
                started = False
                for line in stdout.split("\n"):
                    if "HTML_START" in line:
                        started = True
                        continue
                    if not started:
                        continue

                    if "HTML_END" in line:
                        break

                    output.append(line.rstrip())

                html_output = "\n".join(output)
                write_cache("cli_html", *command, text=html_output)
            except subprocess.CalledProcessError as e:
                print(f"Error with command: {' '.join(command)}")
                print("stdout:")
                print(e.stdout)
                print("stderr:")
                print(e.stderr)
                ex = ExceptionExplanation(e)
                ex_str = "\n".join(ex.create_exception_text())
                stdout = "```\n" + ex_str + "\n```\n"
                return stdout

        pre = """<pre style="font-family:'Roboto Mono',Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace;">"""
        post = "</pre>"

        if max_height is not None and max_height > 0:
            start = f"""<div style="max-height:{max_height}px;overflow:auto" class="terminal-output">\n"""
        else:
            start = """<div style="overflow:auto" class="terminal-output">\n"""

        html_output = html_output.strip()
        if print_command:
            html_output = f"""> {' '.join(command)}\n\n{html_output}"""

        end = "\n</div>"

        result_string = f"{pre}{start}{html_output}{end}{post}"
        return result_string

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
