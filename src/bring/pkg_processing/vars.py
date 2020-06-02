# -*- coding: utf-8 -*-
import uuid
from enum import Enum
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional, Union

from bring.pkg_processing.explanations import ProcessVars
from frtls.args.arg import Arg, RecordArg
from frtls.args.hive import ArgHive
from frtls.dicts import dict_merge, get_seeded_dict
from frtls.exceptions import ArgValidationError, FrklException


class VarSetType(Enum):

    CONSTANTS = 1
    DEFAULTS = 2
    INPUT = 3


class VarSet(object):
    def __init__(
        self,
        _name: Optional[str] = None,
        _type: VarSetType = VarSetType.DEFAULTS,
        _metadata: Optional[Mapping[str, Any]] = None,
        **vars: Any,
    ):

        if _name is None:
            _name = str(uuid.uuid4())

        self._name: str = _name
        self._type: VarSetType = _type
        if _metadata is None:
            self._metadata: MutableMapping[str, Any] = {}
        else:
            self._metadata = dict(_metadata)

        self._metadata["origin"] = _name
        self._vars: Mapping[str, Any] = vars

    @property
    def name(self) -> str:
        return self._name

    @property
    def type(self) -> VarSetType:
        return self._type

    @property
    def metadata(self) -> Mapping[str, Any]:
        return self._metadata

    @property
    def vars(self) -> Mapping[str, Any]:
        return self._vars

    @property
    def var_names(self) -> Iterable[str]:
        return self._vars.keys()

    def __repr__(self):

        return f"[VarSet: name={self.name} type={self.type} vars={self.vars}]"


class VarHolder(object):
    def __init__(self):

        self._var_sets: Dict[str, VarSet] = {}

        self._aliases: Dict[Any, Any] = {}

        self._merged_per_type: Optional[
            Mapping[VarSetType, MutableMapping[str, Any]]
        ] = None

        self._var_sets_per_type: Optional[
            Mapping[VarSetType, MutableMapping[str, VarSet]]
        ] = None

        self._merged: Optional[Mapping[str, Any]] = None

    def invalidate(self) -> None:

        self._merged = None
        self._var_sets_per_type = None
        self._merged_per_type = None

    def add_var_set(self, var_set: VarSet, replace_existing: bool = False):

        if var_set.name in self._var_sets.keys():
            if not replace_existing:
                raise FrklException(
                    msg=f"Can't add var set '{var_set.name}'.",
                    reason="Var set with that name already exists.",
                )

        self._var_sets[var_set.name] = var_set
        self.invalidate()

    @property
    def merged_per_type(self):

        if self._merged_per_type is not None:
            return self._merged_per_type

        self._merged_per_type = {
            VarSetType.CONSTANTS: {},
            VarSetType.DEFAULTS: {},
            VarSetType.INPUT: {},
        }

        for var_set in self._var_sets.values():
            self._merged_per_type[var_set.type].update(var_set.vars)
        return self._merged_per_type

    @property
    def var_sets_per_type(self) -> Mapping[VarSetType, MutableMapping[str, VarSet]]:

        if self._var_sets_per_type is not None:
            return self._var_sets_per_type

        self._var_sets_per_type = {
            VarSetType.CONSTANTS: {},
            VarSetType.DEFAULTS: {},
            VarSetType.INPUT: {},
        }
        for var_set in self._var_sets.values():
            for k in var_set.var_names:
                self._var_sets_per_type[var_set.type][k] = var_set
        return self._var_sets_per_type

    def get_var_metadata(
        self, var_name: str, var_set_type: Optional[VarSetType] = None
    ) -> Optional[Mapping[str, Any]]:

        metadata = {}
        if var_set_type is not None:
            var_set = self.var_sets_per_type[var_set_type].get(var_name, None)
            if var_set is None:
                metadata["is_set"] = False
            else:
                metadata.update(var_set.metadata)
        elif var_name in self.var_sets_per_type[VarSetType.CONSTANTS].keys():
            md = self.var_sets_per_type[VarSetType.CONSTANTS][var_name].metadata
            metadata.update(md)
        elif var_name in self.var_sets_per_type[VarSetType.INPUT].keys():
            md = self.var_sets_per_type[VarSetType.INPUT][var_name].metadata
            metadata.update(md)
        elif var_name in self.var_sets_per_type[VarSetType.DEFAULTS].keys():
            md = self.var_sets_per_type[VarSetType.DEFAULTS][var_name].metadata
            metadata.update(md)
        else:
            metadata["is_set"] = False

        metadata.setdefault("is_set", True)
        return metadata

    @property
    def merged_vars(self) -> Mapping[str, Any]:

        if self._merged is None:
            self._merged = get_seeded_dict(
                self.merged_per_type[VarSetType.DEFAULTS],
                self.merged_per_type[VarSetType.INPUT],
                self.merged_per_type[VarSetType.CONSTANTS],
            )
        return self._merged

    def create_args(
        self, arg_hive: ArgHive, **arg_descs: Union[Mapping[str, Any], Arg, str]
    ) -> Mapping[VarSetType, RecordArg]:

        constant_args = {}
        input_args = {}

        for arg_name, arg_desc in arg_descs.items():
            if arg_name in self.merged_per_type[VarSetType.CONSTANTS].keys():
                constant_args[arg_name] = arg_desc
            else:
                input_args[arg_name] = arg_desc

        result = {}
        result[VarSetType.CONSTANTS] = arg_hive.create_record_arg(childs=constant_args)
        defaults = self.merged_per_type[VarSetType.DEFAULTS]
        result[VarSetType.INPUT] = arg_hive.create_record_arg(
            childs=input_args, default=defaults
        )

        return result


