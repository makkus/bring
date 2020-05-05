# -*- coding: utf-8 -*-
from typing import Dict, Optional, Union

from asyncclick import Command
from bring.bring import Bring
from bring.plugins.cli import AbstractBringCommand, BringCliPlugin
from bring.plugins.templating.core import BringTemplate
from frtls.args.arg import Arg, RecordArg
from frtls.cli.terminal import create_terminal
from frtls.exceptions import FrklException
from tings.common.templating import TemplaTing


class TemplatePlugin(BringCliPlugin):

    _plugin_name = "template"

    async def create_command(self) -> Command:
        command = TemplatePluginCommand(
            name="template", bring=self.bring, terminal=self.terminal
        )
        return command


class TemplatePluginCommand(AbstractBringCommand):
    def __init__(self, name: str, bring: Bring, terminal=None, **kwargs):

        super().__init__(
            name=name,
            bring=bring,
            terminal=terminal,
            subcommand_metavar="PKG",
            **kwargs,
        )

    def get_group_options(self) -> Union[Arg, Dict]:

        return {
            # "templates_pkg": {
            #     "doc": "The package that contains the templates.",
            #     "type": "string",
            #     "default": "collections.templates",
            #     "required": False,
            # },
            # "pkg_vars": {
            #     "doc": "The vars to determine ther version of the templates package to use.",
            #     "type": "dict",
            #     "required": False
            # }
        }

    async def _list_commands(self, ctx):

        ctx.obj[f"list_{self.name}_commands"] = True
        return []

    async def _get_command(self, ctx, name):

        # params = dict(self._group_params)
        # templates_pkg = params["templates_pkg"]
        templates_pkg = "collections.templates"
        template_pkg_vars = {"version": "develop"}

        if not await self._bring.pkg_exists(templates_pkg):
            raise FrklException(
                msg=f"Can't process template '{templates_pkg}'",
                reason="Pkg does not exist.",
            )

        bring_template = BringTemplate(
            bring=self._bring,
            templates_pkg=templates_pkg,
            templates_pkg_vars=template_pkg_vars,
        )

        load_details = not ctx.obj.get(f"list_{self.name}_commands", False)
        args = None
        templa_ting = None
        if load_details:
            templa_ting = await bring_template.get_tempting(name)
            _args = await templa_ting.get_value("args")
            args = self._bring.arg_hive.create_record_arg(_args)

        plugin_command = TemplatePkgCommand(
            name=name,
            bring_template=bring_template,
            template_name=name,
            templa_ting=templa_ting,
            terminal=self._terminal,
            load_details=load_details,
            args=args,
        )

        return plugin_command


class TemplatePkgCommand(Command):
    def __init__(
        self,
        name: str,
        bring_template: BringTemplate,
        template_name: str,
        templa_ting: TemplaTing,
        load_details: bool = False,
        args: Optional[RecordArg] = None,
        terminal=None,
        **kwargs,
    ):

        self._plugin_name = name
        self._bring_template: BringTemplate = bring_template

        self._template_name: str = template_name

        if terminal is None:
            terminal = create_terminal()
        self._terminal = terminal

        self._templa_ting: Optional[TemplaTing] = templa_ting
        self._args = args
        if load_details:
            if self._args is None:
                raise Exception("args not set, this is a bug")
            kwargs["params"] = self._args.to_cli_options()

        super().__init__(name=name, callback=self.process, **kwargs)

    async def process(self, **kwargs):

        vars = self._args.from_cli_input(**kwargs, _remove_none_values=True)

        if self._templa_ting is None:
            raise Exception("'templating not set, this is a bug")

        result = await self._templa_ting.process_template(**vars)

        print(result)
