# -*- coding: utf-8 -*-
import logging
import os
from typing import Iterable, Optional

import asyncclick as click
from asyncclick import Command, Option
from bring.bring import Bring
from bring.config.bring_config import BringConfig
from bring.defaults import DEFAULT_PKG_EXTENSION
from bring.doc.index import IndexExplanation
from bring.doc.pkg import PkgExplanation
from bring.interfaces.cli import console
from bring.interfaces.cli.config import BringContextGroup
from bring.pkg_index.index import BringIndexTing
from bring.pkg_types import PkgType
from frkl.args.cli.click_commands import FrklBaseCommand
from frkl.args.hive import ArgHive
from frkl.common.cli.exceptions import handle_exc_async
from frkl.common.formats.auto import AutoInput
from frkl.explain.explanations.doc import InfoListExplanation
from frkl.targets.local_folder import TrackingLocalFolder


log = logging.getLogger("bring")

INFO_HELP = """Display information about a config context, an index, a package or a target.
"""


class BringInfoPkgsGroup(FrklBaseCommand):
    def __init__(
        self,
        bring_config: BringConfig,
        config_list: Iterable[str],
        name: str,
        arg_hive: ArgHive,
        **kwargs,
    ):

        self._bring_config: BringConfig = bring_config
        self._bring: Optional[Bring] = None
        self._config_list: Iterable[str] = config_list

        kwargs["help"] = INFO_HELP

        super(BringInfoPkgsGroup, self).__init__(
            name=name,
            invoke_without_command=False,
            no_args_is_help=True,
            chain=False,
            result_callback=None,
            # callback=self.all_info,
            arg_hive=arg_hive,
            subcommand_metavar="CONTEXT_OR_PKG_NAME",
            **kwargs,
        )

    async def get_bring(self):

        if self._bring is not None:
            return self._bring

        self._bring = self._bring_config.get_bring()
        self._bring.config.set_config(*self._config_list)
        await self._bring.add_all_config_indexes()

        return self._bring

    async def _list_commands(self, ctx):

        ctx.obj["list_info_commands"] = True
        return ["context", "index", "package", "target"]

    async def _get_command(self, ctx, name):

        # index_name = self._group_params.get("index", None)

        # _ctx_name = await ensure_index(self._bring, name=index_name)
        # await self._bring.get_index(_ctx_name)

        # load_details = not ctx.obj.get("list_info_commands", False)
        #
        # if not load_details:
        #     return None

        if name == "context":

            command = BringContextGroup(bring_config=self._bring_config, name="context")
            return command

        if name == "target":

            @click.command(short_help="show details about a target")
            @click.argument("path", nargs=1, required=False)
            @click.pass_context
            async def command(ctx, path):
                """"""
                if path is None:
                    path = os.path.abspath("..").split(os.path.sep)[0] + os.path.sep
                target = TrackingLocalFolder(path=path)

                console.print(target.explain())

                # target = LocalFolderTarget(bring=bring, path=path)
                # console.line()
                # console.print(target)
                # print(await tf.get_managed_files())

            return command

        elif name in ["index", "idx", "indexes"]:

            @click.command(short_help="show details about an index")
            @click.argument("indexes", nargs=-1, required=False, metavar="INDEX")
            @click.option(
                "--update",
                "-u",
                help="update index before retrieving info",
                is_flag=True,
            )
            # @click.option(
            #     "--full", "-f", help="display extended information", is_flag=True
            # )
            # @click.option(
            #     "--packages", "-p", help="display packages of this index", is_flag=True
            # )
            @click.pass_context
            async def command(ctx, indexes, update):

                full = True
                bring = await self.get_bring()
                if len(indexes) == 1:

                    console.line()
                    idx = await bring.get_index(index_name=indexes[0])

                    display = IndexExplanation(
                        name=indexes[0], data=idx, update=update, full_info=full
                    )
                    console.print(display)
                    return

                if not indexes:
                    indexes = bring.index_ids
                    full = False

                info_items = []
                for index in indexes:
                    idx = await bring.get_index(index_name=index)
                    display = IndexExplanation(
                        name=index, data=idx, update=update, full_info=full
                    )
                    info_items.append(display)

                expl = InfoListExplanation(*info_items, full_info=full)

                console.print(expl)

            return command

        elif name in ["package", "pkg"]:

            @click.command(short_help="show details about a package and its arguments")
            @click.argument("package", nargs=1, required=True)
            # @click.option(
            #     "--update",
            #     "-u",
            #     help="update index before retrieving info",
            #     is_flag=True,
            # )
            # @click.option(
            #     "--args",
            #     "-a",
            #     help="display full information on package args",
            #     is_flag=True,
            # )
            @click.pass_context
            @handle_exc_async
            async def command(ctx, package):

                if (
                    package.endswith(DEFAULT_PKG_EXTENSION)
                    or package.endswith(".yaml")
                    or package.endswith(".yml")
                    or package.endswith(".json")
                ):

                    package = os.path.abspath(package)
                    ai = AutoInput(package)
                    desc = await ai.get_content_async()
                    source = desc.pop("source")

                    pkg_type = source["type"]
                    plugin_manager = self.arg_hive.typistry.get_plugin_manager(
                        PkgType, plugin_config={"arg_hive": self.arg_hive}
                    )
                    plugin: PkgType = plugin_manager.get_plugin(pkg_type)

                    pkg_metadata = await plugin.get_pkg_metadata(source_details=source)

                    md = PkgExplanation(
                        pkg_name=os.path.basename(package),
                        pkg_metadata=pkg_metadata,
                        **desc,
                    )

                    console.print(md)

                else:
                    bring = await self.get_bring()
                    console.line()
                    pkg = await bring.get_pkg(name=package, raise_exception=True)

                    full_name = await self._bring.get_full_package_name(package)

                    vals = await pkg.get_values()

                    pkg_info: PkgExplanation = PkgExplanation(
                        pkg_name=full_name,
                        pkg_metadata=vals["metadata"],
                        info=vals["info"],
                        tags=vals["tags"],
                        labels=vals["labels"],
                    )
                    console.print(pkg_info)

            return command

        return None


