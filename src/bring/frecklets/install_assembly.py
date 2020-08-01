# -*- coding: utf-8 -*-
import collections
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Union

from anyio import create_task_group
from bring.bring import Bring
from bring.defaults import BRING_DEFAULT_MAX_PARALLEL_TASKS
from bring.frecklets import BringFrecklet, parse_target_data
from bring.utils import parse_pkg_string
from freckles.core.frecklet import FreckletVar
from frkl.args.arg import Arg, RecordArg
from frkl.common.exceptions import FrklException
from frkl.common.formats import VALUE_TYPE
from frkl.common.formats.auto import AutoInput
from frkl.common.iterables import ensure_iterable
from frkl.common.regex import create_var_regex, find_var_names_in_obj
from frkl.targets.local_folder import FolderMergeResult, TrackingLocalFolder
from frkl.tasks.task import PostprocessTask, Task
from frkl.tasks.task_desc import TaskDesc
from frkl.tasks.tasks import ParallelTasksAsync, Tasks


# if TYPE_CHECKING:
#     from freckles.core.frecklet import FreckletVar

BRING_IN_DEFAULT_DELIMITER = create_var_regex()


class BringAssembly(object):
    @classmethod
    async def create_from_string(cls, bring: Bring, config: Union[str, Path]):

        inp = AutoInput(config)
        content = await inp.get_content_async()
        value_type = await inp.get_value_type_async()

        if value_type == VALUE_TYPE.mapping:
            pkgs: Iterable = content["pkgs"]
        elif value_type == VALUE_TYPE.iterable:
            pkgs = content
        else:
            raise FrklException(
                msg=f"Can't create BringAssembly from config: {config}",
                reason=f"Invalid value type: {value_type}",
            )

        return BringAssembly(bring, *pkgs)

    def __init__(self, bring: Bring, *pkgs: Union[str, Mapping[str, Any]]):

        self._bring: Bring = bring
        self._pkg_data: List[Mapping[str, Mapping[str, Any]]] = []
        self._pkg_map: Optional[MutableMapping[str, MutableMapping[str, Any]]] = None
        _pkg_data: Iterable[Union[MutableMapping[str, Any], str]] = ensure_iterable(pkgs)  # type: ignore
        for pkg_data in _pkg_data:
            if isinstance(pkg_data, str):
                pkg_name, pkg_index = parse_pkg_string(pkg_data)
                if not pkg_index:
                    raise ValueError(
                        f"Invalid pkg item, no 'index' in package name: {pkg_data}"
                    )
                p = {"name": pkg_name, "index": pkg_index}
                self._pkg_data.append({"pkg": p})
            elif isinstance(pkg_data, collections.abc.Mapping):
                if "pkg" not in pkg_data.keys():
                    raise ValueError(f"Invalid package item, no 'pkg' key: {pkg_data}")
                pkg: Union[str, Mapping[str, Any]] = pkg_data["pkg"]
                if isinstance(pkg, str):
                    pkg_name, pkg_index = parse_pkg_string(pkg)
                    if not pkg_index:
                        raise ValueError(
                            f"Invalid pkg item, no 'index' in package name: {pkg_data}"
                        )
                    pkg = {"name": pkg_name, "index": pkg_index}
                    pkg_data["pkg"] = pkg

                if "name" not in pkg.keys():
                    raise ValueError(f"Invalid pkg item, no 'name' key: {pkg_data}")
                if "index" not in pkg.keys():
                    raise ValueError(f"Invalid pkg item, no 'index' key: {pkg_data}")
                if not pkg_data.get("vars", None):
                    pkg_data["vars"] = {}

                self._pkg_data.append(pkg_data)

        # TODO: validate

    @property
    def pkg_data(self) -> Iterable[Mapping[str, Mapping[str, Any]]]:
        return self._pkg_data

    async def get_pkg_map(self) -> Mapping[str, Any]:

        if self._pkg_map is not None:
            return self._pkg_map

        self._pkg_map = {}

        async def get_pkg(_pkg_data: MutableMapping[str, Any]):
            _pkg = await self._bring.get_pkg(
                name=_pkg_data["pkg"]["name"], index=_pkg_data["pkg"]["index"]
            )
            self._pkg_map[f"{_pkg_data['pkg']['name']}.{_pkg_data['pkg']['index']}"] = {"pkg": _pkg, "config": _pkg_data}  # type: ignore

        async with create_task_group() as tg:
            for pkg_data in self._pkg_data:
                await tg.spawn(get_pkg, pkg_data)

        missing = []
        for id, details in self._pkg_map.items():
            if details["pkg"] is None:
                missing.append(id)
        if missing:
            raise FrklException(
                msg="Can't assemble package list.",
                reason=f"No packages found for: {', '.join(missing)}",
            )

        return self._pkg_map  # type: ignore

    async def get_required_args(
        self,
    ) -> Mapping[str, Union[str, Arg, Mapping[str, Any]]]:

        # TODO: parse file for arg definitions
        args_dict: Dict[str, Union[str, Arg, Mapping[str, Any]]] = {}

        var_names = find_var_names_in_obj(
            self._pkg_data, delimiter=BRING_IN_DEFAULT_DELIMITER
        )

        if not var_names:
            return {}

        result: Dict[str, Union[str, Arg, Mapping[str, Any]]] = {}
        for var_name in var_names:
            if var_name in args_dict.keys():
                result[var_name] = args_dict[var_name]
            else:
                result[var_name] = {
                    "type": "any",
                    "required": True,
                    "doc": f"value for '{var_name}'",
                }

        return result


