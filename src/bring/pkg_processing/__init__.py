# -*- coding: utf-8 -*-
import logging
from abc import ABCMeta, abstractmethod
from typing import (
    TYPE_CHECKING,
    Any,
    Iterable,
    Mapping,
    MutableMapping,
    Optional,
    Union,
)

from bring.mogrify import Transmogrificator
from frtls.args.arg import Arg, RecordArg
from frtls.args.hive import ArgHive
from frtls.async_helpers import wrap_async_task
from frtls.dicts import get_seeded_dict
from frtls.exceptions import FrklException


if TYPE_CHECKING:
    from bring.pkg_index.pkg import PkgTing
    from bring.bring import Bring


log = logging.getLogger("bring")


class BringProcessor(metaclass=ABCMeta):

    _plugin_type = "instance"

    def __init__(self, bring: "Bring", **input_vars) -> None:

        self._bring: "Bring" = bring

        self._arg_hive: ArgHive = self._bring._tingistry_obj.arg_hive

        self._result: Optional[Any] = None

        self._input_args: Optional[RecordArg] = None
        self._input_vars: MutableMapping[str, Any] = {}
        self._input_processed: Optional[Mapping[str, Any]] = None
        self._input_validated: Optional[Mapping[str, Any]] = None
        if input_vars:
            self.set_input(**input_vars)

    def get_current_input(self, validate: bool = False) -> Mapping[str, Any]:

        if validate:
            if self._input_validated is None:
                wrap_async_task(self.get_current_input_async, validate=True)
            return self._input_validated  # type: ignore
        else:
            if self._input_processed is None:
                wrap_async_task(self.get_current_input_async, validate=False)
            return self._input_processed  # type: ignore

    async def get_current_input_async(
        self, validate: bool = False
    ) -> Mapping[str, Any]:

        if self._input_processed is None:
            self._input_processed = await self.preprocess_input(self._input_vars)

        if not validate:
            return self._input_processed

        if self._input_validated is None:
            args = await self.get_input_args()
            self._input_validated = args.validate(self._input_processed)

        return self._input_validated

    def invalidate(self):

        self._input_processed = None
        self._input_validated

    def set_input(self, **input_vars: Any):

        if self._result is not None:
            raise FrklException(
                msg="Can't set input for pkg processor.",
                reason="Processor already ran.",
            )

        self._input_vars.update(input_vars)
        self.invalidate()

    async def get_input_args(self) -> RecordArg:

        if self._input_args is not None:
            return self._input_args

        reqs = await self.requires()
        self._input_args = self._arg_hive.create_record_arg(reqs)
        return self._input_args

    @abstractmethod
    async def requires(self) -> Mapping[str, Union[str, Arg, Mapping[str, Any]]]:
        pass

    # @abstractmethod
    # def requires(self) -> Mapping[str, Union[str, Arg, Mapping[str, Any]]]:
    #     pass

    async def preprocess_input(
        self, input_vars: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        return input_vars

    @abstractmethod
    async def process(self) -> Mapping[str, Any]:

        pass


class PkgProcessor(BringProcessor):
    def __init__(self, bring: "Bring", **input_vars):

        self._pkg: Optional["PkgTing"] = None
        self._pkg_args: Optional[RecordArg] = None
        self._transmogrificator: Optional[Transmogrificator] = None

        super().__init__(bring, **input_vars)

    @abstractmethod
    def get_pkg_name(self) -> str:
        pass

    @abstractmethod
    def get_pkg_index(self) -> Optional[str]:
        pass

    async def extra_requires(self) -> Mapping[str, Union[str, Arg, Mapping[str, Any]]]:

        return {}

    async def preprocess_input(
        self, input_vars: Mapping[str, Any]
    ) -> Mapping[str, Any]:

        pkg = await self.get_pkg()

        pkg_vars = await pkg.calculate_full_vars(**input_vars)

        result = get_seeded_dict(input_vars, pkg_vars)
        return result

    async def requires(self) -> Mapping[str, Union[str, Arg, Mapping[str, Any]]]:

        pkg = await self.get_pkg()
        pkg_args: RecordArg = await pkg.get_pkg_args()

        result: MutableMapping[str, Union[str, Arg, Mapping[str, Any]]] = dict(
            pkg_args.childs
        )

        req_extra = await self.extra_requires()
        for k, v in req_extra.items():
            if k in result.keys():
                raise FrklException(
                    msg="Can't create args for pkg processor.",
                    reason=f"Duplicate arg name: {k}",
                )
            result[k] = v
        return result

    async def get_pkg(self) -> "PkgTing":

        if self._pkg is None:
            pkg_name = self.get_pkg_name()
            if pkg_name is None:
                raise FrklException(
                    msg="Error in package processor",
                    reason="No package name specified (yet).",
                )
            pkg_index = self.get_pkg_index()
            self._pkg = await self._bring.get_pkg(
                pkg_name, pkg_index, raise_exception=True
            )

        return self._pkg  # type: ignore

    def invalidate(self):

        super().invalidate()
        self._transmogrificator = None
        self._pkg = None

    async def get_transmogrificator(self) -> Transmogrificator:

        if self._transmogrificator is not None:
            return self._transmogrificator

        extra_mogrifiers = self.get_mogrifiers()
        # pkg = await self.get_pkg()
        # cur_inp = await self.get_current_input_async()

        # vals: Mapping[str, Any] = await self.get_values(  # type: ignore
        #      "metadata", resolve=True
        # )
        # metadata = vals["metadata"]
        full_vars = await self.get_current_input_async(validate=True)
        pkg = await self.get_pkg()
        self._transmogrificator = await pkg.create_transmogrificator(
            vars=full_vars, extra_mogrifiers=extra_mogrifiers
        )

        return self._transmogrificator

    def get_mogrifiers(self) -> Iterable[Union[str, Mapping[str, Any]]]:
        return []

    async def process(self) -> Mapping[str, Any]:

        if self._result is not None:
            raise FrklException(msg="Can't run pkg processor.", reason="Already ran.")

        await self.get_current_input_async(validate=True)
        # args = await self.get_input_args()
        # args.validate(self.get_current_input(), raise_exception=True)

        tm: Transmogrificator = await self.get_transmogrificator()
        self._result = await tm.transmogrify()
        return self._result


class InstallProcessor(PkgProcessor):

    _plugin_name = "install"

    def get_pkg_name(self) -> str:

        return self._input_vars["pkg_name"]

    def get_pkg_index(self) -> Optional[str]:

        return self._input_vars.get("pkg_index", None)

    async def extra_requires(self) -> Mapping[str, Union[str, Arg, Mapping[str, Any]]]:
        """Overwrite this method if you inherit from this class, not '_requires' directly."""

        return {"pkg_name": "string", "pkg_index": "string?"}

    # async def requires(
    #     self,
    # ) -> Optional[Mapping[str, Union[str, Arg, Mapping[str, Any]]]]:
    #     return {"pkg_name": "string", "pkg_index": "string?"}

    # async def get_pkg_name(self) -> str:
    #
    #     return (await self.get_current_input())["pkg_name"]
    #
    # async def get_pkg_index(self) -> Optional[str]:
    #
    #     return (await self.get_current_input()).get("pkg_index", None)


# class InstallProcessor(PkgProcessor):
#
#     _plugin_name = "install"
#
#     _extra_args = {
#         "merge_strategy": {
#             "type": "merge_strategy",
#             "doc": "the merge configuration",
#             "required": False,
#         }
#     }
#
#     def requires(self) -> Mapping[str, Union[str, Mapping[str, Any]]]:
#
#         return InstallProcessor._extra_args
#
#     def get_mogrifiers(self) -> Iterable[Union[str, Mapping[str, Any]]]:
#
#         return []
#         # ci =  self.current_input
#         # print(ci)
#         # return [
#         #     {
#         #         "type": "merge_into",
#         #         "target": ci.get("path", None),
#         #         "merge_strategy": ci.get("merge_strategy", None),
#         #     }
#         # ]