class IndexInfoTingCommand(Command):
    def __init__(
        self, name: str, index: BringIndexTing, load_details: bool = False, **kwargs
    ):

        self._index: BringIndexTing = index
        self._index_info: IndexExplanation = IndexExplanation(
            name=name, data=self._index
        )
        try:

            # slug = self._pkg_info.slug
            short_help = self._index_info.short_help

            kwargs["short_help"] = short_help
            desc = self._index_info.desc
            help = f"Display info for index '{self._index.name}'"
            if desc:
                help = f"{help}\n\n{desc}"

            params = [
                Option(
                    ["--update", "-u"],
                    help="update index metadata before display",
                    is_flag=True,
                    required=False,
                ),
                # Option(
                #     ["--pkgs", "-p"],
                #     help="display packages of this index",
                #     is_flag=True,
                #     required=False,
                # ),
                Option(
                    ["--full", "-f"],
                    help="display full information for index",
                    is_flag=True,
                    required=False,
                ),
            ]

            kwargs["help"] = help
        except (Exception) as e:
            log.debug(f"Can't create IndexInfoTingCommand object: {e}", exc_info=True)
            raise e

        super().__init__(name=name, callback=self.info, params=params, **kwargs)

    @click.pass_context
    async def info(ctx, self, update: bool = False, full: bool = False):

        self._index_info.update = update
        self._index_info.display_full = full

        console.print(self._index_info)


# class PkgInfoTingCommand(Command):
#     def __init__(self, name: str, pkg: PkgTing, load_details: bool = False, **kwargs):
#
#         self._pkg: PkgTing = pkg
#
#         self._pkg_info: PkgInfoDisplay = PkgInfoDisplay(data=pkg, full_info=True)
#         try:
#
#             # slug = self._pkg_info.slug
#             short_help = self._pkg_info.short_help
#
#             kwargs["short_help"] = short_help
#             desc = self._pkg_info.desc
#             help = f"Display info for the '{self._pkg.name}' package."
#             if desc:
#                 help = f"{help}\n\n{desc}"
#
#             params = [
#                 Option(
#                     ["--update", "-u"],
#                     help="update package metadata",
#                     is_flag=True,
#                     required=False,
#                 ),
#                 Option(
#                     ["--args", "-a"],
#                     help="display only full arguments for package",
#                     is_flag=True,
#                     required=False,
#                 ),
#                 Option(
#                     ["--full", "-f"],
#                     help="display full information for package",
#                     is_flag=True,
#                     required=False,
#                 ),
#             ]
#
#             kwargs["help"] = help
#         except (Exception) as e:
#             log.debug(f"Can't create PkgInstallTingCommand object: {e}", exc_info=True)
#             raise e
#
#         super().__init__(name=name, callback=self.info, params=params, **kwargs)
#
#     @click.pass_context
#     async def info(
#         ctx, self, update: bool = False, full: bool = False, args: bool = False
#     ):
#
#         self._pkg_info.update = update
#         self._pkg_info.display_full_args = args
#         self._pkg_info.display_full = full
#         console.print(self._pkg_info)
