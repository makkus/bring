# -*- coding: utf-8 -*-
import asyncclick as click
from asyncclick import Argument
from bring.bring import Bring


class BringUpdateCommand(click.Command):
    def __init__(self, name: str, bring: Bring):

        self._bring: Bring = bring

        params = [Argument(["index"], required=False, nargs=1)]

        super().__init__(name=name, callback=self.update, params=params)

    @click.pass_context
    async def update(ctx, self, index):

        if index is not None:
            click.echo()
            click.echo(f"Updating metadata for index '{index}'...")
            click.echo()
            await self._bring.update(index_names=[index])

        else:
            click.echo()
            click.echo("Updating metadata for all registered indexes...")
            click.echo()
            await self._bring.update()
