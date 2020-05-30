# -*- coding: utf-8 -*-
import copy
import logging
import uuid
from abc import ABCMeta, abstractmethod
from enum import Enum
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
from frtls.async_helpers import wrap_async_task
from frtls.dicts import dict_merge, get_seeded_dict
from frtls.doc.explanation import Explanation
from frtls.doc.explanation.steps import StepsExplanation
from frtls.exceptions import FrklException
from frtls.types.utils import is_instance_or_subclass
from rich.console import Console, ConsoleOptions, RenderResult


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


class ProcessVars(Explanation):
    def __init__(self, args_holder: "ArgsHolder"):

        self._args_holder: ArgsHolder = args_holder
        self._arg_map: Optional[Dict[str, Dict[str, Any]]] = None

    @property
    def arg_map(self):

        if self._arg_map is not None:
            return self._arg_map

        # print(self._vars_validated)
        result: Dict[str, Dict[str, Any]] = {}
        for arg_name, data in sorted(self._args_holder.vars_validated.items()):

            result[arg_name] = {}

            metadata = data["metadata"]
            is_set = metadata["is_set"]

            if not is_set:
                result[arg_name]["is_set"] = is_set
                continue

            result[arg_name]["value"] = data["validated"]

            origin = metadata["origin"]
            result[arg_name]["origin"] = origin

            alias = metadata.get("from_alias", None)
            if alias is not None:
                result[arg_name]["from_alias"] = alias

            if data["validated"] != data["value"] and data["value"] != metadata.get(
                "from_alias", None
            ):
                result[arg_name]["orig_value"] = data["value"]

        self._arg_map = result
        return self._arg_map

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:

        result = []

        result.append("\n[bold]Variables[/bold]:")
        result.append("")
        for arg_name, data in self.arg_map.items():
            _alias = data.get("from_alias", "")
            if _alias:
                _alias = f" (from alias: [italic]{_alias}[/italic])"
            result.append(f"  {arg_name}: [italic]{data['value']}[/italic]{_alias}")

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
            for arg_name, arg in self.input_args.childs.items():
                value = self.preprocessed_vars.get(arg_name, None)
                v = arg.validate(value, raise_exception=True)
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

    def explain(self) -> ProcessVars:

        pv = ProcessVars(self)
        return pv

    @property
    def vars(self) -> Mapping[str, Any]:

        if self._vars is None:
            self._vars = {}
            for k, v in self.vars_validated.items():
                self._vars[k] = v["validated"]
        return self._vars


