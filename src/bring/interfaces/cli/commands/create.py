# -*- coding: utf-8 -*-
import logging
import os

import asyncclick as click
from asyncclick import Argument
from bring.defaults import DEFAULT_PKG_EXTENSION
from bring.pkg_types import PkgType
from frkl.args.arg import RecordArg
from frkl.args.cli.click_commands import FrklBaseCommand
from frkl.args.hive import ArgHive
from frkl.common.cli.exceptions import handle_exc_async
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

        pkg_desc_file = Argument(("pkg_desc_file",), nargs=1)
        params = self._args_renderer.rendered_arg + [pkg_desc_file]
        # params = self._args_renderer.rendered_arg
        super().__init__(name=name, callback=self.create_pkg_desc, params=params)

    @click.pass_context
    @handle_exc_async
    async def create_pkg_desc(ctx, self, pkg_desc_file, **kwargs):

        pkg_desc_path = os.path.abspath(pkg_desc_file)
        pkg_desc_filename = os.path.basename(pkg_desc_path)

        if "." not in pkg_desc_filename:
            pkg_desc_filename = f"{pkg_desc_filename}.{DEFAULT_PKG_EXTENSION}"

        pkg_name, extension = pkg_desc_filename.split(".", maxsplit=1)

        arg_value = self._args_renderer.create_arg_value(kwargs)
        user_input = arg_value.processed_input

        str = await self._plugin.create_pkg_desc_string(
            pkg_name, self.name, **user_input
        )

        print(str)

        # source = desc.pop("source")
        #
        # pkg_metadata = await self._plugin.get_pkg_metadata(source_details=source)
        #
        # md = PkgExplanation(pkg_name="example_name", pkg_metadata=pkg_metadata, **desc)
        #
        # get_console().print(md)
