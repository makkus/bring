# -*- coding: utf-8 -*-
import gzip
import json
import logging
import os
from typing import Optional

import asyncclick as click
from asyncclick.core import Argument, Option
from blessings import Terminal
from bring.bring import Bring
from bring.context import BringContextTing


log = logging.getLogger("bring")


class BringExportContextCommand(click.Command):
    def __init__(self, name: str, bring: Bring, terminal=None, **kwargs):

        self._bring: Bring = bring
        if terminal is None:
            terminal = Terminal()
        self._terminal = terminal

        params = [
            Argument(["context"], required=False, nargs=1),
            Option(["--output-file", "-o"], required=False),
        ]

        super().__init__(
            name=name, callback=self.export_context, params=params, **kwargs
        )

    @click.pass_context
    async def export_context(ctx, self, output_file, context: Optional[str]):

        click.echo()

        context_obj: BringContextTing = self._bring.get_context(
            context_name=context, raise_exception=True
        )  # type: ignore

        all_values = await context_obj.export_context()

        json_data = json.dumps(all_values, indent=2) + "\n"

        json_bytes = json_data.encode("utf-8")

        if output_file is None:
            _path = os.path.join(os.getcwd(), f"{context_obj.name}.bx")
        elif os.path.isdir(os.path.realpath(output_file)):
            _path = os.path.join(output_file, f"{context_obj.name}.bx")
        else:
            _path = output_file

        with gzip.GzipFile(_path, "w") as f:
            f.write(json_bytes)
