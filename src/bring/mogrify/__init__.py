# -*- coding: utf-8 -*-
import atexit
import collections
import logging
import os
import shutil
import tempfile
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Optional, Union

from bring.defaults import BRING_WORKSPACE_FOLDER
from bring.display.explanation import StepsExplanation
from bring.utils import BringTaskDesc
from frtls.args.arg import RecordArg
from frtls.dicts import get_seeded_dict
from frtls.exceptions import FrklException
from frtls.files import ensure_folder
from frtls.tasks import Task, Tasks
from frtls.templating import replace_strings_in_obj
from frtls.types.plugins import TypistryPluginManager
from frtls.types.utils import generate_valid_identifier
from tings.defaults import NO_VALUE_MARKER
from tings.ting import SimpleTing, TingMeta
from tings.tingistry import Tingistry


if TYPE_CHECKING:
    from bring.mogrify.parallel_pkg_merge import ParallelPkgMergeMogrifier


log = logging.getLogger("bring")


def assemble_mogrifiers(
    mogrifier_list: Iterable[Union[Mapping, str]],
    vars: Mapping[str, Any],
    args: Mapping[str, Any],
    task_desc: Optional[Mapping[str, Any]] = None,
) -> Iterable[Union[Mapping, Iterable[Mapping]]]:

    # TODO: validate vars
    if not vars or not args:
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

    _plugin_type = "instance"

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

    def explain(self) -> str:

        return self.get_msg()


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

    async def execute(self) -> Any:

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


