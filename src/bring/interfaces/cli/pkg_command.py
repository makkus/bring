# -*- coding: utf-8 -*-
import logging
from typing import Any, Dict, Optional

import arrow
import asyncclick as click
from asyncclick.core import Command, Option
from blessed import Terminal
from bring.pkg import PkgTing
from frtls.args.arg import RecordArg
from frtls.async_helpers import wrap_async_task
from frtls.formats.output_formats import serialize


log = logging.getLogger("bring")


class PkgInstallTingCommand(Command):
    def __init__(
        self,
        name: str,
        pkg: PkgTing,
        target: str,
        strategy: str,
        load_details: bool = False,
        terminal=None,
        **kwargs,
    ):

        self._pkg: PkgTing = pkg

        self._target = target
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


class PkgInfoTingCommand(Command):
    def __init__(
        self,
        name: str,
        pkg: PkgTing,
        load_details: bool = False,
        terminal: Optional[Terminal] = None,
        **kwargs,
    ):

        self._pkg: PkgTing = pkg

        if terminal is None:
            terminal = Terminal()

        self._terminal = terminal
        try:
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
            help = f"Display info for the '{self._pkg.name}' package."
            if desc:
                help = f"{help}\n\n{desc}"

            params = [
                Option(
                    ["--update", "-u"],
                    help="update package metadata",
                    is_flag=True,
                    required=False,
                ),
                Option(
                    ["--full", "-f"],
                    help="display full info",
                    is_flag=True,
                    required=False,
                ),
            ]

            kwargs["help"] = help
        except (Exception) as e:
            log.debug(f"Can't create PkgInstallTingCommand object: {e}", exc_info=True)
            raise e

        super().__init__(name=name, callback=self.info, params=params, **kwargs)

    @click.pass_context
    async def info(ctx, self, update: bool = False, full: bool = False):

        args: Dict[str, Any] = {"include_metadata": True}
        if update:
            args["retrieve_config"] = {"metadata_max_age": 0}

        info = await self._pkg.get_info(**args)

        metadata = info["metadata"]
        age = arrow.get(metadata["timestamp"])

        to_print = {}
        to_print["info"] = info["info"]
        to_print["labels"] = info["labels"]
        to_print["metadata snapshot"] = age.humanize()
        to_print["args"] = metadata["pkg_args"]
        to_print["aliases"] = metadata["aliases"]

        if full:
            to_print["version list"] = metadata["version_list"]

        click.echo()
        click.echo(serialize(to_print, format="yaml"))
