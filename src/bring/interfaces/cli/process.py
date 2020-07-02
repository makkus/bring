# -*- coding: utf-8 -*-
PROCESS_HELP = """Process one or a list of packages."""


# class BringProcessGroup(FrklBaseCommand):
#     def __init__(
#         self,
#         bring: Bring,
#         name: str = None,
#         **kwargs
#         # print_version_callback=None,
#         # invoke_without_command=False,
#     ):
#         """Install"""
#
#         # self.print_version_callback = print_version_callback
#         self._bring: Bring = bring
#         kwargs["help"] = PROCESS_HELP
#
#         super(BringProcessGroup, self).__init__(
#             name=name,
#             invoke_without_command=False,
#             no_args_is_help=True,
#             chain=False,
#             result_callback=None,
#             add_help_option=True,
#             arg_hive=bring.arg_hive,
#             subcommand_metavar="PROCESSOR",
#             **kwargs,
#         )
#
#     async def _list_commands(self, ctx):
#
#         pm = self._bring.tingistry.get_plugin_manager(PkgProcessor)
#         return pm.plugin_names
#
#     async def _get_command(self, ctx, name):
#
#         command = BringPkgProcessorGroup(bring=self._bring, name=name)
#         return command
#
#
# class BringPkgProcessorGroup(FrklBaseCommand):
#     def __init__(
#         self,
#         bring: Bring,
#         name: str = None,
#         **kwargs
#         # print_version_callback=None,
#         # invoke_without_command=False,
#     ):
#         """Install"""
#
#         # self.print_version_callback = print_version_callback
#         self._bring: Bring = bring
#         kwargs["help"] = PROCESS_HELP
#
#         super(BringPkgProcessorGroup, self).__init__(
#             name=name,
#             invoke_without_command=True,
#             no_args_is_help=True,
#             callback=self.install_info,
#             chain=False,
#             result_callback=None,
#             add_help_option=False,
#             arg_hive=bring.arg_hive,
#             subcommand_metavar="PROCESSOR",
#             **kwargs,
#         )
#
#     @click.pass_context
#     async def install_info(ctx, self, **kwargs):
#
#         if ctx.invoked_subcommand is not None:
#             return
#
#         help = self.get_help(ctx)
#         click.echo(help)
#
#     def format_commands(self, ctx, formatter):
#         """Extra format methods for multi methods that adds all the commands
#         after the options.
#         """
#
#         wrap_async_task(print_pkg_list_help, bring=self._bring, formatter=formatter)
#
#     def get_group_options(self) -> Union[Arg, Dict]:
#
#         # target = wrap_async_task(self.get_bring_target)
#         # target_args = target.requires()
#
#         default_args = {
#             "explain": {
#                 "doc": "Don't perform installation, only explain steps.",
#                 "type": "boolean",
#                 "default": False,
#                 "required": False,
#                 "cli": {"is_flag": True},
#             },
#             "help": {
#                 "doc": "Show this message and exit.",
#                 "type": "boolean",
#                 "default": False,
#                 "required": False,
#                 "cli": {"is_flag": True},
#             },
#         }
#
#         return default_args
#
#     async def _list_commands(self, ctx):
#
#         return []
#
#     async def _get_command(self, ctx, name):
#
#         explain = self._group_params.get("explain")
#         load_details = not ctx.obj.get("list_install_commands", False)
#
#         if not load_details:
#             return None
#
#         command = PkgProcessorCommand(
#             name=self.name,
#             bring=self._bring,
#             pkg_name=name,
#             explain=explain,
#             load_details=load_details,
#         )
#
#         return command


# class PkgProcessorCommand(Command):
#     def __init__(
#         self,
#         name: str,
#         bring: Bring,
#         pkg_name: str,
#         explain: bool,
#         load_details: bool,
#         **kwargs,
#     ):
#
#         self._bring: Bring = bring
#         self._pkg_name: str = pkg_name
#         self._pkg: Optional[PkgTing] = None
#         self._processor_name = name
#         self._processor: Optional[PkgProcessor] = None
#
#         self._explain: bool = explain
#
#         try:
#             if load_details:
#
#                 args = wrap_async_task(self.get_args)
#                 kwargs["params"] = args.to_cli_options()
#
#         except (Exception) as e:
#             log.debug(f"Can't create PkgInstallTingCommand object: {e}", exc_info=True)
#             raise e
#         super().__init__(name=name, callback=self.process, **kwargs)
#
#     async def get_pkg(self):
#
#         if self._pkg is None:
#             self._pkg = await self._bring.get_pkg(self._pkg_name, raise_exception=True)
#         return self._pkg
#
#     async def get_processor(self):
#
#         if self._processor is None:
#             pkg = await self.get_pkg()
#             self._processor = self._bring.create_processor(self._processor_name)
#             self._processor.add_constants(
#                 _constants_name="pkg", pkg_name=pkg.name, pkg_index=pkg.bring_index.id
#             )
#         return self._processor
#
#     async def get_args(self) -> RecordArg:
#
#         proc = await self.get_processor()
#         return await proc.get_user_input_args()
#
#     async def process(self):
#
#         # args = await self.get_args()
#         # vals = args.from_cli_input(**kwargs)
#         # print(vals)
#
#         proc = await self.get_processor()
#         proc.set_user_input(**vals)
#         result = await proc.process()
#         # result = await self._target.apply(proc)
#         print(result)