class CheckMogrifier(Mogrifier):
    """A mogrifier class that provides a 'is_ready' class that checks whether the required environment specified by the
    input arguments already exists.

    This is useful for example to check whether a package (or a version of a package) already exists at a target, and
    thus the pipeline up to this point can be skipped.

    When implementing such a method, make sure to not do any changes, just check the environment.
    """

    def __init__(self, name: str, meta: TingMeta, **kwargs):

        self._input_arg: Optional[RecordArg] = None
        self._result_arg: Optional[RecordArg] = None

        self._status: Optional[EnvironmentStatus] = None

        Mogrifier.__init__(self, name=name, meta=meta)

    async def execute(self) -> Any:

        result = await self.get_values(raise_exception=True)

        return result

    async def retrieve(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        return await self.mogrify(*value_names, **requirements)

    @abstractmethod
    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:
        pass

    @property
    def input_arg_obj(self) -> RecordArg:

        if self._input_arg is None:
            self._input_arg = self.tingistry.arg_hive.create_record_arg(
                self.input_args()
            )
        return self._input_arg

    @property
    def user_input(self):

        result = {}
        for k, v in self.current_input.items():
            if v != NO_VALUE_MARKER:
                result[k] = v

        vals = self.input_arg_obj.validate(result, raise_exception=True)

        return vals

    def get_user_input(self, key, default=None):

        return self.user_input.get(key, default)

    # async def get_status(self) -> Optional[EnvironmentStatus]:
    #
    #     if self._status is not None:
    #         return self._status
    #
    #     user_input = self.user_input
    #
    #     self._status = await self.check_status(**user_input)
    #     return self._status

    # @abstractmethod
    # async def check_status(self, **user_input: Any) -> Optional[EnvironmentStatus]:
    #
    #     pass

    def input_args(self) -> Mapping[str, Union[str, Mapping[str, Any]]]:

        if not hasattr(self.__class__, "_input_args"):
            raise FrklException(
                f"Error processing mogrifier '{self.name}'.",
                reason=f"No class attribute '_input_args' availble for {self.__class__.__name__}. This is a bug.",
            )

        return self.__class__._input_args  # type: ignore

    def pipeline_args(self) -> Mapping[str, Union[str, Mapping[str, Any]]]:

        if not hasattr(self.__class__, "_pipeline_args"):
            raise FrklException(
                f"Error processing mogrifier '{self.name}'.",
                reason=f"No class attribute '_pipeline_args' availble for {self.__class__.__name__}. This is a bug.",
            )

        return self.__class__._pipeline_args  # type: ignore

    def requires(self) -> Mapping[str, Union[str, Mapping[str, Any]]]:

        return get_seeded_dict(self.input_args(), self.pipeline_args())

    def check_output(self) -> Mapping[str, Union[str, Mapping[str, Any]]]:

        if not hasattr(self.__class__, "_check_output"):
            raise FrklException(
                f"Error processing mogrifier '{self.name}'.",
                reason=f"No class attribute '_check_output' availble for {self.__class__.__name__}. This is a bug.",
            )

        return self.__class__._check_output  # type: ignore

    def pipeline_output(self) -> Mapping[str, Union[str, Mapping[str, Any]]]:

        if not hasattr(self.__class__, "_pipeline_output"):
            raise FrklException(
                f"Error processing mogrifier '{self.name}'.",
                reason=f"No class attribute '_pipeline_output' availble for {self.__class__.__name__}. This is a bug.",
            )

        return self.__class__._pipeline_output  # type: ignore

    def provides(self) -> Mapping[str, Union[str, Mapping[str, Any]]]:

        return get_seeded_dict(self.check_output(), self.pipeline_output())


class Transmogrificator(Tasks):
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

        def delete_workspace():
            shutil.rmtree(self._working_dir, ignore_errors=True)

        debug = os.environ.get("DEBUG", "false")
        if debug.lower() != "true":
            atexit.register(delete_workspace)
        self._tingistry = tingistry

        self._target_folder = os.path.join(BRING_WORKSPACE_FOLDER, "results", self._id)
        ensure_folder(os.path.dirname(self._target_folder))

        self._result: Optional[Mapping[str, Any]] = None

        super().__init__(**kwargs)

        self._current: Optional[Mogrifier] = None
        self._last_item: Optional[Mogrifier] = None

    @property
    def working_dir(self):
        return self._working_dir

    def add_mogrifier(self, mogrifier: Mogrifier) -> None:

        mogrifier.working_dir = self._working_dir
        if self._current is not None:
            mogrifier.set_requirements(self._current)

        self.add_task(mogrifier)  # type: ignore
        self._current = mogrifier
        self._last_item = self._current

    # async def is_ready(self) -> bool:
    #
    #     if not issubclass(self._last_item.__class__, CheckMogrifier):
    #         return False
    #
    #     status: EnvironmentStatus = await self._last_item.get_status()  # type: ignore
    #
    #     if status is None:
    #         return False
    #     elif isinstance(status, bool):
    #         return status
    #     else:
    #         return status.is_ready

    async def transmogrify(self) -> Mapping[str, Any]:

        # if await self.is_ready():
        #     if self._result is None:
        #         raise Exception("No result value, this is a bug.")
        #     return self._result

        await self.run_async()
        self._result = self._last_item.current_state  # type: ignore
        return self._result  # type: ignore

    async def execute(self) -> Any:

        for child in self._children.values():
            await child.run_async()

    def explain_steps(self) -> StepsExplanation:

        result = {}

        for mogrifier in self._children.values():
            result[mogrifier.name] = mogrifier.explain()  # type: ignore

        # result.append(self._result_mogrifier.explain())  # type: ignore

        return StepsExplanation(steps_map=result)


class Transmogritory(SimpleTing):
    """Registry that holds all mogrify plugins.
    """

    def __init__(self, name: str, meta: TingMeta, _load_plugins_at_init: bool = True):

        self._tingistry_obj: Tingistry = meta.tingistry
        self._plugin_manager: Optional[TypistryPluginManager] = None

        super().__init__(name=name, meta=meta)
        if _load_plugins_at_init:
            self.plugin_manager  # noqa

    def provides(self) -> Mapping[str, Union[str, Mapping[str, Any]]]:

        # TODO: make a real 'ting' out of this, probably not necessary though, it's really just a tingistry-global object
        return {}

    def requires(self) -> Mapping[str, Union[str, Mapping[str, Any]]]:

        return {}

    async def retrieve(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        return {}

    @property
    def plugin_manager(self) -> TypistryPluginManager:

        if self._plugin_manager is not None:
            return self._plugin_manager

        self._plugin_manager = self._tingistry_obj.typistry.get_plugin_manager(
            "bring.mogrify.Mogrifier"
        )
        for k, v in self._plugin_manager._plugins.items():
            self._tingistry_obj.register_prototing(f"bring.mogrify.plugins.{k}", v)

        return self._plugin_manager

    def create_mogrifier_ting(
        self,
        mogrify_plugin: str,
        pipeline_id: str,
        index: str,
        input_vals: Mapping[str, Any],
        vars: Mapping[str, Any],
    ) -> Mogrifier:

        plugin: Mogrifier = self.plugin_manager.get_plugin(mogrify_plugin)
        if not plugin:
            raise FrklException(
                msg="Can't create transmogrifier.",
                reason=f"No mogrify plugin '{mogrify_plugin}' available.",
            )

        ting: Mogrifier = self._tingistry_obj.create_ting(  # type: ignore
            prototing=f"bring.mogrify.plugins.{mogrify_plugin}",
            ting_name=f"bring.mogrify.pipelines.{pipeline_id}.{mogrify_plugin}_{index}",
        )
        ting.set_input(**input_vals)
        msg = ting.get_msg()
        td = BringTaskDesc(name=mogrify_plugin, msg=msg)
        ting.task_desc = td

        return ting

    def create_transmogrificator(
        self,
        data: Iterable[Union[Mapping[str, Any], str]],
        vars: Mapping[str, Any],
        args: Mapping[str, Any],
        task_desc: Optional[BringTaskDesc] = None,
        # target: Union[str, Path, Mapping[str, Any]] = None,
        **kwargs,
    ) -> Transmogrificator:

        pipeline_id = generate_valid_identifier(prefix="pipe_", length_without_prefix=6)

        if task_desc is None:
            task_desc = BringTaskDesc(
                name=pipeline_id, msg=f"executing pipeline '{pipeline_id}'"
            )

        mogrifier_list = assemble_mogrifiers(mogrifier_list=data, vars=vars, args=args)

        transmogrificator = Transmogrificator(
            pipeline_id,
            self._tingistry_obj,
            task_desc=task_desc,
            # target=target,
            **kwargs,
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
                    vars=vars,
                )

                transmogrificator.add_mogrifier(ting)
            elif isinstance(_mog, collections.Iterable):

                tms = []
                for j, child_list in enumerate(_mog):

                    tings = []
                    guess_task_desc = None
                    for k, _m in enumerate(child_list):

                        if guess_task_desc is None and "_task_desc" in _m.keys():
                            guess_task_desc = _m["_task_desc"]

                        m = dict(_m)
                        mogrify_plugin = m.pop("type", None)
                        # sub_task_desc = m.pop("_task_desc", {})
                        if not mogrify_plugin:
                            raise FrklException(
                                msg="Can't create transmogrificator.",
                                reason=f"No mogrifier type specified in config: {mogrifier_list}",
                            )
                        t = self.create_mogrifier_ting(
                            mogrify_plugin=mogrify_plugin,
                            pipeline_id=pipeline_id,
                            index=f"{index}_{j}_{k}",
                            input_vals=m,
                            vars=vars,
                        )
                        tings.append(t)

                    tm_working_dir = os.path.join(
                        transmogrificator.working_dir, f"{index}_{j}"
                    )
                    if guess_task_desc:
                        td = BringTaskDesc()
                        if "name" in guess_task_desc.keys():
                            td.name = guess_task_desc["name"]
                        if "msg" in guess_task_desc.keys():
                            td.msg = guess_task_desc["msg"]
                    else:
                        td = BringTaskDesc()

                    tm = Transmogrificator(
                        f"{pipeline_id}_{index}_{j}",
                        self._tingistry_obj,
                        task_desc=td,
                        working_dir=tm_working_dir,
                        is_root_transmogrifier=False,
                    )
                    for _m in tings:
                        tm.add_mogrifier(_m)

                    tms.append(tm)

                merge = self.create_mogrifier_ting(
                    mogrify_plugin="merge_folders",
                    pipeline_id=pipeline_id,
                    index=f"{index}_merge",
                    input_vals={},
                    vars=vars,
                )
                p_ting: ParallelPkgMergeMogrifier = self.create_mogrifier_ting(  # type: ignore
                    mogrify_plugin="parallel_pkg_merge",
                    pipeline_id=pipeline_id,
                    index=str(index),
                    input_vals={"pipeline_id": pipeline_id, "merge": merge},
                    vars=vars,
                )
                p_ting.add_mogrificators(*tms)

                transmogrificator.add_mogrifier(p_ting)
                p_ting.set_merge_task(merge)
            else:

                raise FrklException(
                    msg="Can't create transmogrificator.",
                    reason=f"Invalid configuration type '{type(_mog)}': {_mog}",
                )

        return transmogrificator
