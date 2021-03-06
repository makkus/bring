# -*- coding: utf-8 -*-
import atexit
import collections
import logging
import os
import shutil
import tempfile
from abc import abstractmethod
from typing import Any, Iterable, Mapping, Optional, Union

from bring.defaults import BRING_WORKSPACE_FOLDER
from frkl.common.exceptions import FrklException
from frkl.common.filesystem import ensure_folder
from frkl.common.jinja_templating import replace_strings_in_obj
from frkl.common.strings import generate_valid_identifier
from frkl.tasks.task import Task
from frkl.tasks.task_desc import TaskDesc
from frkl.tasks.tasks import SimpleTasks
from frkl.types.plugins import PluginFactory
from tings.defaults import NO_VALUE_MARKER
from tings.ting import SimpleTing, TingMeta
from tings.tingistry import Tingistry


# if TYPE_CHECKING:
#     from bring.mogrify.parallel_pkg_merge import ParallelPkgMergeMogrifier


log = logging.getLogger("bring")


def assemble_mogrifiers(
    mogrifier_list: Iterable[Union[Mapping, str]],
    vars: Mapping[str, Any],
    args: Mapping[str, Any],
    task_desc: Optional[Mapping[str, Any]] = None,
) -> Iterable[Union[Mapping, Iterable[Mapping]]]:

    # TODO: validate vars
    if not vars and not args:
        _data: Iterable[Union[Mapping, str]] = mogrifier_list
    else:
        relevant_vars = {}
        for k, v in vars.items():
            if k in args.keys():
                relevant_vars[k] = v

        _data = replace_strings_in_obj(
            source_obj=mogrifier_list, replacement_dict=relevant_vars
        )

    mog_data = []
    for index, _mog in enumerate(_data):
        if isinstance(_mog, str):
            mog: Mapping[str, Any] = {"type": _mog, "_task_desc": task_desc}
            mog_data.append(mog)
        elif isinstance(_mog, collections.Mapping):
            mog = dict(_mog)
            if "_task_desc" not in mog.keys():
                mog["_task_desc"] = task_desc
            mog_data.append(mog)
        elif isinstance(_mog, collections.Iterable):
            mog_l: Iterable[Union[Mapping, Iterable[Mapping]]] = assemble_mogrifiers(
                mogrifier_list=_mog, vars=vars, args=args, task_desc=task_desc
            )
            mog_data.append(mog_l)
        else:
            raise FrklException(
                msg="Can't create transmogrifier.",
                reason=f"Invalid configuration type '{type(_mog)}': {_mog}",
            )

    return mog_data


class Mogrifiception(FrklException):
    def __init__(self, *args, mogrifier: "Mogrifier" = None, **kwargs):

        self._mogrifier = mogrifier

        super().__init__(*args, **kwargs)


class MogrifierException(FrklException):
    def __init__(self, mogrifier: "Mogrifier", **kwargs):

        self._mogrifier: "Mogrifier" = mogrifier

        super().__init__(**kwargs)

    @property
    def mogrifier(self):
        return self._mogrifier


class Mogrifier(Task, SimpleTing):
    """The base class to extend to implement a 'Mogrifier'.

    A mogrifier is one part of a pipeline, usually taking an input folder, along other arguments, and providing an
    output folder path as result. Which in turn is used by the subsequent Mogrifier as input, etc. There are a few special
    cases, for example the 'download' mogrifier which takes a url as input and provides a path to a file (not folder) as
    output, or the 'extract' mogrifier which takes an (archive) file as input and provides a folder path as output.

    Currently there is not much checking whether Mogrifiers that are put together fit each others input/output arguments,
    but that will be implemented at some stage. So, for now, it's the users responsibility to assemble mogrifier
    pipelines that make sense.

    An implementation of a Mogrifier can either provide class-level attributes '_provides' and '_requires', or implement
    the 'provides()' and 'requires()' instance or class level methods. This method will be only read once per Ting prototype
    (TODO: reference), so make sure to not process any calculated values in there.
    """

    def __init__(self, name: str, meta: TingMeta, **kwargs) -> None:

        self._tingistry_obj: Tingistry = meta.tingistry

        self._working_dir: Optional[str] = None
        SimpleTing.__init__(self, name=name, meta=meta)
        Task.__init__(self, **kwargs)

    @property
    def working_dir(self) -> Optional[str]:

        return self._working_dir

    @working_dir.setter
    def working_dir(self, working_dir: str) -> None:

        self._working_dir = working_dir

    def create_temp_dir(self, prefix=None):
        if prefix is None:
            prefix = self._name

        if not self.working_dir:
            raise FrklException(
                msg=f"Can't create temporary directory for mogrifier {self.name}",
                reason="Working dir not set for mogrifier",
            )

        tempdir = tempfile.mkdtemp(prefix=f"{prefix}_", dir=self.working_dir)
        return tempdir

    @abstractmethod
    def get_msg(self) -> str:

        pass


