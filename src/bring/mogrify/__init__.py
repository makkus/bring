# -*- coding: utf-8 -*-
import atexit
import collections
import os
import shutil
import tempfile
from abc import abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Iterable, Mapping, Optional, Union

from bring.defaults import BRING_WORKSPACE_FOLDER
from frtls.exceptions import FrklException
from frtls.files import ensure_folder
from frtls.tasks import Task, TaskDesc, Tasks
from frtls.templating import replace_strings_in_obj
from frtls.types.utils import generate_valid_identifier
from tings.ting import SimpleTing


if TYPE_CHECKING:
    from bring.bring import Bring
    from bring.mogrify.parallel_pkg_merge import ParallelPkgMergeMogrifier


def assemble_mogrifiers(
    mogrifier_list: Iterable[Union[Mapping, str]],
    vars: Mapping[str, Any],
    args: Mapping[str, Any],
    task_desc: Mapping[str, Any] = None,
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
    def __init__(
        self, name: str, meta: Optional[Mapping[str, Any]] = None, **kwargs
    ) -> None:

        self._mogrify_result: Optional[Mapping[str, Any]] = None

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
    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:
        pass

    async def retrieve(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        if self._mogrify_result is None:
            self._mogrify_result = await self.mogrify(*value_names, **requirements)

        return self._mogrify_result


class SimpleMogrifier(Mogrifier):
    def __init__(self, name: str, meta: Optional[Mapping[str, Any]], **kwargs):

        Mogrifier.__init__(self, name=name, meta=meta)
        # SingleTaskAsync.__init__(self, self.get_values, **kwargs)
        self._func: Callable = self.get_values

    async def execute(self) -> Any:

        result = await self._func()

        return result


class Transmogrificator(Tasks):
    def __init__(
        self,
        t_id: str,
        bring: "Bring",
        *transmogrifiers: Mogrifier,
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

        atexit.register(delete_workspace)
        self._bring = bring

        super().__init__(**kwargs)

        self._current: Optional[Mogrifier] = None
        self._last_item: Optional[Mogrifier] = None

        self._mogrify_result: Optional[Mapping[str, Any]] = None
        self._result_moved: bool = False

        for tm in transmogrifiers:
            self.add_mogrifier(tm)

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

    async def transmogrify(self) -> Mapping[str, Any]:

        await self.run_async()

        result = self._last_item.current_state  # type: ignore

        if not self._is_root_transmogrifier:
            return result

        result_folder = result["folder_path"]
        self._mogrify_result = {
            "folder_path": os.path.join(BRING_WORKSPACE_FOLDER, "results", self._id)
        }

        shutil.move(result_folder, self._mogrify_result["folder_path"])
        shutil.rmtree(self.working_dir)

        return self._mogrify_result

    @property
    def result_path(self) -> str:

        if self._result_moved:
            raise FrklException(
                msg="Can't return result path for transmogrifier.",
                reason=f"Result already moved to a target location and result folder deleted.",
            )

        return self._mogrify_result["folder_path"]  # type: ignore

    def set_target(
        self, target: Union[str, Path], delete_pipeline_folder: bool = True
    ) -> str:

        if self._result_moved:
            raise FrklException(
                msg="Can't return result path for transmogrifier.",
                reason=f"Result already moved to a target location and result folder deleted.",
            )

        folder_path = self._mogrify_result["folder_path"]  # type: ignore

        if isinstance(target, Path):
            _target = target.resolve().as_posix()
        else:
            _target = os.path.expanduser(target)

        ensure_folder(os.path.dirname(_target))

        if not delete_pipeline_folder:
            shutil.copy2(folder_path, _target)
        else:
            shutil.move(folder_path, _target)
            self._result_moved = True

        return _target

    async def execute(self) -> Any:

        for child in self._children.values():
            await child.run_async()


class Transmogritory(object):
    def __init__(self, bring: "Bring"):

        self._bring = bring
        self._plugin_manager = self._bring.get_plugin_manager(
            "bring.mogrify.Mogrifier", plugin_type="instance"
        )
        for k, v in self._plugin_manager._plugins.items():
            self._bring.register_prototing(f"bring.mogrify.plugins.{k}", v)

    def create_mogrifier_ting(
        self,
        mogrify_plugin: str,
        pipeline_id: str,
        index: str,
        input_vals: Mapping[str, Any],
    ) -> Mogrifier:

        plugin: Mogrifier = self._plugin_manager.get_plugin(mogrify_plugin)
        if not plugin:
            raise FrklException(
                msg="Can't create transmogrifier.",
                reason=f"No mogrify plugin '{mogrify_plugin}' available.",
            )

        ting: Mogrifier = self._bring.create_ting(
            prototing=f"bring.mogrify.plugins.{mogrify_plugin}",
            ting_name=f"bring.mogrify.pipelines.{pipeline_id}.{mogrify_plugin}_{index}",
        )  # type: ignore
        ting.input.set_values(**input_vals)
        msg = ting.get_msg()
        ting.task_desc.name = mogrify_plugin
        ting.task_desc.msg = msg

        return ting

    def create_transmogrificator(
        self,
        data: Iterable[Union[Mapping, str]],
        vars: Mapping[str, Any],
        args: Mapping[str, Any],
        task_desc: Optional[TaskDesc] = None,
        **kwargs,
    ) -> Transmogrificator:

        pipeline_id = generate_valid_identifier(prefix="pipe_", length_without_prefix=6)

        if task_desc is None:
            task_desc = TaskDesc(
                name=pipeline_id, msg=f"executing pipeline '{pipeline_id}'"
            )

        mogrifier_list = assemble_mogrifiers(mogrifier_list=data, vars=vars, args=args)

        transmogrificator = Transmogrificator(
            pipeline_id, self._bring, desc=task_desc, **kwargs
        )

        for index, _mog in enumerate(mogrifier_list):

            if isinstance(_mog, collections.Mapping):

                vals = dict(_mog)
                mogrify_plugin: Optional[str] = vals.pop("type", None)
                if not mogrify_plugin:
                    raise FrklException(
                        msg="Can't create transmogrificator.",
                        reason=f"No mogrifier type specified in config: {mogrifier_list}",
                    )

                ting: Mogrifier = self.create_mogrifier_ting(
                    mogrify_plugin=mogrify_plugin,
                    pipeline_id=pipeline_id,
                    index=str(index),
                    input_vals=_mog,
                )

                transmogrificator.add_mogrifier(ting)
            elif isinstance(_mog, collections.Iterable):

                tms = []
                for j, child_list in enumerate(_mog):

                    tings = []
                    for k, m in enumerate(child_list):
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
                        )
                        tings.append(t)

                    td = TaskDesc(
                        # name=f"{sub_task_desc['name']}",
                        # msg=f"retrieving {sub_task_desc['name']}",
                    )
                    tm_working_dir = os.path.join(
                        transmogrificator.working_dir, f"{index}_{j}"
                    )
                    tm = Transmogrificator(
                        f"{pipeline_id}_{index}_{j}",
                        self._bring,
                        *tings,
                        desc=td,
                        working_dir=tm_working_dir,
                        is_root_transmogrifier=False,
                    )

                    tms.append(tm)

                merge = self.create_mogrifier_ting(
                    mogrify_plugin="merge",
                    pipeline_id=pipeline_id,
                    index=f"{index}_merge",
                    input_vals={},
                )
                p_ting: ParallelPkgMergeMogrifier = self.create_mogrifier_ting(
                    mogrify_plugin="parallel_pkg_merge",
                    pipeline_id=pipeline_id,
                    index=str(index),
                    input_vals={"pipeline_id": pipeline_id, "merge": merge},
                )  # type: ignore
                p_ting.add_mogrificators(*tms)

                transmogrificator.add_mogrifier(p_ting)
                p_ting.set_merge_task(merge)
            else:

                raise FrklException(
                    msg="Can't create transmogrificator.",
                    reason=f"Invalid configuration type '{type(_mog)}': {_mog}",
                )

        return transmogrificator
