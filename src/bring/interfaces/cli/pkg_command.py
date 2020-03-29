# -*- coding: utf-8 -*-
import logging

import asyncclick as click
from asyncclick.core import Command
from blessed import Terminal
from bring.pkg import PkgTing
from frtls.args.arg import RecordArg
from frtls.async_helpers import wrap_async_task


log = logging.getLogger("bring")


class PkgInstallTingCommand(Command):
    def __init__(
        self,
        name: str,
        pkg: PkgTing,
        target: str,
        context: str,
        strategy: str,
        load_details: bool = False,
        terminal=None,
        **kwargs,
    ):

        self._pkg: PkgTing = pkg

        self._target = target
        self._context = context
        self._strategy = strategy

        if terminal is None:
            terminal = Terminal()
        self._terminal = terminal

        try:
            if load_details:
                val_names = ["info", "args"]
            else:
                val_names = ["info"]
            vals = wrap_async_task(
                self._pkg.get_values, *val_names, _raise_exception=True
            )
            info = vals["info"]
            slug = info.get("slug", "n/a")
            if slug.endswith("."):
                slug = slug[0:-1]
            short_help = f"{slug} (from: {self._pkg.bring_context.name})"

            kwargs["short_help"] = short_help
            desc = info.get("desc", None)
            help = f"Install the '{self._pkg.name}' package."
            if desc:
                help = f"{help}\n\n{desc}"

            if load_details:
                args: RecordArg = vals["args"]
                params = args.to_cli_options()
                kwargs["params"] = params

            kwargs["help"] = help
        except (Exception) as e:
            log.debug(f"Can't create PkgInstallTingCommand object: {e}", exc_info=True)
            raise e

        super().__init__(name=name, callback=self.install, **kwargs)

    @click.pass_context
    async def install(ctx, self, **kwargs):

        path = await self._pkg.create_version_folder(vars=kwargs, target=self._target)
        print(path)