class BringProcessor(metaclass=ABCMeta):

    _plugin_type = "instance"

    def __init__(self, bring: "Bring") -> None:

        self._bring: "Bring" = bring

        self._arg_hive: ArgHive = self._bring._tingistry_obj.arg_hive
        self._args_holder: ArgsHolder = ArgsHolder(arg_hive=self._arg_hive)

        self._input_processed: Optional[Mapping[str, Any]] = None
        self._result: Optional[Any] = None

        bring_defaults = wrap_async_task(self._bring.get_defaults)
        self.add_defaults(
            _defaults_name="bring_defaults",
            _defaults_metadata={"bring": self._bring},
            **bring_defaults,
        )

    @property
    def args_holder(self) -> ArgsHolder:
        return self._args_holder

    def invalidate(self) -> None:

        self._input_processed = None

    def add_var_set(self, var_set: VarSet, replace_existing: bool = False) -> None:

        self._args_holder.add_var_set(var_set, replace_existing=replace_existing)
        self.invalidate()

    def add_constants(
        self,
        _constants_name: Optional[str] = None,
        _constants_metadata: Optional[Mapping[str, Any]] = None,
        **constants: Any,
    ) -> None:

        var_set = VarSet(
            _name=_constants_name,
            _type=VarSetType.CONSTANTS,
            _metadata=_constants_metadata,
            **constants,
        )
        self.add_var_set(var_set)

    def add_defaults(
        self,
        _defaults_name: Optional[str] = None,
        _defaults_metadata: Optional[Mapping[str, Any]] = None,
        _replace_existing: bool = False,
        **defaults: Any,
    ) -> None:

        var_set = VarSet(
            _name=_defaults_name,
            _type=VarSetType.DEFAULTS,
            _metadata=_defaults_metadata,
            **defaults,
        )
        self.add_var_set(var_set, replace_existing=_replace_existing)

    def set_user_input(self, **input_vars: Any):

        # TODO: check if overwriting constants

        if self._result is not None:
            raise FrklException(
                msg="Can't set input for pkg processor.",
                reason="Processor already ran.",
            )

        if not input_vars:
            return

        input_var_set = VarSet(_name="input", _type=VarSetType.INPUT, **input_vars)
        self.add_var_set(input_var_set)

    async def get_processed_input_async(self) -> Mapping[str, Any]:

        if self._input_processed is None:
            all_args = await self.get_all_required_args()

            self._args_holder.set_args_descs(**all_args)

            self._input_processed = self._args_holder.vars

        return self._input_processed  # type: ignore

    async def get_user_input_args(self) -> RecordArg:
        await self.get_processed_input_async()
        result = self._args_holder.input_args
        return result

    @abstractmethod
    async def get_all_required_args(
        self,
    ) -> Mapping[str, Union[str, Arg, Mapping[str, Any]]]:
        pass

    @abstractmethod
    async def _process(self) -> Any:

        pass

    async def process(self) -> Any:

        result = await self._process()

        if is_instance_or_subclass(result, Explanation):
            self._result = result
        else:
            self._result = ProcessResult(vars=self._args_holder.vars, result=result)
        return self._result

    def explain(self) -> "ProcessInfo":

        pi = ProcessInfo(self)
        return pi

    def explain_vars(self) -> ProcessVars:

        return self._args_holder.explain()

    async def explain_tasks(self) -> StepsExplanation:

        se = StepsExplanation({"process": self.get_msg()})
        return se

    async def get_msg(self) -> str:

        if hasattr(self.__class__, "_plugin_name"):
            proc_name = self.__class__._plugin_name  # type: ignore
        else:
            proc_name = self.__class__.__name__

        return f"executing processor '{proc_name}'"

    def create_process_info(self) -> "ProcessInfo":

        pi = ProcessInfo(self)
        return pi


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
        self,
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
            pkg: PkgTing = await self._bring.get_pkg(
                pkg_name, pkg_index, raise_exception=True
            )  # type: ignore

            vals: Mapping[str, Any] = await pkg.get_values(
                "aliases", "args", resolve=True
            )  # type: ignore

            args: RecordArg = vals["args"]
            pkg_defaults = args.default

            aliases: Mapping[str, Mapping[Any, Any]] = vals["aliases"]

            self.add_defaults(
                _defaults_name="pkg_defaults",
                _defaults_metadata={"pkg": pkg},
                _replace_existing=True,
                **pkg_defaults,
            )
            index_defaults = await pkg.bring_index.get_index_defaults()
            self.add_defaults(
                _defaults_name="index_defaults",
                _defaults_metadata={"index": pkg.bring_index},
                _replace_existing=True,
                **index_defaults,
            )
            self.args_holder.clear_value_aliases()
            self._args_holder.update_value_aliases(aliases)
            self._pkg = pkg

        return self._pkg  # type: ignore

    def invalidate(self, invalidate_args: bool = True):

        self._transmogrificator = None
        self._pkg = None

        super().invalidate()

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

    async def _process(self) -> Mapping[str, Any]:

        if self._result is not None:
            raise FrklException(msg="Can't run pkg processor.", reason="Already ran.")

        # await self.get_processed_input_async()
        # args = await self.get_input_args()
        # args.validate(self.get_current_input(), raise_exception=True)

        tm: Transmogrificator = await self.get_transmogrificator()
        result = await tm.transmogrify()
        return result

    async def explain_tasks(self) -> StepsExplanation:

        tm: Transmogrificator = await self.get_transmogrificator()

        steps = tm.explain_steps()
        return steps

    async def get_msg(self) -> str:

        msg = await super(PkgProcessor, self).get_msg()
        pkg = await self.get_pkg()
        return msg + f" with package '{pkg.pkg_id}'"


class ProcessInfo(Explanation):
    def __init__(self, processor: BringProcessor):

        self._processor: BringProcessor = processor
        self._msg: Optional[str] = None
        self._explained_tasks: Optional[StepsExplanation] = None

    @property
    def explained_vars(self) -> ProcessVars:

        return self._processor.explain_vars()

    async def get_explained_tasks(self) -> StepsExplanation:

        if self._explained_tasks is None:
            self._explained_tasks = await self._processor.explain_tasks()
        return self._explained_tasks

    async def get_process_msg(self) -> str:

        if self._msg is None:
            self._msg = await self._processor.get_msg()
        return self._msg

    async def _init(self) -> None:

        await self.get_process_msg()
        await self.get_explained_tasks()

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:

        if self._msg is None or self._explained_tasks is None:
            wrap_async_task(self._init)

        yield f"\n[bold]Task[/bold]: {self._msg}"

        yield self.explained_vars

        yield self._explained_tasks  # type: ignore


class ProcessResult(Explanation):
    def __init__(self, vars: Mapping[str, Any], result: Any):

        self._vars: Mapping[str, Any] = vars
        self._result: Any = result

    @property
    def vars(self):

        return self._vars

    @property
    def result(self):

        return self._result

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:

        result = []

        result.append("[bold]Result:[/bold]")
        result.append("")
        for key, data in self._result.items():
            result.append(f"  {key}: [italic]{data}[/italic]")

        return result
