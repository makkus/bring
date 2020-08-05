# -*- coding: utf-8 -*-
import logging

import asyncclick as click
from bring.bring import Bring
from bring.pkg_types import PkgType
from frkl.args.arg import RecordArg
from frkl.args.cli.click_commands import FrklBaseCommand


log = logging.getLogger("bring")


class BringDevGroup(FrklBaseCommand):
    def __init__(
        self,
        bring: Bring,
        name: str = None,
        **kwargs
        # print_version_callback=None,
        # invoke_without_command=False,
    ):
        """Install"""

        # self.print_version_callback = print_version_callback
        self._bring: Bring = bring
        kwargs["help"] = """Commands to help development."""

        super(BringDevGroup, self).__init__(
            name=name,
            invoke_without_command=True,
            no_args_is_help=True,
            callback=None,
            chain=False,
            result_callback=None,
            add_help_option=False,
            subcommand_metavar="PROCESSOR",
            **kwargs,
        )

    async def _list_commands(self, ctx):

        return ["create-pkg"]

    async def _get_command(self, ctx, name):
        plugin_manager = self._bring.typistry.get_plugin_manager(PkgType)
        plugin: PkgType = plugin_manager.get_plugin("github_release")
        command = BringCreatePkgCommand(
            name="create-pkg", bring=self._bring, plugin=plugin
        )
        return command


class BringCreatePkgCommand(click.Command):
    def __init__(self, name: str, bring: Bring, plugin: PkgType, **kwargs):

        self._bring: Bring = bring
        self._plugin: PkgType = plugin

        args_dict = self._plugin.get_args()
        arg_obj: RecordArg = self._bring.arg_hive.create_record_arg(args_dict)

        self._args_renderer = arg_obj.create_arg_renderer(
            "cli", add_defaults=False, remove_required=True
        )
        params = self._args_renderer.rendered_arg

        super().__init__(name=name, callback=self.create_pkg, params=params, **kwargs)

    # @click.pass_context
    async def create_pkg(self, **kwargs):

        arg_value = self._args_renderer.create_arg_value(kwargs)
        user_input = arg_value.processed_input

        str = await self._plugin.create_pkg_desc_string(
            "example_name", "github_release", **user_input
        )
        print(str)

        # source = desc.pop("source")
        #
        # pkg_metadata = await self._plugin.get_pkg_metadata(source_details=source)
        #
        # md = PkgExplanation(pkg_name="example_name", pkg_metadata=pkg_metadata, **desc)
        #
        # get_console().print(md)
