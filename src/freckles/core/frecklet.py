# -*- coding: utf-8 -*-
import collections
import copy
from abc import abstractmethod
from functools import lru_cache
from typing import (
    Any,
    Dict,
    Hashable,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Type,
    Union,
)

from anyio import create_task_group
from bring.defaults import BRING_TASKS_BASE_TOPIC
from bring.interfaces.cli import console
from bring.utils import BringTaskDesc
from freckles.core.explanation import FreckletExplanation, FreckletInputExplanation
from freckles.core.vars import FreckletInputSet, FreckletInputType, Var, VarSet
from frtls.args.arg import Arg, RecordArg
from frtls.async_helpers import wrap_async_task
from frtls.dicts import get_seeded_dict
from frtls.doc.explanation import to_value_string
from frtls.doc.utils.rich import to_key_value_table
from frtls.exceptions import ArgValidationError, ArgsValidationError
from frtls.introspection.pkg_env import AppEnvironment
from frtls.tasks import PostprocessTask, Task, Tasks, TasksResult
from frtls.tasks.task_watcher import TaskWatchManager
from frtls.tasks.watchers.rich import RichTaskWatcher
from frtls.types.utils import is_instance_or_subclass
from rich.console import Console, ConsoleOptions, RenderResult
from tings.ting import SimpleTing, TingMeta


class FreckletInput(object):
    def __init__(self):

        self._input_sets: Dict[str, FreckletInputSet] = {}
        self._aliases: Dict[str, MutableMapping[Hashable, Any]] = {}
        self._processed_values: MutableMapping[str, Any] = {}

    @property
    def aliases(self) -> Mapping[str, Mapping[Hashable, Any]]:
        return self._aliases

    def add_alias(self, arg_name: str, alias: Hashable, value: Any):
        self._aliases.setdefault(arg_name, {})[alias] = value
        self.invalidate()

    def add_aliases(self, aliases: Mapping[str, Mapping[Hashable, Any]]):

        for arg_name, a in aliases.items():
            self._aliases.setdefault(arg_name, {}).update(a)

        self.invalidate()

    def clear_aliases(self) -> None:
        self._aliases.clear()

    @property
    def input_sets(self) -> Mapping[str, FreckletInputSet]:
        return self._input_sets

    def invalidate(self) -> None:
        self.get_merged_values.cache_clear()
        self._processed_values.clear()

    def add_processed_value(self, id: str, value: Any):

        if id in self._processed_values.keys():
            raise NotImplementedError()

        self._processed_values[id] = value

    def get_processed_value(self, id: str) -> Any:

        return self._processed_values.get(id, None)

    def var_set_ids(self) -> Iterable[str]:

        return self._input_sets.keys()

    def remove_input_set(self, id: str) -> FreckletInputSet:

        input_set = self._input_sets.pop(id)
        return input_set

    def add_input_set(self, input_set: FreckletInputSet) -> None:

        if input_set.id in self._input_sets.keys():
            print(input_set)
            raise NotImplementedError()

        self._input_sets[input_set.id] = input_set
        self.invalidate()

    def add_defaults(
        self,
        _id: Optional[str] = None,
        _priority: int = 0,
        _metadata: Mapping[str, Any] = None,
        **values: Any,
    ):

        input_set = FreckletInputSet(
            _id=_id,
            _type=FreckletInputType.DEFAULTS,
            _priority=_priority,
            _metadata=_metadata,
            **values,
        )
        self.add_input_set(input_set)

    def add_input_values(
        self,
        _id: Optional[str] = None,
        _priority: int = 0,
        _metadata: Mapping[str, Any] = None,
        **values: Any,
    ):

        input_set = FreckletInputSet(
            _id=_id,
            _type=FreckletInputType.INPUT,
            _priority=_priority,
            _metadata=_metadata,
            **values,
        )
        self.add_input_set(input_set)

    def add_constants(
        self,
        _id: Optional[str] = None,
        _priority: int = 0,
        _metadata: Mapping[str, Any] = None,
        **values: Any,
    ):

        input_set = FreckletInputSet(
            _id=_id,
            _type=FreckletInputType.CONSTANTS,
            _priority=_priority,
            _metadata=_metadata,
            **values,
        )
        self.add_input_set(input_set)

    @lru_cache()
    def get_merged_values(self) -> Mapping[str, Mapping[str, Any]]:

        result: Dict[str, Mapping[str, Any]] = {}
        value_list = sorted(self._input_sets.values())

        for input_set in reversed(value_list):
            for key, value in input_set.values.items():
                if key in result.keys():
                    continue

                if (
                    key in self.aliases.keys()
                    and isinstance(value, collections.abc.Hashable)
                    and value in self.aliases[key].keys()
                ):
                    alias = value
                    value = self.aliases[key][alias]
                    result[key] = {
                        "origin": input_set,
                        "raw_value": value,
                        "from_alias": alias,
                    }
                else:
                    result[key] = {"origin": input_set, "raw_value": value}

        return result

    async def get_vars(self, args: RecordArg) -> VarSet:

        result = {}
        merged_values = self.get_merged_values()

        errors = {}
        for arg_name, arg in args.childs.items():

            input_data = merged_values.get(arg_name, None)
            if input_data is None:
                raw_value: Any = None
                origin: Optional[FreckletInputSet] = None
            else:
                raw_value = input_data["raw_value"]
                origin = input_data["origin"]

            try:
                validated = arg.validate(raw_value, raise_exception=True)
            except ArgValidationError as ave:
                errors[arg_name] = ave

            if errors:
                raise ArgsValidationError(error_args=errors)

            var = Var(raw_value=raw_value, value=validated, origin=origin, arg=arg)
            result[arg_name] = var

        return VarSet(**result)

    def explain(self) -> FreckletInputExplanation:

        return FreckletInputExplanation(self)


