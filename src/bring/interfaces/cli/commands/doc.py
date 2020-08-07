# -*- coding: utf-8 -*-
import logging
from typing import Any, Optional, Type

import asyncclick as click
from bring.bring import Bring
from bring.config.bring_config import BringConfig
from bring.interfaces.cli import bring_code_theme, bring_style, console
from bring.mogrify import Mogrifier
from bring.pkg_types import PkgType, get_pkg_type_plugin_factory
from bring.utils.doc import create_pkg_type_markdown_string
from freckles.core.freckles import Freckles
from frkl.args.cli.click_commands import FrklBaseCommand
from frkl.args.hive import ArgHive
from frkl.args.renderers.rich import to_rich_table
from frkl.types.plugins import PluginFactory, PluginManager
from frkl.types.typistry import Typistry
from rich import box
from rich.console import RenderGroup
from rich.markdown import Markdown
from rich.panel import Panel
from tings.tingistry import Tingistry


log = logging.getLogger("bring")

PLUGIN_HELP = """documentation for application components"""


class BringDocGroup(FrklBaseCommand):
    def __init__(self, freckles: Freckles, name: str = "doc", **kwargs):
        """Install"""

        # self.print_version_callback = print_version_callback
        self._freckles: Freckles = freckles
        self._tingistry: Tingistry = freckles.tingistry
        self._typistry: Typistry = self._tingistry.typistry
        kwargs["help"] = PLUGIN_HELP

        self._bring: Optional[Bring] = None

        # self._plugin_managers: Dict[str, TypistryPluginManager] = None

        super(BringDocGroup, self).__init__(name=name, **kwargs)

    # def plugin_managers(self) -> Mapping[str, TypistryPluginManager]:
    #
    #     if self._plugin_managers is not None:
    #         return self._plugin_managers
    #
    #     self._plugin_managers = {}
    #     for pl_cls in self._plugin_classes:
    #
    #         pm = self._typistry.get_plugin_manager(pl_cls)
    #         self._plugin_managers[pm.manager_name] = pm
    #
    #     return self._plugin_managers

    @property
    def bring(self) -> Bring:

        if self._bring is None:
            bring_config = BringConfig(freckles=self._freckles)
            self._bring = bring_config.get_bring()
        return self._bring

    async def _list_commands(self, ctx):

        return ["pkg-type", "mogrifier"]

    async def _get_command(self, ctx, name):

        command = None
        if name == "pkg-type":
            command = PkgTypePluginGroup(
                freckles=self._freckles, arg_hive=self.arg_hive
            )

        elif name == "mogrifier":
            command = MogrifyPluginGroup(
                freckles=self._freckles, arg_hive=self.arg_hive
            )

        return command


class BringPluginGroup(FrklBaseCommand):
    def __init__(
        self, name: str, freckles: Freckles, plugin_class: Type, arg_hive: ArgHive
    ):

        self._freckles: Freckles = freckles
        self._tingistry: Tingistry = self._freckles.tingistry

        self._plugin_class: Type = plugin_class
        self._plugin_manager: Optional[PluginManager] = None

        self._bring: Optional[Bring] = None
        super(BringPluginGroup, self).__init__(
            name=name, arg_hive=arg_hive, subcommand_metavar="PLUGIN",
        )

    def get_plugin_manager(self) -> PluginManager:

        if self._plugin_manager is None:
            self._plugin_manager = self.arg_hive.typistry.get_plugin_manager(
                self._plugin_class
            )
        return self._plugin_manager

    @property
    def bring(self) -> Bring:

        if self._bring is None:
            bring_config = BringConfig(freckles=self._freckles, name="doc")
            self._bring = bring_config.get_bring()
        return self._bring

    def get_plugin_doc(self, plugin_name: str):

        return self.get_plugin_manager().get_plugin_doc(plugin_name=plugin_name)

    def get_plugin(self, plugin_name: str) -> Any:

        return self.get_plugin_manager().get_plugin(plugin_name=plugin_name)

    async def _list_commands(self, ctx):

        return sorted(self.get_plugin_manager().plugin_names)


