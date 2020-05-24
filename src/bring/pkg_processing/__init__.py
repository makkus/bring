# -*- coding: utf-8 -*-
import copy
import logging
import uuid
from abc import ABCMeta, abstractmethod
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    Mapping,
    MutableMapping,
    Optional,
    Union,
)

from bring.mogrify import Transmogrificator
from frtls.args.arg import Arg, RecordArg
from frtls.args.hive import ArgHive
from frtls.dicts import get_seeded_dict
from frtls.exceptions import FrklException


if TYPE_CHECKING:
    from bring.pkg_index.pkg import PkgTing
    from bring.bring import Bring


log = logging.getLogger("bring")


# class BringProcessor(SimpleTing):
#
#     def __init__(self, name: str, meta: TingMeta):
#
#         super().__init__(name=name, meta=meta)
#
#


class BringProcessor(metaclass=ABCMeta):

    _plugin_type = "instance"

    def __init__(self, bring: "Bring") -> None:

        self._bring: "Bring" = bring

        self._arg_hive: ArgHive = self._bring._tingistry_obj.arg_hive

        self._result: Optional[Any] = None

        # if constants is None:
        #     constants = {}
        self._constants_list: Dict[str, Mapping[str, Any]] = {}
        self._constants: Dict[str, Any] = {}
        self._constants_args: Optional[RecordArg] = None

        self._user_input: MutableMapping[str, Any] = {}
        self._user_input_args: Optional[RecordArg] = None

        self._all_args: Optional[RecordArg] = None

        self._current_vars: Optional[MutableMapping[str, Any]] = None

        self._constants_validated: Optional[Mapping[str, Any]] = None
        self._user_input_validated: Optional[Mapping[str, Any]] = None

        self._input_validated: Optional[Mapping[str, Any]] = None
        self._input_processed: Optional[Mapping[str, Any]] = None

    def invalidate(self, invalidate_args: bool = True) -> None:

        self._current_vars = None
        self._input_processed = None

        self._user_input_validated = None
        self._constants_validated = None
        self._input_validated = None

        if invalidate_args:
            self._all_args = None
            self._user_input_args = None
            self._constants_args = None

    def add_constants(
        self,
        _constants_name: Optional[str] = None,
        _constants_metadata: Optional[Mapping[str, Any]] = None,
        **constants: Any,
    ) -> None:

        if self._result is not None:
            raise FrklException(
                msg="Can't set constants for pkg processor.",
                reason="Processor already ran.",
            )

        # if not constants:
        #     return

        if _constants_name is None:
            _constants_name = str(uuid.uuid4())

        if _constants_name in self._constants.keys():
            raise FrklException(
                msg=f"Can't add constants set '{_constants_name}'",
                reason="Set with that name already exists.",
            )
        if _constants_metadata is None:
            _constants_metadata = {}
        self._constants_list[_constants_name] = {
            "metadata": _constants_metadata,
            "value": constants,
        }
        self._constants.update(constants)
        self.invalidate()

    def set_user_input(self, **input_vars: Any):

        # TODO: check if overwriting constants

        if self._result is not None:
            raise FrklException(
                msg="Can't set input for pkg processor.",
                reason="Processor already ran.",
            )

        if not input_vars:
            return

        self._user_input = input_vars
        self.invalidate(invalidate_args=False)

    @property
    def current_vars(self) -> Mapping[str, Any]:

        if self._current_vars is not None:
            return self._current_vars

        self._current_vars = {}
        self._current_vars.update(self._user_input)
        self._current_vars.update(self._constants)

        return self._current_vars

    # def get_current_input(self, validate: bool = False) -> Mapping[str, Any]:
    #
    #     if validate:
    #         if self._input_validated is None:
    #             wrap_async_task(self.get_current_input_async, validate=True)
    #         return self._input_validated  # type: ignore
    #     else:
    #         if self._input_processed is None:
    #             wrap_async_task(self.get_current_input_async, validate=False)
    #         return self._input_processed  # type: ignore

    async def get_processed_input_async(self) -> Mapping[str, Any]:

        if self._input_processed is None:
            input_values_preprocessed = await self._preprocess_input_values()
            self._input_processed = await self.preprocess_input(
                input_values_preprocessed
            )

        if self._user_input_validated is None:
            args = await self.get_user_input_args()
            self._user_input_validated = args.validate(self._input_processed)

            c_args = await self.get_constants_args()
            self._constants_validated = c_args.validate(self._input_processed)

            self._input_validated = get_seeded_dict(
                self._user_input_validated,
                self._constants_validated,
                merge_strategy="update",
            )
            self._input_processed = await self.postprocess_input(
                self._input_validated  # type: ignore
            )

        return self._input_processed  # type: ignore

    async def get_args(self) -> RecordArg:

        if self._all_args is not None:
            return self._all_args

        reqs = await self.get_all_required_args()
        self._all_args = self._arg_hive.create_record_arg(reqs)
        return self._all_args

    async def get_constants_args(self) -> RecordArg:

        if self._constants_args is not None:
            return self._constants_args

        reqs = await self.get_all_required_args()
        reqs_filtered = {}

        for arg_name, arg in reqs.items():
            if arg_name not in self._constants.keys():
                continue
            reqs_filtered[arg_name] = arg
        self._constants_args = self._arg_hive.create_record_arg(reqs_filtered)
        return self._constants_args

    async def get_user_input_args(self) -> RecordArg:

        if self._user_input_args is not None:
            return self._user_input_args

        reqs = await self.get_all_required_args()
        reqs_filtered = {}

        for arg_name, arg in reqs.items():
            if arg_name in self._constants.keys():
                continue
            reqs_filtered[arg_name] = arg
        self._user_input_args = self._arg_hive.create_record_arg(reqs_filtered)
        return self._user_input_args

    @abstractmethod
    async def get_all_required_args(
        self
    ) -> Mapping[str, Union[str, Arg, Mapping[str, Any]]]:
        pass

    # @abstractmethod
    # def requires(self) -> Mapping[str, Union[str, Arg, Mapping[str, Any]]]:
    #     pass

    async def _preprocess_input_values(self) -> Mapping[str, Any]:

        result = {}
        constants_args = await self.get_constants_args()
        for arg_name, arg in constants_args.childs.items():
            old_value = self._constants[arg_name]
            new_value = await self.preprocess_value(arg_name, old_value, arg)
            result[arg_name] = new_value

        input_args = await self.get_user_input_args()
        for arg_name, arg in input_args.childs.items():
            old_value = self._user_input.get(arg_name, None)
            new_value = await self.preprocess_value(arg_name, old_value, arg)
            result[arg_name] = new_value

        return result

    async def preprocess_value(self, key: str, value: Any, arg: Arg):

        return value

    async def preprocess_input(
        self, input_vars: Mapping[str, Any]
    ) -> Mapping[str, Any]:

        return input_vars

    async def postprocess_input(self, input_vars: Mapping[str, Any]):
        return input_vars

    @abstractmethod
    async def process(self) -> Mapping[str, Any]:

        pass


