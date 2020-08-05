# -*- coding: utf-8 -*-
# import logging
# from typing import TYPE_CHECKING, Any, Mapping, Optional
#
# from bring.pkg_index.pkg import PkgTing
# from frkl.common.exceptions import FrklException
# from tings.common.templating import TemplaTing, TemplaTingRepo
#
#
# if TYPE_CHECKING:
#     from bring.bring import Bring
#
# log = logging.getLogger("bring")
#
#
# class BringTemplate(object):
#     def __init__(
#         self,
#         bring: "Bring",
#         templates_pkg: str,
#         templates_pkg_vars: Optional[Mapping[str, Any]] = None,
#     ):
#
#         self._bring: "Bring" = bring
#         self._templates_pkg_name: str = templates_pkg
#         if templates_pkg_vars is None:
#             templates_pkg_vars = {}
#         self._templates_pkg_vars: Mapping[str, Any] = templates_pkg_vars
#
#         self._templates_pkg: Optional[PkgTing] = None
#         self._pkg_version_hash: Optional[str] = None
#
#         self._tempting_repo: Optional[TemplaTingRepo] = None
#         self._temptings: Optional[Mapping[str, TemplaTing]] = None
#
#         self._version_folder: Optional[str] = None
#
#     async def get_templates_pkg(self) -> PkgTing:
#
#         if self._templates_pkg is None:
#             self._templates_pkg = await self._bring.get_pkg(
#                 self._templates_pkg_name, raise_exception=False
#             )
#             if self._templates_pkg is None:
#                 raise FrklException(
#                     msg="Can't process template.",
#                     reason=f"Specified templates pkg '{self._templates_pkg_name}' does not exist.",
#                 )
#         return self._templates_pkg
#
#         # async def get_pkg_version_hash(self):
#         #
#         #     if self._pkg_version_hash is None:
#         #         pkg = await self.get_templates_pkg()
#         #         self._pkg_version_hash = await pkg.create_version_hash(
#         #             **self._templates_pkg_vars
#         #         )
#         #     return self._pkg_version_hash
#
#         # async def get_version_folder(self) -> str:
#         #
#         #     raise NotImplementedError()
#         # if self._version_folder is None:
#         #
#         #     pkg = await self.get_templates_pkg()
#         #     version_hash = await pkg.create_version_hash(**self._templates_pkg_vars)
#         #     self._version_folder = os.path.join(
#         #         BRING_PLUGIN_CACHE, self.__class__.__name__, str(version_hash)
#         #     )
#         #
#         #     if not os.path.exists(self._version_folder):
#         #         try:
#         #             await pkg.create_version_folder(
#         #                 vars=self._templates_pkg_vars, target=self._version_folder
#         #             )
#         #         except Exception as e:
#         #             log.debug(
#         #                 f"Error when creating plugin pkg folder: {self._version_folder}",
#         #                 exc_info=True,
#         #             )
#         #             shutil.rmtree(self._version_folder)
#         #             self._version_folder = None
#         #             raise e
#
#         # return self._version_folder
#
#     async def get_tempting_repo(self) -> TemplaTingRepo:
#
#         if self._tempting_repo is None:
#             version_folder = await self.get_version_folder()
#             self._tempting_repo = self._bring._tingistry_obj.create_singleting(  # type: ignore
#                 f"bring.plugins.template.{self._pkg_version_hash}", TemplaTingRepo
#             )
#             if self._tempting_repo is None:
#                 raise Exception("tempting repo not set, this is a bug")
#             self._tempting_repo.add_repo_path(version_folder)
#         return self._tempting_repo
#
#     async def get_temptings(self) -> Mapping[str, TemplaTing]:
#
#         if self._temptings is None:
#             repo = await self.get_tempting_repo()
#             self._temptings = await repo.get_temptings()
#
#         return self._temptings
#
#     async def get_tempting(self, name: str) -> TemplaTing:
#
#         temptings = await self.get_temptings()
#         tempting = temptings.get(name, None)
#         if tempting is None:
#             raise FrklException(
#                 f"Can't process template '{name}'.",
#                 reason=f"Template does not exist. Available: {', '.join(sorted(temptings.keys()))}",
#             )
#         return tempting