class ArgsHolder(object):
    def __init__(
        self,
        arg_hive: ArgHive,
        vars_holder: Optional[VarHolder] = None,
        processed_arg_names: Optional[Iterable[str]] = None,
        args_descs: Optional[Mapping[str, Union[Mapping[str, Any], Arg, str]]] = None,
    ):

        self._arg_hive = arg_hive
        if vars_holder is None:
            vars_holder = VarHolder()
        self._vars_holder: VarHolder = vars_holder

        self._args: Optional[RecordArg] = None
        self._constants_args: Optional[RecordArg] = None
        self._input_args: Optional[RecordArg] = None
        self._processed_args: Optional[RecordArg] = None

        self._processed_arg_names: Iterable[str] = []
        self._args_descs: Mapping[str, Union[Mapping[str, Any], Arg, str]] = {}

        self._preprocessed_vars: Optional[Mapping[str, Any]] = None

        self._constant_vars_validated: Optional[Mapping[str, Mapping[str, Any]]] = None
        self._input_vars_validated: Optional[Mapping[str, Mapping[str, Any]]] = None
        self._processed_vars_validated: Optional[Mapping[str, Mapping[str, Any]]] = None
        self._vars_validated: Optional[Mapping[str, Mapping[str, Any]]] = None

        self._value_aliases: Dict[str, Mapping[Any, Any]] = {}

        self._vars: Optional[Mapping[str, Any]] = None
        if args_descs is None:
            args_descs = {}
        self.set_args_descs(_processed_arg_names=processed_arg_names, **args_descs)

    def invalidate(self, invalidate_args: bool = False):

        self._preprocessed_vars = None
        self._constant_vars_validated = None
        self._input_vars_validated = None
        self._processed_vars_validated = None
        self._vars_validated = None
        self._vars = None

        if invalidate_args:
            self._processed_arg_names = []
            self._args = None
            self._constants_args = None
            self._input_args = None
            self._processed_args = None

    def update_value_aliases(
        self, new_aliases: Mapping[str, Mapping[Any, Any]]
    ) -> None:

        dict_merge(self._value_aliases, new_aliases, copy_dct=False)

    def clear_value_aliases(self) -> None:

        self._value_aliases.clear()

    def add_var_set(self, var_set: VarSet, replace_existing: bool = False):

        self.vars_holder.add_var_set(var_set, replace_existing=replace_existing)

        invalidate_args = var_set.type == VarSetType.CONSTANTS
        self.invalidate(invalidate_args=invalidate_args)

    @property
    def vars_holder(self):
        return self._vars_holder

    @property
    def args_descs(self) -> Mapping[str, Union[Mapping[str, Any], Arg, str]]:

        return self._args_descs

    def set_args_descs(
        self,
        _processed_arg_names: Optional[Iterable[str]] = None,
        **args_descs: Mapping[str, Union[Mapping[str, Any], Arg, str]],
    ) -> None:

        self.invalidate(invalidate_args=True)
        self._args_descs = args_descs
        if _processed_arg_names is None:
            _processed_arg_names = []
        self._processed_arg_names = _processed_arg_names

    @property
    def constants_args(self) -> RecordArg:

        if self._constants_args is None:
            self._calculate_args()
        return self._constants_args  # type: ignore

    @property
    def input_args(self) -> RecordArg:

        if self._input_args is None:
            self._calculate_args()
        return self._input_args  # type: ignore

    @property
    def processed_args(self) -> RecordArg:

        if self._processed_args is None:
            self._calculate_args()
        return self._processed_args  # type: ignore

    @property
    def args(self):

        if self._args is None:
            self._args = self._arg_hive.create_record_arg(childs=self._args_descs)
        return self._args

    def _calculate_args(self):

        processed: Mapping[str, Arg] = {}
        other: Mapping[str, Arg] = {}
        for arg_name, arg in self.args.childs.items():
            if arg_name in self._processed_arg_names:
                processed[arg_name] = arg
            else:
                other[arg_name] = arg

        args = self.vars_holder.create_args(arg_hive=self._arg_hive, **other)
        self._constants_args = args[VarSetType.CONSTANTS]
        self._input_args = args[VarSetType.INPUT]
        self._processed_args = self._arg_hive.create_record_arg(childs=processed)

    @property
    def merged_vars(self) -> Mapping[str, Any]:

        return self._vars_holder.merged_vars

    @property
    def preprocessed_vars(self) -> Mapping[str, Any]:

        if self._preprocessed_vars is None:
            self._preprocessed_vars = self._preprocess(**self.merged_vars)
        return self._preprocessed_vars

    def _preprocess(self, **vars: Any) -> Mapping[str, Any]:

        return vars

    def _get_value_alias(self, arg_name: str, value: Any) -> Optional[Any]:

        aliases = self._value_aliases.get(arg_name, None)
        if not aliases:
            return None

        return aliases.get(value, None)

    @property
    def constant_vars_validated(self) -> Mapping[str, Mapping[str, Any]]:

        if self._constant_vars_validated is None:
            validated = {}
            for arg_name, arg in self.constants_args.childs.items():
                value = self.preprocessed_vars[arg_name]
                v = arg.validate(value, raise_exception=True)

                validated[arg_name] = {
                    "value": value,
                    "metadata": self._vars_holder.get_var_metadata(
                        arg_name, var_set_type=VarSetType.CONSTANTS
                    ),
                }

                alias_for = self._get_value_alias(arg_name, v)
                if alias_for is None:
                    validated[arg_name]["validated"] = v
                else:
                    validated[arg_name]["validated"] = alias_for
                    validated[arg_name]["metadata"]["from_alias"] = v

            self._constant_vars_validated = validated
        return self._constant_vars_validated

    @property
    def input_vars_validated(self) -> Mapping[str, Mapping[str, Any]]:

        if self._input_vars_validated is None:
            validated = {}
            errors = {}
            values = {}
            for arg_name, arg in self.input_args.childs.items():
                value = self.preprocessed_vars.get(arg_name, None)
                values[arg_name] = value
                try:
                    v = arg.validate(value, raise_exception=True)
                except ArgValidationError as ave:
                    errors[arg_name] = ave
                    continue
                validated[arg_name] = {
                    "value": value,
                    "metadata": self._vars_holder.get_var_metadata(arg_name),
                }

                alias_for = self._get_value_alias(arg_name, v)
                if alias_for is None:
                    validated[arg_name]["validated"] = v
                else:
                    validated[arg_name]["validated"] = alias_for
                    validated[arg_name]["metadata"]["from_alias"] = v

            if errors:
                raise ArgValidationError(self.input_args, values, child_errors=errors)

            self._input_vars_validated = validated

        return self._input_vars_validated

    @property
    def processed_vars_validated(self) -> Mapping[str, Mapping[str, Any]]:

        if self._processed_vars_validated is None:
            validated = {}
            for arg_name, arg in self.processed_args.childs.items():
                value = self.preprocessed_vars[arg_name]
                v = arg.validate(value, raise_exception=True)
                validated[arg_name] = {"value": value, "metadata": {}}

                alias_for = self._get_value_alias(arg_name, v)
                if alias_for is None:
                    validated[arg_name]["validated"] = v
                else:
                    validated[arg_name]["validated"] = alias_for
                    validated[arg_name]["metadata"]["from_alias"] = v
            self._processed_vars_validated = validated
        return self._processed_vars_validated

    @property
    def vars_validated(self) -> Mapping[str, Mapping[str, Any]]:

        if self._vars_validated is None:
            self._vars_validated = get_seeded_dict(
                self.input_vars_validated,
                self.processed_vars_validated,
                self.constant_vars_validated,
            )
        return self._vars_validated

    def explain(self, show_title: bool = True, as_table: bool = True) -> ProcessVars:

        pv = ProcessVars(self, show_title=show_title, render_as_table=as_table)
        return pv

    @property
    def vars(self) -> Mapping[str, Any]:

        if self._vars is None:
            self._vars = {}
            for k, v in self.vars_validated.items():
                self._vars[k] = v["validated"]
        return self._vars
