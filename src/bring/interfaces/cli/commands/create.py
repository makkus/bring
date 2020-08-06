# -*- coding: utf-8 -*-
import logging
import os
import sys
from typing import Optional

import asyncclick as click
from anyio import aopen
from asyncclick import Argument, Option
from bring.defaults import DEFAULT_PKG_EXTENSION
from bring.pkg_types import PkgType
from frkl.args.arg import RecordArg
from frkl.args.cli.click_commands import FrklBaseCommand
from frkl.args.hive import ArgHive
from frkl.common.cli import get_console
from frkl.common.cli.exceptions import handle_exc_async
from frkl.common.filesystem import ensure_folder
from frkl.types.plugins import PluginManager


log = logging.getLogger("bring")


class BringCreateGroup(FrklBaseCommand):
    def __init__(self, name: str = None, **kwargs):
        """Command to create bring-related elements."""

        kwargs["short_help"] = """create bring-related elementes"""

        super(BringCreateGroup, self).__init__(
            name=name,
            invoke_without_command=True,
            no_args_is_help=True,
            callback=None,
            chain=False,
            result_callback=None,
            add_help_option=False,
            subcommand_metavar="TYPE",
            **kwargs,
        )

    async def _list_commands(self, ctx):

        return ["pkg-desc"]

    async def _get_command(self, ctx, name):

        command = None
        if name == "pkg-desc":
            command = BringCreatePkgDescGroup(name="pkg-desc", arg_hive=self.arg_hive)
        return command


class BringCreatePkgDescGroup(FrklBaseCommand):
    def __init__(self, name: str = None, **kwargs):
        """Command to create bring-related elements."""

        kwargs["short_help"] = """create a package description"""

        super(BringCreatePkgDescGroup, self).__init__(
            name=name,
            invoke_without_command=True,
            no_args_is_help=True,
            callback=None,
            chain=False,
            result_callback=None,
            add_help_option=False,
            subcommand_metavar="PKG_TYPE",
            **kwargs,
        )

        self._plugin_manager: PluginManager = self.arg_hive.typistry.get_plugin_manager(
            PkgType, plugin_config={"arg_hive": self.arg_hive}
        )

    async def _list_commands(self, ctx):

        return self._plugin_manager.plugin_names

    async def _get_command(self, ctx, name):
        plugin: PkgType = self._plugin_manager.get_plugin(name, raise_exception=True)

        command = BringCreatePkgDescCommand(
            name=name, plugin=plugin, arg_hive=self.arg_hive
        )
        return command


class BringCreatePkgDescCommand(click.Command):
    def __init__(self, name: str, plugin: PkgType, **kwargs):

        self._plugin: PkgType = plugin

        args_dict = self._plugin.get_args()
        arg_hive: ArgHive = kwargs["arg_hive"]
        arg_obj: RecordArg = arg_hive.create_record_arg(args_dict)

        self._args_renderer = arg_obj.create_arg_renderer(
            "cli", add_defaults=False, remove_required=True
        )

        pkg_desc_file = Argument(("pkg_name_or_path",), nargs=1, required=False)
        force = Option(
            ["--force", "-f"],
            help="overwrite existing package description",
            is_flag=True,
            required=False,
        )
        params = self._args_renderer.rendered_arg + [pkg_desc_file, force]
        # params = self._args_renderer.rendered_arg
        super().__init__(name=name, callback=self.create_pkg_desc, params=params)

    @click.pass_context
    @handle_exc_async
    async def create_pkg_desc(ctx, self, pkg_name_or_path, force, **kwargs):

        pkg_desc_path: Optional[str] = None

        if pkg_name_or_path is not None:

            basename = os.path.basename(pkg_name_or_path)
            if "." not in basename:
                pkg_name_or_path = f"{pkg_name_or_path}{DEFAULT_PKG_EXTENSION}"

            pkg_desc_path = os.path.abspath(pkg_name_or_path)

        arg_value = self._args_renderer.create_arg_value(kwargs)
        user_input = arg_value.processed_input

        pkg_desc_str = await self._plugin.create_pkg_desc_string(
            self.name, **user_input
        )

        if not pkg_desc_path:
            get_console().print(pkg_desc_str)
        else:
            get_console().line()
            if os.path.exists(pkg_desc_path) and not force:
                get_console().print(
                    f"Not writing package description to: {pkg_desc_path}"
                )
                get_console().print(
                    "  -> file already exists and 'force' not specified"
                )
                sys.exit(1)

            ensure_folder(os.path.dirname(pkg_desc_path))
            async with await aopen(pkg_desc_path, "w") as f:
                await f.write(pkg_desc_str)

            get_console().print(f"Saved package descrition to: {pkg_desc_path}")

        # source = desc.pop("source")
        #
        # pkg_metadata = await self._plugin.get_pkg_metadata(source_details=source)
        #
        # md = PkgExplanation(pkg_name="example_name", pkg_metadata=pkg_metadata, **desc)
        #
        # get_console().print(md)