class SimpleMogrifier(Mogrifier):
    def __init__(self, name: str, meta: TingMeta, **kwargs):

        Mogrifier.__init__(self, name=name, meta=meta)

    def requires(self) -> Mapping[str, Union[str, Mapping[str, Any]]]:

        if not hasattr(self.__class__, "_requires"):
            raise FrklException(
                f"Error processing mogrifier '{self.name}'.",
                reason=f"No class attribute '_requires' availble for {self.__class__.__name__}. This is a bug.",
            )

        return self.__class__._requires  # type: ignore

    def provides(self) -> Mapping[str, Union[str, Mapping[str, Any]]]:

        if not hasattr(self.__class__, "_provides"):
            raise FrklException(
                f"Error processing mogrifier '{self.name}'.",
                reason=f"No class attribute '_provides' availble for {self.__class__.__name__}. This is a bug.",
            )

        return self.__class__._provides  # type: ignore

    async def execute_task(self) -> Any:

        result = await self.get_values(raise_exception=True)
        return result

    @property
    def user_input(self):

        result = {}
        for k, v in self.current_input.items():
            if v != NO_VALUE_MARKER:
                result[k] = v

        return result

    def get_user_input(self, key, default=None):

        return self.user_input.get(key, default)

    @abstractmethod
    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:
        pass

    async def retrieve(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        return await self.mogrify(*value_names, **requirements)


class EnvironmentStatus(object):
    def __init__(self, is_ready: bool, result: Optional[Mapping[str, Any]] = None):

        self._is_ready: bool = is_ready
        self._result: Optional[Mapping[str, Any]] = result

    @property
    def is_ready(self) -> bool:
        return self._is_ready

    @property
    def result(self) -> Optional[Mapping[str, Any]]:
        return self._result


# class TransmogrificatorResult(TasksResult):
#
#     def process_result(self, result_value: Mapping[str, TaskResult]):
#
#         print("PROCESSSSSSSS")
#         last_result = None
#         for result_value in result_value.values():
#             last_result = result_value
#
#         print(last_result)
#         return last_result


class Transmogrificator(SimpleTasks):
    def __init__(
        self,
        t_id: str,
        tingistry: "Tingistry",
        working_dir=None,
        is_root_transmogrifier: bool = True,
        **kwargs,
    ):

        self._id = t_id

        self._is_root_transmogrifier = is_root_transmogrifier

        if working_dir is None:
            working_dir = os.path.join(BRING_WORKSPACE_FOLDER, "pipelines", self._id)

        self._working_dir = working_dir
        ensure_folder(self._working_dir)

        debug = os.environ.get("DEBUG", "false")
        if debug.lower() != "true":

            def delete_workspace():
                shutil.rmtree(self._working_dir, ignore_errors=True)

            atexit.register(delete_workspace)

        self._tingistry = tingistry

        self._target_folder = os.path.join(BRING_WORKSPACE_FOLDER, "results", self._id)
        ensure_folder(os.path.dirname(self._target_folder))

        super().__init__(**kwargs)

        self._current: Optional[Mogrifier] = None
        self._last_item: Optional[Mogrifier] = None

    @property
    def working_dir(self):
        return self._working_dir

    async def add_mogrifier(self, mogrifier: Mogrifier) -> None:

        mogrifier.working_dir = self._working_dir
        if self._current is not None:
            mogrifier.set_requirements(self._current)

        await self.add_tasklet(mogrifier)  # type: ignore
        self._current = mogrifier
        self._last_item = self._current

    async def execute_tasklets(self, *tasklets: Task) -> Any:

        for child in tasklets:
            last_result = await child.run_async()
            if not last_result.success:
                # msg = "Error executing retrieval pipeline."
                # exc = MogrifierException(child, last_result.error, msg=msg)  # type: ignore
                # raise exc
                if last_result.error is None:
                    raise FrklException(
                        msg=f"Unknown error when executing '{child.__class__.__name__}' mogrifier."
                    )
                else:
                    raise last_result.error

    async def create_result_value(self, *tasklets: Task) -> Any:

        last_task: Task
        for t in tasklets:
            last_task = t

        return last_task.result.result_value

    # def explain_steps(self) -> StepsExplanation:
    #
    #     result = {}
    #
    #     for mogrifier in self._tasklets:
    #         result[mogrifier.name] = mogrifier.explain()  # type: ignore
    #
    #     # result.append(self._result_mogrifier.explain())  # type: ignore
    #
    #     return StepsExplanation(data=result)


class Transmogritory(SimpleTing):
    """Registry that holds all mogrify plugins.
    """

    def __init__(self, name: str, meta: TingMeta, _load_plugins_at_init: bool = True):

        self._tingistry_obj: Tingistry = meta.tingistry
        self._plugin_factory: Optional[PluginFactory] = None

        super().__init__(name=name, meta=meta)
        if _load_plugins_at_init:
            self.plugin_factory  # noqa

    def provides(self) -> Mapping[str, Union[str, Mapping[str, Any]]]:

        # TODO: make a real 'ting' out of this, probably not necessary though, it's really just a tingistry-global object
        return {}

    def requires(self) -> Mapping[str, Union[str, Mapping[str, Any]]]:

        return {}

    async def retrieve(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        return {}

    @property
    def plugin_factory(self) -> PluginFactory:

        if self._plugin_factory is not None:
            return self._plugin_factory

        self._plugin_factory = self._tingistry_obj.typistry.register_plugin_factory(
            "mogrifiers", Mogrifier, singleton=False, use_existing=False
        )

        for k, v in self._plugin_factory.plugin_type_map.items():
            self._tingistry_obj.register_prototing(f"bring.mogrify.plugins.{k}", v)

        return self._plugin_factory

    def create_mogrifier_ting(
        self,
        mogrify_plugin: str,
        pipeline_id: str,
        index: str,
        input_vals: Mapping[str, Any],
    ) -> Mogrifier:

        if mogrify_plugin not in self.plugin_factory.plugin_names:
            raise FrklException(
                msg="Can't create transmogrifier.",
                reason=f"No mogrify plugin '{mogrify_plugin}' available.",
            )

        # print("---")
        # print(input_vals)
        # print(vars)

        ting: Mogrifier = self._tingistry_obj.create_ting(  # type: ignore
            prototing=f"bring.mogrify.plugins.{mogrify_plugin}",
            ting_name=f"bring.runtime.pipelines.{pipeline_id}.{mogrify_plugin}_{index}",
        )
        ting.set_input(**input_vals)
        msg = ting.get_msg()
        td = TaskDesc(name=mogrify_plugin, msg=msg,)
        ting.task_desc = td

        return ting

    async def create_transmogrificator(
        self,
        data: Iterable[Union[Mapping[str, Any], str]],
        vars: Mapping[str, Any],
        args: Mapping[str, Any],
        task_desc: Optional[TaskDesc] = None,
        pipeline_id: Optional[str] = None,
        **kwargs,
    ) -> Transmogrificator:

        if pipeline_id is None:
            pipeline_id = generate_valid_identifier(
                prefix="pipe_", length_without_prefix=6
            )

        if task_desc is None:
            task_desc = TaskDesc(
                name=pipeline_id, msg=f"executing pipeline '{pipeline_id}'",
            )

        mogrifier_list = assemble_mogrifiers(mogrifier_list=data, vars=vars, args=args)

        transmogrificator = Transmogrificator(
            pipeline_id, self._tingistry_obj, task_desc=task_desc, **kwargs,
        )

        for index, _mog in enumerate(mogrifier_list):

            if isinstance(_mog, collections.Mapping):

                vals = dict(_mog)
                mogrify_plugin: Optional[str] = vals.pop("type", None)
                vals.pop("_task_desc")
                if not mogrify_plugin:
                    raise FrklException(
                        msg="Can't create transmogrificator.",
                        reason=f"No mogrifier type specified in config: {mogrifier_list}",
                    )

                ting: Mogrifier = self.create_mogrifier_ting(
                    mogrify_plugin=mogrify_plugin,
                    pipeline_id=pipeline_id,
                    index=str(index),
                    input_vals=vals,
                )

                await transmogrificator.add_mogrifier(ting)
            elif isinstance(_mog, collections.Iterable):

                raise NotImplementedError()
                #
                # tms = []
                # for j, child_list in enumerate(_mog):
                #
                #     tings = []
                #     guess_task_desc = None
                #     for k, _m in enumerate(child_list):
                #
                #         if guess_task_desc is None and "_task_desc" in _m.keys():
                #             guess_task_desc = _m["_task_desc"]
                #
                #         m = dict(_m)
                #         mogrify_plugin = m.pop("type", None)
                #         # sub_task_desc = m.pop("_task_desc", {})
                #         if not mogrify_plugin:
                #             raise FrklException(
                #                 msg="Can't create transmogrificator.",
                #                 reason=f"No mogrifier type specified in config: {mogrifier_list}",
                #             )
                #         t = self.create_mogrifier_ting(
                #             mogrify_plugin=mogrify_plugin,
                #             pipeline_id=pipeline_id,
                #             index=f"{index}_{j}_{k}",
                #             input_vals=m,
                #             basetopic=basetopic
                #         )
                #         tings.append(t)
                #
                #     tm_working_dir = os.path.join(
                #         transmogrificator.working_dir, f"{index}_{j}"
                #     )
                #     subtopic = f"{pipeline_id}.{index}_{j}"
                #     if guess_task_desc:
                #         td = BringTaskDesc(subtopic=subtopic)
                #         if "name" in guess_task_desc.keys():
                #             td.name = guess_task_desc["name"]
                #         if "msg" in guess_task_desc.keys():
                #             td.msg = guess_task_desc["msg"]
                #     else:
                #         td = BringTaskDesc(subtopic=subtopic)
                #
                #     tm = Transmogrificator(
                #         f"{pipeline_id}_{index}_{j}",
                #         self._tingistry_obj,
                #         task_desc=td,
                #         working_dir=tm_working_dir,
                #         is_root_transmogrifier=False,
                #     )
                #     for _m in tings:
                #         tm.add_mogrifier(_m)
                #
                #     tms.append(tm)
                #
                # merge = self.create_mogrifier_ting(
                #     mogrify_plugin="merge_folders",
                #     pipeline_id=pipeline_id,
                #     index=f"{index}_merge",
                #     input_vals={},
                #     basetopic=basetopic
                # )
                # p_ting: ParallelPkgMergeMogrifier = self.create_mogrifier_ting(  # type: ignore
                #     mogrify_plugin="parallel_pkg_merge",
                #     pipeline_id=pipeline_id,
                #     index=str(index),
                #     input_vals={"pipeline_id": pipeline_id, "merge": merge},
                #     basetopic=basetopic
                # )
                # p_ting.add_mogrificators(*tms)
                #
                # transmogrificator.add_mogrifier(p_ting)
                # p_ting.set_merge_task(merge)
            else:

                raise FrklException(
                    msg="Can't create transmogrificator.",
                    reason=f"Invalid configuration type '{type(_mog)}': {_mog}",
                )

        return transmogrificator
