# -*- coding: utf-8 -*-
import logging
from typing import Any

import asyncclick as click
from bring.bring import Bring
from bring.pkg_types import PkgType
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

        command = BringCreatePkgCommand(name="create-pkg", bring=self._bring)
        return command


class BringCreatePkgCommand(click.Command):
    def __init__(self, name: str, bring: Bring, **kwargs):

        print(name)

        self._bring: Bring = bring
        self._plugin_manager = self._bring.tingistry.get_plugin_manager(PkgType)
        super().__init__(name=name, callback=self.create_pkg, **kwargs)

    def get_plugin(self, plugin_name: str) -> Any:

        return self._plugin_manager.get_plugin(plugin_name=plugin_name)

    @click.pass_context
    async def create_pkg(ctx, self):

        print("XXXX")
        plugin: PkgType = self.get_plugin("github-release")

        regexes_to_try = [
            "https://github.com/.*/releases/download/v*(?P<version>.*)/.*-v*(?P=version)-(?P<arch>[^-]*)-(?P<os>[^.]*)\\..*$",
            "https://github.com/.*/releases/download/(?P<version>.*)/.*-(?P=version)-(?P<arch>[^-]*)-(?P<os>[^.]*)\\..*$",
        ]

        source_details = {"user_name": "cloudflare", "repo_name": "wrangler"}

        for r in regexes_to_try:
            source_details["url_regex"] = r
            md = await plugin.get_pkg_metadata(source_details)
            versions = md.versions
            if not versions:
                continue
            print(versions[0])
            matches = len(versions)
            print(f"Found {matches} matches")