class FreckletResult(TasksResult):
    def __init__(self, **kwargs):

        self._input: Optional[Mapping[str, Any]] = None
        super().__init__(**kwargs)

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:

        result_data: Mapping[str, Any] = self.explanation_data

        result = result_data["result"]

        if isinstance(result, collections.abc.Mapping):

            table = to_key_value_table(
                result_data["result"], show_headers=False, console=console, sort=True
            )
            yield table
        else:
            yield to_value_string(result)


class FreckletTask(Tasks):
    def __init__(self, **kwargs):

        self._preprocess_task: Optional[Task] = None
        self._main_task: Optional[Task] = None

        super().__init__(**kwargs)

    def set_preprocess_task(self, preprocess_task: Task) -> None:

        self._preprocess_task = preprocess_task

    async def run_children(self) -> None:

        if self._preprocess_task is not None:
            return NotImplemented

        async with create_task_group() as tg:
            for child in self._children.values():
                await tg.spawn(child.run_async)

        return None


class Frecklet(SimpleTing):
    def __init__(self, name: str, meta: TingMeta, init_values: Mapping[str, Any]):

        self._input_sets = FreckletInput()

        self._base_args: Optional[RecordArg] = None
        self._base_vars: Optional[VarSet] = None

        self._required_args: Optional[RecordArg] = None
        self._required_vars: Optional[VarSet] = None

        self._input_args: Optional[RecordArg] = None
        self._input_vars: Optional[VarSet] = None

        self._processed_args: Optional[RecordArg] = None
        self._processed_vars: Optional[Mapping[str, Any]] = None

        self._vars: Optional[Mapping[str, Any]] = None

        self._result_args: Optional[RecordArg] = None
        self._result: Optional[TasksResult] = None

        self._current_console: Optional[Console] = None

        super().__init__(name=name, meta=meta)
        wrap_async_task(self.init_frecklet, init_values)

    def _invalidate(self) -> None:

        self._base_args = None
        self._base_vars = None
        self._required_args = None
        self._required_vars = None
        self._input_args = None
        self._input_vars = None
        self._processed_args = None
        self._processed_vars = None
        self._vars = None
        self._result_args = None
        self._result = None

    async def init_frecklet(self, init_values: Mapping[str, Any]):
        pass

    @property
    def input_sets(self):
        return self._input_sets

    def requires(self) -> Mapping[str, Union[str, Mapping[str, Any]]]:
        return {"id": "string", "input": "dict"}

    def provides(self) -> Mapping[str, Union[str, Mapping[str, Any]]]:

        return {
            "id": "string",
            "input": "dict",
            "base_args": "dict",
            "required_args": "dict",
            "output": "dict",
        }

    async def retrieve(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        _id = requirements["id"]
        _input = requirements["input"]

        result = {}

        if "id" in value_names:
            result["id"] = _id

        if "input" in value_names:
            result["input"] = _input

        if "base_args" in value_names:
            result["base_args"] = await self._get_base_args()

        if "required_args" in value_names:
            result["required_args"] = await self._get_required_args()

        return result

    async def _get_base_args(self) -> RecordArg:

        if self._base_args is None:
            base_args = await self.get_base_args()
            if base_args is None:
                base_args = {}
            self._base_args = self.tingistry.arg_hive.create_record_arg(base_args)
        return self._base_args

    async def get_base_args(
        self
    ) -> Optional[Mapping[str, Union[str, Arg, Mapping[str, Any]]]]:
        return None

    async def get_base_vars(self) -> VarSet:

        if self._base_vars is None:
            self._base_vars = await self.input_sets.get_vars(
                await self._get_base_args()
            )
        return self._base_vars

    async def _get_required_args(self) -> RecordArg:

        if self._required_args is None:
            base_vars: VarSet = await self.get_base_vars()
            frecklet_args = await self.get_required_args(
                **base_vars.create_values_dict()
            )
            if frecklet_args is None:
                frecklet_args = {}
            # TODO: maybe check for duplicate keys?
            base_args = await self._get_base_args()
            merged_args = get_seeded_dict(
                base_args.childs, frecklet_args, merge_strategy="update"
            )

            self._required_args = self.tingistry.arg_hive.create_record_arg(merged_args)
        return self._required_args

    async def get_required_args(
        self, **base_vars: Any
    ) -> Optional[Mapping[str, Union[str, Arg, Mapping[str, Any]]]]:
        return None

    @property
    async def input_args(self) -> RecordArg:

        if self._input_args is None:
            required_args = await self._get_required_args()
            input_args = await self.get_input_args(required_args)
            self._input_args = self.tingistry.arg_hive.create_record_arg(input_args)
        return self._input_args

    async def get_input_args(
        self, required_args: RecordArg
    ) -> Mapping[str, Union[str, Arg, Mapping[str, Any]]]:

        return required_args.childs

    async def get_input_vars(self) -> VarSet:

        if self._input_vars is None:
            self._input_vars = await self.input_sets.get_vars(await self.input_args)
        return self._input_vars

    async def get_processed_vars(self) -> Mapping[str, Any]:

        if self._processed_vars is None:
            self._processed_vars = await self.process_vars(await self.get_input_vars())
        return self._processed_vars

    async def process_vars(self, input_vars: VarSet) -> Mapping[str, Any]:
        vars = input_vars.create_values_dict()
        return vars

    async def get_vars(self) -> Mapping[str, Any]:

        if self._vars is None:
            processed = await self.get_processed_vars()
            required_args = await self._get_required_args()
            self._vars = required_args.validate(processed, raise_exception=True)
        return self._vars

    async def get_msg(self) -> str:

        return f"executing frecklet '{self.name}'"

    async def get_frecklet_result(self) -> TasksResult:

        if self._result is None:
            self._result = await self.execute()
        return self._result

    def print(self, renderable):

        if self._current_console is not None:
            self._current_console.print(renderable)
        else:
            print(renderable)

    def explain(self) -> FreckletExplanation:

        return FreckletExplanation(self)

    def get_result_type(self) -> Type[FreckletResult]:

        return FreckletResult

    async def execute(self) -> FreckletResult:

        twm: TaskWatchManager = AppEnvironment().get_global("task_watcher")
        # twm = TaskWatchManager(typistry=self._bring._tingistry_obj.typistry)
        tlc = {
            "type": "rich",
            "base_topics": [BRING_TASKS_BASE_TOPIC],
            "console": console,
        }

        wid = twm.add_watcher(tlc)
        tw: RichTaskWatcher = twm.get_watcher(wid)  # type: ignore

        progress = tw.progress
        self._current_console = progress.console

        main_task = await self._create_task()
        if main_task is None:
            raise NotImplementedError()

        with progress:
            result: FreckletResult = await main_task.run_async()  # type: ignore
            twm.remove_watcher(wid)

        if not main_task.success:
            if main_task.error is None:
                # TODO: better exception class
                raise Exception(main_task.task_desc.get_failed_msg())
            else:
                raise main_task.error
        self._current_console = None

        return result

    async def _create_task(self) -> Optional[FreckletTask]:

        vars = await self.get_vars()

        # input_vars = copy.deepcopy(vars)
        # preprocess_task = await self.create_preprocessing_task(**input_vars)

        input_vars = copy.deepcopy(vars)
        _tasks_list = await self.create_processing_tasks(**input_vars)

        if is_instance_or_subclass(_tasks_list, Frecklet):
            tasks_list: Iterable[Union[Task, Frecklet]] = [_tasks_list]  # type: ignore
        elif is_instance_or_subclass(_tasks_list, Task):
            tasks_list = [_tasks_list]  # type: ignore
        else:
            tasks_list = _tasks_list  # type: ignore

        final_list: List[Task] = []
        for item in tasks_list:
            if is_instance_or_subclass(item, Frecklet):
                final_list.append(await item._create_task())  # type: ignore
            else:
                final_list.append(item)  # type: ignore

        msg = await self.get_msg()
        desc = BringTaskDesc(name=self.name, msg=msg)
        frecklet_task = FreckletTask(task_desc=desc, result_type=self.get_result_type())

        for t in final_list:
            frecklet_task.add_task(t)

        input_vars = copy.deepcopy(vars)
        postprocess_task = await self.create_postprocess_task(**input_vars)
        if postprocess_task:
            # pp_desc = BringTaskDesc(name="postprocessing", msg=f"postprocessing {self.name}")
            # postprocess_task.task_desc = pp_desc

            frecklet_task.set_postprocess_task(postprocess_task)

        return frecklet_task

    async def create_preprocessing_task(self, **input_vars: Any) -> Optional[Task]:
        return None

    @abstractmethod
    async def create_processing_tasks(
        self, **input_vars: Any
    ) -> Union[Task, Iterable[Task], "Frecklet", Iterable["Frecklet"]]:
        pass

    async def create_postprocess_task(
        self, **input_vars: Any
    ) -> Optional[PostprocessTask]:
        return None
