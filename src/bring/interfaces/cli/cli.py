# -*- coding: utf-8 -*-

import sys

import asyncclick as click
from bring.interfaces.cli.command_group import BringCommandGroup


try:
    import uvloop

    uvloop.install()
except Exception:
    pass

click.anyio_backend = "asyncio"


cli = BringCommandGroup()

if __name__ == "__main__":
    sys.exit(cli(_anyio_backend="asyncio"))  # pragma: no cover
