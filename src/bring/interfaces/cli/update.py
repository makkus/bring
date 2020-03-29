# -*- coding: utf-8 -*-
import asyncclick as click
from asyncclick import Argument
from blessed import Terminal
from bring.bring import Bring


class BringUpdateCommand(click.Command):
    def __init__(self, name: str, bring: Bring, terminal=None):

        self._bring: Bring = bring
        if terminal is None:
            terminal = Terminal()
        self._terminal = terminal

        params = [Argument(["context"], required=False, nargs=1)]

        super().__init__(name=name, callback=self.update, params=params)

    @click.pass_context
    async def update(ctx, self, context):

        if context is not None:
            click.echo()
            click.echo(f"Updating metadata for context '{context}'...")
            click.echo()
            await self._bring.update(context_names=[context])

        else:
            click.echo()
            click.echo("Updating metadata for all registered contexts...")
            click.echo()
            await self._bring.update()
