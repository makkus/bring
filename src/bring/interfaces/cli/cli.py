# -*- coding: utf-8 -*-

import sys

import asyncclick as click
from bring.interfaces.cli.command_group import BringCommandGroup
from frkl.project_meta import AppEnvironment


try:
    import uvloop

    uvloop.install()
except Exception:
    pass

click.anyio_backend = "asyncio"

AppEnvironment.set_main_app("bring")


cli = BringCommandGroup()

if __name__ == "__main__":
    exit_code = cli(_anyio_backend="asyncio")  # pragma: no cover
    sys.exit(exit_code)
