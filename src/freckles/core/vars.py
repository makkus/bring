# -*- coding: utf-8 -*-
import functools
import uuid
from enum import Enum
from typing import Any, Mapping, Optional

from frkl.args.arg import Arg


@functools.total_ordering
class FreckletInputType(Enum):

    DEFAULTS = 1
    INPUT = 2
    CONSTANTS = 3

    @staticmethod
    def min():
        return FreckletInputType.DEFAULTS

    @staticmethod
    def max():
        return FreckletInputType.CONSTANTS

    @staticmethod
    def list():
        return sorted(FreckletInputType)

    def __lt__(self, other):

        if self.__class__ is other.__class__:
            return self.value < other.value

        return NotImplemented


@functools.total_ordering
class FreckletInputSet(object):
    def __init__(
        self,
        _id: Optional[str] = None,
        _type: FreckletInputType = FreckletInputType.DEFAULTS,
        _priority: int = 0,
        _metadata: Mapping[str, Any] = None,
        **values: Any,
    ):

        if _id is None:
            _id = str(uuid.uuid4())

        self._id: str = _id
        self._type: FreckletInputType = _type
        self._priority: int = _priority

        if _metadata is None:
            self._metadata: Mapping[str, Any] = {}
        else:
            self._metadata = dict(_metadata)

        self._values: Mapping[str, Any] = values

    @property
    def id(self) -> str:
        return self._id

    @property
    def type(self) -> FreckletInputType:
        return self._type

    @property
    def priority(self) -> int:
        return self._priority

    @property
    def metadata(self) -> Mapping[str, Any]:
        return self._metadata

    def has_value(self, key: str):

        return key in self.values.keys()

    @property
    def values(self) -> Mapping[str, Any]:
        return self._values

    def get_value(self, key) -> Any:

        return self.values.get(key)

    def __lt__(self, other):

        if not isinstance(other, FreckletInputSet):
            return NotImplemented

        return (self.type, self.priority, self.id) < (
            other.type,
            other.priority,
            other.id,
        )

    def __eq__(self, other):

        if not isinstance(other, FreckletInputSet):
            return False

        return (self.id, self.type, self.priority) == (
            other.id,
            other.type,
            other.priority,
        )

    def __repr__(self):

        return f"[FreckletInput: id={self.id} type={self.type} values={self.values}]"


class Var(object):
    def __init__(
        self, raw_value: Any, value: Any, origin: Optional[FreckletInputSet], arg: Arg
    ):

        self._raw_value: Any = raw_value
        self._value: Any = value
        self._origin: Optional[FreckletInputSet] = origin
        self._arg: Arg = arg

    @property
    def raw_value(self) -> Any:
        return self._raw_value

    @property
    def value(self) -> Any:
        return self._value

    @property
    def origin(self) -> Optional[FreckletInputSet]:
        return self._origin

    @property
    def arg(self) -> Arg:
        return self._arg

    def __repr__(self):

        origin = "n/a" if self.origin is None else self.origin.id

        return f"[Var: value={self.value} origin={origin}]"


class VarSet(object):
    def __init__(self, **vars: Var):

        self._vars: Mapping[str, Var] = vars

    def vars(self) -> Mapping[str, Var]:

        return self._vars

    def create_values_dict(self) -> Mapping[str, Any]:

        result = {}
        for k, v in self._vars.items():
            result[k] = v.value
        return result
