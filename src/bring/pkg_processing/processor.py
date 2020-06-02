# -*- coding: utf-8 -*-
import copy
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

from bring.interfaces.cli import console
from bring.mogrify import Transmogrificator
from bring.pkg_index.pkg import PkgTing
from bring.pkg_processing.explanations import ProcessInfo, ProcessResult, ProcessVars
from bring.pkg_processing.vars import ArgsHolder, VarSet, VarSetType
from frtls.args.arg import Arg, RecordArg
from frtls.args.hive import ArgHive
from frtls.async_helpers import wrap_async_task
from frtls.dicts import get_seeded_dict
from frtls.doc.explanation import Explanation
from frtls.doc.explanation.steps import StepsExplanation
from frtls.exceptions import FrklException
from frtls.introspection.pkg_env import AppEnvironment
from frtls.tasks import Tasks
from frtls.tasks.task_watcher import TaskWatchManager
from frtls.types.utils import is_instance_or_subclass


if TYPE_CHECKING:
    from bring.bring import Bring

log = logging.getLogger("bring")


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
    async def _create_tasks(self) -> Any:

        pass

    async def process(self) -> Any:

        tasks: Transmogrificator = await self._create_tasks()
        topic = tasks.task_desc._topic

        twm: TaskWatchManager = AppEnvironment().get_global("task_watcher")
        # twm = TaskWatchManager(typistry=self._bring._tingistry_obj.typistry)
        tlc = {
            "type": "rich",
            "base_topics": [topic],
            "console": console,
            "tasks": tasks,
        }

        wid = twm.add_watcher(tlc)
        tw = twm.get_watcher(wid)

        progress = tw.progress

        with progress:
            await tasks.run_async()

        twm.remove_watcher(wid)

        result = tasks.get_result()

        if is_instance_or_subclass(result, Explanation):
            self._result = result
        else:
            self._result = ProcessResult(vars=self._args_holder.vars, result=result)
        return self._result

    def explain(self) -> "ProcessInfo":

        pi = ProcessInfo(self)
        return pi

    def explain_vars(
        self, show_title: bool = True, as_table: bool = True
    ) -> ProcessVars:

        return self._args_holder.explain(show_title=show_title, as_table=as_table)

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

    async def _create_tasks(self) -> Tasks:

        if self._result is not None:
            raise FrklException(msg="Can't run pkg processor.", reason="Already ran.")

        # await self.get_processed_input_async()
        # args = await self.get_input_args()
        # args.validate(self.get_current_input(), raise_exception=True)

        tm: Transmogrificator = await self.get_transmogrificator()
        return tm
        # result = await tm.transmogrify()
        # return result

    async def explain_tasks(self) -> StepsExplanation:

        tm: Transmogrificator = await self.get_transmogrificator()

        steps = tm.explain_steps()
        return steps

    async def get_msg(self) -> str:

        msg = await super(PkgProcessor, self).get_msg()
        pkg = await self.get_pkg()
        return msg + f" with package '{pkg.pkg_id}'"
