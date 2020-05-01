# -*- coding: utf-8 -*-
from typing import Any, Dict, Optional

import arrow
import asyncclick as click
from asyncclick import Command, Option
from blessed import Terminal
from bring.bring import Bring
from bring.context import BringContextTing
from bring.defaults import BRING_NO_METADATA_TIMESTAMP_MARKER
from bring.interfaces.cli.utils import (
    log,
    print_context_list_for_help,
    print_pkg_list_help,
)
from bring.pkg import PkgTing
from frtls.async_helpers import wrap_async_task
from frtls.cli.group import FrklBaseCommand
from frtls.cli.terminal import create_terminal
from frtls.formats.output_formats import serialize


INFO_HELP = """Display information about a context or package.

You can either provide a context or package name. If the specified value matches a context name, context information will
be displayed. Otherwise all contexts will be looked up to find a matching package name. If you want to display information for a package from the default context, you may omit the 'context' part of the package name.
"""


class BringInfoPkgsGroup(FrklBaseCommand):
    def __init__(self, bring: Bring, name=None, **kwargs):

        self._bring: Bring = bring

        kwargs["help"] = INFO_HELP

        super(BringInfoPkgsGroup, self).__init__(
            name=name,
            invoke_without_command=False,
            no_args_is_help=True,
            chain=False,
            result_callback=None,
            # callback=self.all_info,
            arg_hive=bring.arg_hive,
            subcommand_metavar="CONTEXT_OR_PKG_NAME",
            **kwargs,
        )

    def format_commands(self, ctx, formatter):
        """Extra format methods for multi methods that adds all the commands
        after the options.
        """

        wrap_async_task(
            print_context_list_for_help, bring=self._bring, formatter=formatter
        )
        wrap_async_task(print_pkg_list_help, bring=self._bring, formatter=formatter)

    async def _list_commands(self, ctx):

        ctx.obj["list_info_commands"] = True
        return []

    async def _get_command(self, ctx, name):

        # context_name = self._group_params.get("context", None)

        # _ctx_name = await ensure_context(self._bring, name=context_name)
        # await self._bring.get_context(_ctx_name)

        load_details = not ctx.obj.get("list_info_commands", False)

        if not load_details:
            return None

        context = await self._bring.get_context(
            context_name=name, raise_exception=False
        )
        if context is not None:
            command = ContextInfoTingCommand(
                name=name,
                context=context,
                load_details=load_details,
                terminal=self._terminal,
            )
            return command

        pkg = await self._bring.get_pkg(name=name, raise_exception=False)
        if pkg is None:
            return None

        command = PkgInfoTingCommand(
            name=name, pkg=pkg, load_details=load_details, terminal=self._terminal
        )
        return command


class ContextInfoTingCommand(Command):
    def __init__(
        self,
        name: str,
        context: BringContextTing,
        load_details: bool = False,
        terminal: Optional[Terminal] = None,
        **kwargs,
    ):

        self._context: BringContextTing = context

        if terminal is None:
            terminal = create_terminal()

        self._terminal = terminal
        try:
            val_names = ["config", "info"]
            self._data = wrap_async_task(
                self._context.get_values, *val_names, _raise_exception=True
            )
            slug = self._data["info"].get("slug", "n/a")
            if slug.endswith("."):
                slug = slug[0:-1]
            short_help = slug

            kwargs["short_help"] = short_help
            desc = self._data["info"].get("desc", None)
            help = f"Display info for the '{self._context.name}' package."
            if desc:
                help = f"{help}\n\n{desc}"

            params = [
                Option(
                    ["--update", "-u"],
                    help="update context metadata",
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

        # args: Dict[str, Any] = {"include_metadata": True}
        # if update:
        #     args["retrieve_config"] = {"metadata_max_age": 0}
        #
        # info = await self._pkg.get_info(**args)
        #
        # metadata = info["metadata"]
        # age = arrow.get(metadata["timestamp"])

        if not full:
            to_print = self._data
        else:
            metadata_timestamp = await self._context.get_metadata_timestamp(
                return_format="human"
            )

            if metadata_timestamp == BRING_NO_METADATA_TIMESTAMP_MARKER:
                metadata_timestamp = "unknown"
            pkgs = await self._context.get_all_pkg_values("info")
            pkg_slug_map = {}
            for pkg_name in sorted(pkgs.keys()):
                pkg_slug_map[pkg_name] = (
                    pkgs[pkg_name]
                    .get("info", {})
                    .get("slug", "no description available")
                )

            to_print = {
                "metadata snapshot": metadata_timestamp,
                "config": self._data["config"],
                "pkgs": pkg_slug_map,
            }
        # to_print["info"] = info["info"]
        # to_print["labels"] = info["labels"]
        # to_print["metadata snapshot"] = age.humanize()
        # to_print["args"] = metadata["pkg_args"]
        # to_print["aliases"] = metadata["aliases"]
        #
        # if full:
        #     to_print["version list"] = metadata["version_list"]
        #
        # click.echo()
        click.echo(serialize(to_print, format="yaml", ignore_aliases=True))


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
            terminal = create_terminal()

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
