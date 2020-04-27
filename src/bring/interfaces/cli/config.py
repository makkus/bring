# -*- coding: utf-8 -*-
import logging
from typing import Iterable, Optional

import asyncclick as click
from bring.config import BringConfig
from frtls.cli.exceptions import handle_exc_async
from frtls.cli.group import FrklBaseCommand
from frtls.formats.output_formats import create_multi_column_table, serialize
from tings.tingistry import Tingistries, Tingistry


CONFIG_HELP = """Configuration-related utility commands"""

log = logging.getLogger("bring")


class BringConfigGroup(FrklBaseCommand):
    def __init__(self, config_list: Iterable[str], name: str = "config", **kwargs):

        self._config_list: Iterable[str] = config_list
        self._tingistry_obj: Optional[Tingistry] = None
        self._bring_config: Optional[BringConfig] = None

        kwargs["help"] = CONFIG_HELP

        super(BringConfigGroup, self).__init__(
            name=name,
            invoke_without_command=True,
            no_args_is_help=False,
            callback=self.show,
            result_callback=None,
            **kwargs,
        )

    def get_config(self) -> BringConfig:

        if self._bring_config is None:
            self._tingistry_obj = Tingistries.create("bring")
            self._bring_config = BringConfig(
                tingistry=self._tingistry_obj
            )  # type: ignore
        return self._bring_config

    # def format_commands(self, ctx, formatter):
    #     """Extra format methods for multi methods that adds all the commands
    #     after the options.
    #     """
    #
    #     wrap_async_task(
    #         print_config_list_for_help, bring_config=self._bring_config, formatter=formatter
    #     )

    @click.pass_context
    async def show(ctx, self):

        if ctx.invoked_subcommand is not None:
            return

        self.get_config().config_input = self._config_list
        c = await self.get_config().get_config_dict()

        click.echo(serialize(c, format="yaml"))

    async def _list_commands(self, ctx):

        ctx.obj["list_info_commands"] = True
        return ["profile"]

    async def _get_command(self, ctx, name):

        command = None

        # if name == "show":
        #     @click.command()
        #     @click.pass_context
        #     @handle_exc_async
        #     async def show(ctx):
        #         """show the current configuration"""
        #
        #
        #
        #     command = show

        if name == "profile":

            @click.command()
            @click.argument("profile_name", nargs=1, required=False)
            @click.pass_context
            @handle_exc_async
            async def list(ctx, profile_name):

                profiles = await self.get_config().get_config_profiles()

                if profile_name is None:

                    profile_list = []
                    for profile_name, profile in sorted(profiles.items()):
                        info = await profile.get_value("info")
                        slug = info.get("slug", "no description available")
                        profile_list.append([profile_name, slug])

                    table = create_multi_column_table(
                        profile_list,
                        headers=["profile", "description"],
                        terminal=self._terminal,
                    )
                    click.echo()
                    click.echo(table)
                    return

                profile = profiles.get(profile_name, None)
                if profile is None:
                    click.echo()
                    click.echo(f"No profile '{profile_name}' available.")
                    return

                values = await profile.get_values()
                click.echo(serialize(values, format="yaml"))

            return list

        return command


# @click.group()
# @click.pass_context
# def config(ctx):
#     """Helper tasks for development.
#
#     """
#
#     pass
#
#
# @config.command()
# @click.pass_context
# @handle_exc_async
# async def list(ctx):
#     """List all available config profiles."""
#
#     bring: Bring = ctx.obj["bring"]
#
#     profiles = await bring.config.get_all_context_configs()
#
#     print(profiles)
