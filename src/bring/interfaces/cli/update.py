# -*- coding: utf-8 -*-
from typing import Optional, Union

import asyncclick as click
from blessings import Terminal
from bring.bring import Bring
from bring.context import BringContextTing


class BringUpdateCommand(click.Command):
    def __init__(
        self,
        name: str,
        bring: Bring,
        context: Union[BringContextTing, str] = None,
        terminal=None,
    ):

        self._bring: Bring = bring
        if terminal is None:
            terminal = Terminal()
        self._terminal = terminal
        if isinstance(context, str):
            _context = self._bring.get_context(context)
        else:
            _context = context
        self._context: Optional[BringContextTing] = _context

        super().__init__(name=name, callback=self.update)

    @click.pass_context
    async def update(ctx, self):

        if self._context is not None:
            click.echo()
            click.echo(f"Updating metadata for context '{self._context.name}'...")
            click.echo()
            await self._context.update()

        else:
            click.echo()
            click.echo("Updating metadata for all registered contexts...")
            click.echo()
            await self._bring.update()