class InstallAssemblyPostprocessTask(PostprocessTask):
    def __init__(
        self,
        previous_task: Task,
        target: Optional[str] = None,
        target_config: Optional[Mapping[str, Any]] = None,
        **kwargs,
    ):

        self._target: Optional[str] = target
        self._target_config: Optional[Mapping[str, Any]] = target_config
        self._target_details = parse_target_data(
            self._target, self._target_config, temp_folder_prefix="install_pkgs_"
        )

        super().__init__(previous_task=previous_task, **kwargs)

    async def postprocess(self, task: Task) -> Any:

        result = task.result.result_value

        folders: Dict[str, Mapping[str, Any]] = {}
        for k, v in result.items():

            folder_path = v.result_value["folder_path"]
            metadata = v.result_value["item_metadata"]
            folders[folder_path] = metadata

        _target_path = self._target_details["target_path"]
        # _target_msg = self._target_details["target_msg"]
        _merge_config = self._target_details["target_config"]

        target_folder = TrackingLocalFolder(path=_target_path)
        merge_result = FolderMergeResult(target=target_folder)

        for source_folder, _item_metadata in folders.items():
            result = await target_folder.merge_folders(
                source_folder, item_metadata=_item_metadata, merge_config=_merge_config
            )
            merge_result.add_merge_result(result)

        return {
            "folder_path": _target_path,
            "target": target_folder,
            "merge_result": merge_result,
        }


class ParallelAssemblyTask(Tasks):
    def __init__(
        self,
        bring: Bring,
        assembly: BringAssembly,
        target: Optional[str] = None,
        target_config: Optional[Mapping[str, Any]] = None,
        max_parallel_tasks: Optional[int] = None,
        task_desc: Optional[TaskDesc] = None,
    ):

        self._bring: Bring = bring
        self._assembly: BringAssembly = assembly

        self._target: Optional[str] = target
        self._target_config: Optional[Mapping[str, Any]] = target_config
        self._max_parallel_tasks: Optional[int] = max_parallel_tasks

        if task_desc is None:
            task_desc = TaskDesc(
                name="install pkg assembly", msg="installing package assembly"
            )

        super().__init__(task_desc=task_desc)

    async def initialize_tasklets(self) -> None:

        self._tasklets: List[Task] = []

        task_desc = TaskDesc(
            name="retrieve pkgs", msg="retrieve package files in parallel"
        )

        install_tasks = ParallelTasksAsync(
            task_desc=task_desc, max_parallel_tasks=self._max_parallel_tasks
        )
        for pkg_config in self._assembly.pkg_data:
            pkg = pkg_config["pkg"]
            pkg_name = pkg["name"]
            pkg_index = pkg["index"]

            vars = pkg_config.get("vars", {})
            # transform = pkg_config.get("tarnsform", None)
            frecklet_config = {"type": "install_pkg", "id": f"{pkg_name}.{pkg_index}"}

            frecklet = await self._bring.freckles.create_frecklet(frecklet_config)

            input_values = dict(vars)
            input_values.update({"pkg_name": pkg_name, "pkg_index": pkg_index})
            input_values["target"] = None
            await frecklet.add_input_set(**input_values)

            task = await frecklet.get_frecklet_task()
            await install_tasks.add_tasklet(task)

        await self.add_tasklet(install_tasks)

        task_desc = TaskDesc(name="merge packages", msg="merging packages into target")
        postprocess_task = InstallAssemblyPostprocessTask(
            previous_task=install_tasks,
            target=self._target,
            target_config=self._target_config,
            task_desc=task_desc,
        )
        await self.add_tasklet(postprocess_task)

    async def execute_tasklets(self, *tasklets: Task) -> None:

        for t in tasklets:
            await t.run_async()

    async def create_result_value(self, *tasklets: Task) -> Any:

        return tasklets[-1].result


class BringInstallAssemblyFrecklet(BringFrecklet):
    def get_required_base_args(
        self,
    ) -> Optional[Union[RecordArg, Mapping[str, Mapping[str, Any]]]]:

        args = {
            "data": {
                "type": "any",
                "doc": "a list of packages, or path to a file containing it",
            },
            "target": {"type": "string", "doc": "the target folder", "required": False},
            "target_config": {
                "type": "dict",
                "doc": "(optional) target configuration",
                # TODO: reference
                "required": False,
            },
        }

        return args  # type: ignore

    def get_msg(self) -> str:

        return "installing package assembly"

    async def input_received(self, **input_vars: FreckletVar) -> Any:

        if self.current_amount_of_inputs == 1:
            return None

        data = input_vars["data"].value
        bring_assembly = await BringAssembly.create_from_string(self._bring, data)

        self.set_processed_input("assembly", bring_assembly)

        args = await bring_assembly.get_required_args()

        return self._bring.arg_hive.create_record_arg(childs=args)

    async def _create_frecklet_task(self, **input_values: Any) -> Task:

        target = input_values.pop("target", None)
        target_config = input_values.pop("target_config", None)

        assembly: BringAssembly = self.get_processed_input("assembly")

        ft = ParallelAssemblyTask(
            bring=self._bring,
            assembly=assembly,
            target=target,
            target_config=target_config,
            max_parallel_tasks=BRING_DEFAULT_MAX_PARALLEL_TASKS,
        )
        return ft