class PkgTypePluginGroup(BringPluginGroup):
    def __init__(self, freckles: Freckles, arg_hive: ArgHive):

        self._plugin_factory: Optional[PluginFactory] = None
        super().__init__(
            name="pkg-type", freckles=freckles, plugin_class=PkgType, arg_hive=arg_hive
        )

    def get_plugin_factory(self) -> PluginFactory:

        if self._plugin_factory is None:
            self._plugin_factory = get_pkg_type_plugin_factory(self.arg_hive)
        return self._plugin_factory

    async def _get_command(self, ctx, name):

        if name not in self.get_plugin_manager().plugin_names:
            return None

        @click.command()
        @click.pass_context
        async def plugin_command(ctx):

            all = []

            doc = self.get_plugin_doc(name)
            doc.extract_metadata("examples")

            desc_string = f"## Package type: **{name}**\n"
            if doc.get_short_help(default=None):
                desc_string += doc.get_short_help() + "\n\n"

            desc_string += f"\n## Arguments\n\nThis is the list of arguments that can be used to describe a package of the *{name}* type:\n"
            desc = Markdown(
                desc_string,
                style=bring_style,
                code_theme=bring_code_theme,
                justify="left",
            )
            all.append(desc)

            plugin = self.get_plugin_factory().get_singleton(name)

            args = plugin.get_args()
            record_arg = self.arg_hive.create_record_arg(childs=args)
            arg_table = to_rich_table(record_arg)
            all.append(arg_table)

            desc_string = await create_pkg_type_markdown_string(
                bring=self.bring, plugin_doc=doc
            )

            desc = Markdown(
                desc_string,
                style=bring_style,
                code_theme=bring_code_theme,
                justify="left",
            )
            all.append(desc)

            group = RenderGroup(*all)
            console.print(Panel(Panel(group, box=box.SIMPLE)))

        return plugin_command


class MogrifyPluginGroup(BringPluginGroup):
    def __init__(self, freckles: Freckles, arg_hive: ArgHive):

        super().__init__(
            name="mogrifier",
            freckles=freckles,
            plugin_class=Mogrifier,
            arg_hive=arg_hive,
        )

    async def _get_command(self, ctx, name):
        @click.command()
        @click.pass_context
        async def plugin_command(ctx):

            all = []

            doc = self.get_plugin_doc(name)
            doc.extract_metadata("examples")

            desc_string = f"## Mogrifier: **{name}**\n"
            if doc.get_short_help(default=None):
                desc_string += doc.get_short_help() + "\n\n"

            desc_string += f"\n## Input Arguments\n\nThis is the list of arguments the *{name}* mogrifier accepts as input:\n"
            desc = Markdown(
                desc_string,
                style=bring_style,
                code_theme=bring_code_theme,
                justify="left",
            )
            all.append(desc)

            plugin = self.get_plugin(name)
            if hasattr(plugin, "_requires"):
                args = plugin._requires
            else:
                args = plugin.requires(None)
            record_arg = self.arg_hive.create_record_arg(childs=args)
            arg_table = to_rich_table(record_arg)
            all.append(arg_table)

            desc_string = f"\n## Output Arguments\n\nThis is the list of arguments the *{name}* mogrifier provides as output:\n"
            desc = Markdown(
                desc_string,
                style=bring_style,
                code_theme=bring_code_theme,
                justify="left",
            )
            all.append(desc)

            if hasattr(plugin, "_provides"):
                args = plugin._provides
            else:
                args = plugin.provides(None)
            record_arg = self.arg_hive.create_record_arg(childs=args)
            arg_table = to_rich_table(record_arg)
            all.append(arg_table)

            desc_string = await create_pkg_type_markdown_string(
                bring=self.bring, plugin_doc=doc
            )

            desc = Markdown(
                desc_string,
                style=bring_style,
                code_theme=bring_code_theme,
                justify="left",
            )
            all.append(desc)

            group = RenderGroup(*all)
            console.print(Panel(Panel(group, box=box.SIMPLE)))

        return plugin_command
