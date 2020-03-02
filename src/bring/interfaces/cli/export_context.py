# -*- coding: utf-8 -*-
import json
import logging
import os
from typing import Optional

import asyncclick as click
from asyncclick.core import Argument
from blessings import Terminal
from bring.bring import Bring
from bring.context import BringContextTing


log = logging.getLogger("bring")


class BringExportContextCommand(click.Command):
    def __init__(
        self,
        name: str,
        bring: Bring,
        context: Optional[BringContextTing] = None,
        terminal=None,
        **kwargs,
    ):

        self._bring: Bring = bring
        if terminal is None:
            terminal = Terminal()
        self._terminal = terminal

        self._context: Optional[BringContextTing] = context

        params = [Argument(["path"], required=False, nargs=1)]

        super().__init__(
            name=name, callback=self.export_context, params=params, **kwargs
        )

    @click.pass_context
    async def export_context(ctx, self, path):

        if self._context is None:
            click.echo()
            print("NO CONTEXT")
            click.echo()

        else:
            click.echo()
            print("CONTEXT: {}".format(self._context))

            # pkg = await self._context.get_pkg("fd")
            # all_values = await pkg.get_values("metadata")
            # print(vals)

            all_values = await self._context_context.export()

            json_data = json.dumps(all_values, indent=2)

            if path is None:
                path = os.path.join(os.getcwd(), f"{self._context.name}.json")

            with open(path, "w") as f:
                f.write(json_data)