class PkgProcessor(BringProcessor):
    def __init__(self, bring: "Bring"):

        self._pkg: Optional["PkgTing"] = None
        self._pkg_args: Optional[RecordArg] = None
        self._transmogrificator: Optional[Transmogrificator] = None

        super().__init__(bring)

    @abstractmethod
    async def get_pkg_name(self) -> str:
        pass

    @abstractmethod
    async def get_pkg_index(self) -> str:
        pass

    async def extra_requires(self) -> Mapping[str, Union[str, Arg, Mapping[str, Any]]]:

        return {}

    async def preprocess_input(
        self, input_vars: Mapping[str, Any]
    ) -> Mapping[str, Any]:

        pkg = await self.get_pkg()

        pkg_vars = await pkg.calculate_full_vars(**input_vars)

        result = get_seeded_dict(input_vars, pkg_vars)
        result["pkg_name"] = pkg.name
        result["pkg_index"] = pkg.bring_index.id

        return result

    async def get_all_required_args(
        self
    ) -> Mapping[str, Union[str, Arg, Mapping[str, Any]]]:

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
            pkg_name = await self.get_pkg_name()
            if pkg_name is None:
                raise FrklException(
                    msg="Error in package processor",
                    reason="No package name specified (yet).",
                )

            pkg_index = await self.get_pkg_index()
            pkg = await self._bring.get_pkg(pkg_name, pkg_index, raise_exception=True)
            # index_defaults = await pkg.bring_index.get_index_defaults()
            # self.add_constants(_constants_name="index defaults", **index_defaults)
            self._pkg = pkg

        return self._pkg  # type: ignore

    def invalidate(self, invalidate_args: bool = True):

        self._transmogrificator = None
        self._pkg = None
        super().invalidate(invalidate_args=invalidate_args)

    async def get_transmogrificator(self) -> Transmogrificator:

        if self._transmogrificator is not None:
            return self._transmogrificator

        full_vars = await self.get_processed_input_async()
        extra_mogrifiers = await self.get_mogrifiers(**copy.deepcopy(full_vars))

        pkg = await self.get_pkg()
        self._transmogrificator = await pkg.create_transmogrificator(
            vars=full_vars, extra_mogrifiers=extra_mogrifiers
        )

        return self._transmogrificator

    async def get_mogrifiers(self, **vars) -> Iterable[Union[str, Mapping[str, Any]]]:
        return []

    async def process(self) -> Mapping[str, Any]:

        if self._result is not None:
            raise FrklException(msg="Can't run pkg processor.", reason="Already ran.")

        # await self.get_processed_input_async()
        # args = await self.get_input_args()
        # args.validate(self.get_current_input(), raise_exception=True)

        tm: Transmogrificator = await self.get_transmogrificator()
        self._result = await tm.transmogrify()
        return self._result
