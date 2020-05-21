# -*- coding: utf-8 -*-
import logging
import os
import shutil
from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, List, Mapping, Optional

from bring.defaults import BRING_PLUGIN_CACHE, BRING_WORKSPACE_FOLDER
from bring.pkg import PkgTing
from bring.utils.paths import copy_filtered_files
from frtls.args.arg import RecordArg
from frtls.exceptions import FrklException
from frtls.files import create_temp_dir
from tings.common.templating import TemplaTingRepo
from tings.tingistry import Tingistry
from tings.utils import FileMatcher, file_matches


if TYPE_CHECKING:
    from bring.bring import Bring


log = logging.getLogger("bring")


class PkgProcessor(metaclass=ABCMeta):
    def __init__(
        self,
        bring: "Bring",
        pkg: PkgTing,
        pkg_include: Optional[Iterable[str]] = None,
        **pkg_vars: Any,
    ):

        self._bring: Bring = bring
        self._tingistry_obj: Tingistry = self._bring._tingistry_obj
        self.pkg: PkgTing = pkg
        self._pkg_include: Optional[Iterable[str]] = pkg_include
        self._pkg_vars: Mapping[str, Any] = pkg_vars
        self._pkg_version_hash: Optional[str] = None

        self._pkg: Optional[PkgTing] = None
        self._version_folder: Optional[str] = None

        self._args: Optional[RecordArg] = None

    @property
    async def pkg_version_hash(self) -> str:

        if self._pkg_version_hash is None:
            self._pkg_version_hash = await self.pkg.create_version_hash(
                **self._pkg_vars
            )
        return self._pkg_version_hash

    async def get_version_folder(self) -> str:

        if self._version_folder is None:

            raise Exception("Check create_version_hash arguments")
            version_hash = await self.pkg.create_version_hash(
                vars=self._pkg_vars, include_map=self._pkg_include
            )
            self._version_folder = os.path.join(
                BRING_PLUGIN_CACHE, self.__class__.__name__, str(version_hash)
            )

            if not os.path.exists(self._version_folder):
                try:
                    if self._pkg_include:
                        temp_dir = create_temp_dir(
                            parent_dir=BRING_WORKSPACE_FOLDER, delete_after_exit=True
                        )
                        await self.pkg.create_version_folder(
                            vars=self._pkg_vars, target=temp_dir
                        )
                        copy_filtered_files(
                            orig=temp_dir,
                            include=self._pkg_include,
                            target=self._version_folder,
                            move_files=True,
                        )
                    else:
                        await self.pkg.create_version_folder(
                            vars=self._pkg_vars, target=self._version_folder
                        )

                except Exception as e:
                    log.debug(
                        f"Error when creating processor pkg folder: {self._version_folder}",
                        exc_info=True,
                    )
                    shutil.rmtree(self._version_folder)
                    self._version_folder = None
                    raise e

        return self._version_folder

    async def get_file(self, path: str = None) -> Path:

        version_folder = await self.get_version_folder()

        if path:
            full_path = os.path.join(version_folder, path)
        else:
            childs = os.listdir(version_folder)
            if len(childs) == 0:
                raise FrklException(
                    msg=f"Can't retrieve pkg file for pkg '{self.pkg.name}' (processor: {self.__class__.__name__}).",
                    reason="No files in package.",
                )
            elif len(childs) == 1 and os.path.isfile(childs[0]):
                full_path = os.path.join(version_folder, childs[0])
            else:
                all_files = await self.get_all_files()

                if len(all_files) == 1:
                    full_path = os.path.join(version_folder, all_files[0])
                else:
                    raise FrklException(
                        msg=f"Can't retrieve pkg file for pkg '{self.pkg.name}' (processor: {self.__class__.__name__}).",
                        reason="More than one file in package.",
                    )

        if not os.path.isfile(full_path):

            _p = path
            if _p is None:
                _p = os.path.basename(full_path)
            raise FrklException(
                msg=f"Can't retrieve pkg file '{_p}' for pkg '{self.pkg.name}' (processor: {self.__class__.__name__}).",
                reason="File does not exists, or is not a file.",
            )

        return Path(full_path)

    async def get_all_files(
        self, file_matchers: Optional[Iterable[FileMatcher]] = None
    ) -> List[Path]:

        if file_matchers is None:
            file_matchers = []

        result = []
        version_folder = await self.get_version_folder()

        for root, dirnames, filenames in os.walk(version_folder, topdown=True):

            # if self._search_exclude_dirs:
            #     dirnames[:] = [
            #         d for d in dirnames if d not in self._search_exclude_dirs
            #     ]

            for filename in [
                f
                for f in filenames
                if file_matches(path=os.path.join(root, f), matcher_list=file_matchers)
            ]:

                path = os.path.join(root, filename)

                result.append(Path(path))

        return result

    async def get_args(self) -> RecordArg:

        if self._args is None:
            self._args = await self._get_args()
        return self._args

    async def _get_args(self) -> RecordArg:

        return self._bring.arg_hive.create_record_arg(childs={})

    @abstractmethod
    async def process(self, **vars: Any) -> Mapping[str, Any]:

        pass


class TemplaTingProcessor(PkgProcessor):

    _plugin_name = "template"

    async def process(self, **vars: Any) -> Mapping[str, Any]:

        version_folder = await self.get_version_folder()
        pkg_version_hash = await self.pkg_version_hash
        tempting_repo: TemplaTingRepo = self._tingistry_obj.create_singleting(  # type: ignore
            f"bring.processors.template.{pkg_version_hash}", TemplaTingRepo
        )
        tempting_repo.add_repo_path(version_folder)
        temptings = await tempting_repo.get_value("temptings")

        return {"temptings": temptings}
