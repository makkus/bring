# -*- coding: utf-8 -*-
import gzip
import json
import logging
import os
from typing import Optional

import asyncclick as click
from asyncclick.core import Argument, Option
from bring.bring import Bring
from frtls.cli.terminal import create_terminal


log = logging.getLogger("bring")


class BringExportIndexCommand(click.Command):
    def __init__(self, name: str, bring: Bring, terminal=None, **kwargs):

        self._bring: Bring = bring
        if terminal is None:
            terminal = create_terminal()
        self._terminal = terminal

        params = [
            Argument(["index"], required=False, nargs=1),
            Option(["--output-file", "-o"], required=False),
        ]

        super().__init__(name=name, callback=self.export_index, params=params, **kwargs)

    @click.pass_context
    async def export_index(ctx, self, output_file, index: Optional[str]):

        click.echo()

        if not index:
            index_obj = await self._bring.get_index()
        else:
            index_obj = await self._bring.get_index(index)

        all_values = await index_obj.export_index()

        json_data = json.dumps(all_values, indent=2) + "\n"

        json_bytes = json_data.encode("utf-8")

        if output_file is None:
            _path = os.path.join(os.getcwd(), f"{index_obj.name}.bx")
        elif os.path.isdir(os.path.realpath(output_file)):
            _path = os.path.join(output_file, f"{index_obj.name}.bx")
        else:
            _path = output_file

        with gzip.GzipFile(_path, "w") as f:
            f.write(json_bytes)
