# -*- coding: utf-8 -*-
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Mapping, Optional, Union

from frtls.args.arg import RecordArg


if TYPE_CHECKING:
    from bring.bring import Bring


class BringTarget(metaclass=ABCMeta):

    _plugin_type = "instance"

    def __init__(self, bring: "Bring", **input_vars: Any):

        self._bring: "Bring" = bring
        self._input_args: Optional[RecordArg] = None
        self._input_values: Dict[str, Any] = {}
        self._input_preprocessed: Optional[Mapping[str, Any]] = None
        self._input_validated: Optional[Mapping[str, Any]] = None

        if input_vars:
            self.set_input(**input_vars)

    @abstractmethod
    def requires(self) -> Mapping[str, Union[str, Mapping[str, Any]]]:
        pass

    @property
    def input_args(self) -> RecordArg:

        if self._input_args is None:
            self._input_args = self._bring.tingistry.arg_hive.create_record_arg(
                self.requires()
            )
        return self._input_args

    def set_input(self, **input_vars: Any):

        self.invalidate()
        self._input_values.update(input_vars)

    def preprocess_input(self, input_vars: Mapping[str, Any]) -> Mapping[str, Any]:
        return input_vars

    def invalidate(self):
        self._input_validated = None

        if hasattr(self, "_invalidate"):
            self._invalidate()

    def current_input(self, validate: bool = False) -> Mapping[str, Any]:

        if self._input_preprocessed is None:
            self._input_preprocessed = self.preprocess_input(self._input_values)

        if not validate:
            return self._input_preprocessed

        if self._input_validated is None:
            self._input_validated = self.input_args.validate(
                self._input_preprocessed, raise_exception=True
            )
        return self._input_validated

    # def create_processor(
    #     self, processor_type: str, constants: Optional[Mapping[str, Any]]=None, **processor_input: Any
    # ) -> BringProcessor:
    #
    #     proc = self._bring.create_processor(processor_type, constants=constants, **processor_input)
    #
    #     return proc
    #
    # async def apply(
    #     self, processor: BringProcessor
    # ) -> Mapping[str, Any]:
    #
    #     proc_inp = await processor.get_current_input_async(validate=True)
    #
    #     result_proc = await processor.process()
    #
    #     result = await self.process_result(input=proc_inp, result=result_proc)
    #
    #     return result
    #
    # @abstractmethod
    # async def process_result(
    #     self, input: Mapping[str, Any], result: Mapping[str, Any]
    # ) -> Mapping[str, Any]:
    #     pass
