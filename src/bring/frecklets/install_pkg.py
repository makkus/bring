# -*- coding: utf-8 -*-
import collections
from typing import TYPE_CHECKING, Any, List, Mapping, MutableMapping, Optional, Union

from bring.bring import Bring
from bring.defaults import BRING_RESULTS_FOLDER
from bring.mogrify import Transmogrificator
from bring.pkg_index.pkg import PkgTing
from freckles.core.defaults import FRECKLES_EVENTS_TOPIC_NAME
from freckles.core.frecklet import (
    Frecklet,
    FreckletException,
    FreckletResult,
    FreckletVar,
)
from frkl.args.arg import RecordArg
from frkl.common.filesystem import create_temp_dir
from frkl.common.regex import create_var_regex
from frkl.targets.local_folder import TrackingLocalFolder
from frkl.tasks.exceptions import FrklTaskRunException
from frkl.tasks.task import Task, TaskResult
from frkl.tasks.task_desc import TaskDesc
from frkl.tasks.tasks import Tasks
from sortedcontainers import SortedDict
from tings.ting import TingMeta


if TYPE_CHECKING:
    from rich.console import ConsoleOptions, Console, RenderResult


BRING_IN_DEFAULT_DELIMITER = create_var_regex()
TEMP_DIR_MARKER = "__temp__"


def parse_target_data(
    target: Optional[Union[str]] = None,
    target_config: Optional[Mapping] = None,
    temp_folder_prefix: Optional[str] = None,
):

    if not target or target.lower() == TEMP_DIR_MARKER:
        _target_path: str = create_temp_dir(
            prefix=temp_folder_prefix, parent_dir=BRING_RESULTS_FOLDER
        )
        _target_msg: str = "new temporary folder"
        _is_temp: bool = True
    else:
        _target_path = target
        _target_msg = f"folder '{_target_path}'"
        _is_temp = False

    if not isinstance(_target_path, str):
        raise TypeError(f"Invalid type for 'target' value: {type(target)}")

    if target_config is None:
        _target_data: MutableMapping[str, Any] = {}
    else:
        if not isinstance(target_config, collections.abc.Mapping):
            raise TypeError(
                f"Invalid type for target_config value '{type(target_config)}'"
            )
        _target_data = dict(target_config)

    if "write_metadata" not in _target_data.keys():
        if _is_temp:
            _target_data["write_metadata"] = False
        else:
            _target_data["write_metadata"] = True

    if _target_data["write_metadata"] is None:
        if _is_temp:
            _target_data["write_metadata"] = False
        else:
            _target_data["write_metadata"] = True

    return {
        "target_config": _target_data,
        "target_path": _target_path,
        "target_msg": _target_msg,
        "is_temp": _is_temp,
    }


class MoveToTargetTask(Task):
    def __init__(
        self,
        prior_task_result: TaskResult,
        target: Optional[str] = None,
        target_config: Optional[Mapping[str, Any]] = None,
        item_metadata: Optional[Mapping[str, Any]] = None,
        basetopic: Optional[str] = None,
    ):

        self._prior_task_result: TaskResult = prior_task_result

        self._target: Optional[str] = target
        self._target_config: Optional[Mapping[str, Any]] = target_config
        self._item_metadata: Optional[Mapping[str, Any]] = item_metadata

        self._target_details = parse_target_data(
            self._target, self._target_config, temp_folder_prefix="move_to_target_"
        )

        task_desc = TaskDesc(
            name="merge files",
            msg=f"merging prepared files into {self._target_details['target_msg']}",
            basetopic=basetopic,
        )

        super().__init__(task_desc=task_desc)

    async def execute_task(self) -> Any:

        if not self._prior_task_result.success:
            raise FrklTaskRunException(task=self, msg="Can't move files to target folder.", reason="Required previous job did not finish successfully.", run_exception=self._prior_task_result.error)  # type: ignore

        source_folder = self._prior_task_result.result_value["folder_path"]

        _target_path = self._target_details["target_path"]
        # _target_msg = self._target_details["target_msg"]
        _merge_config = self._target_details["target_config"]

        if self._item_metadata is None:
            _item_metadata = SortedDict()
        else:
            _item_metadata = SortedDict(self._item_metadata)

        item_metadata = {"pkg": _item_metadata}

        target_folder = TrackingLocalFolder(path=_target_path)
        result = await target_folder.merge_folders(
            source_folder, item_metadata=item_metadata, merge_config=_merge_config
        )

        return {
            "target": _target_path,
            "merge_result": result,
            "item_metadata": item_metadata,
        }


class BringInstallTask(Tasks):
    def __init__(
        self,
        pkg: PkgTing,
        input_values: Optional[Mapping[str, Any]] = None,
        target: Optional[str] = None,
        target_config: Optional[Mapping[str, Any]] = None,
        basetopic: Optional[str] = None,
    ):

        self._pkg: PkgTing = pkg
        if input_values is None:
            input_values = {}
        self._input_values: Mapping[str, Any] = input_values
        self._target: Optional[str] = target
        self._target_config: Optional[Mapping[str, Any]] = target_config

        self._basetopic: Optional[str] = basetopic
        task_desc = TaskDesc(
            name=self._pkg.name,
            msg=f"installing pkg '{self._pkg.name}'",
            basetopic=self._basetopic,
        )

        super().__init__(task_desc=task_desc)

    async def initialize_tasklets(self) -> None:

        self._tasklets: List[Task] = []
        extra_mogrifiers = None
        transmogrificator: Transmogrificator = await self._pkg.create_transmogrificator(
            vars=self._input_values,
            extra_mogrifiers=extra_mogrifiers,
            basetopic=f"{self._basetopic}.{FRECKLES_EVENTS_TOPIC_NAME}",
        )

        self.add_tasklet(transmogrificator)

        mttt = MoveToTargetTask(
            prior_task_result=transmogrificator.result,
            target=self._target,
            target_config=self._target_config,
            item_metadata=self._input_values,
            basetopic=f"{self._basetopic}.{FRECKLES_EVENTS_TOPIC_NAME}",
        )
        self.add_tasklet(mttt)

        # result = await mttt.run_async(raise_exception=True)
        # return result

    async def execute_tasklets(self, *tasklets: Task) -> None:

        await tasklets[0].run_async(raise_exception=True)
        await tasklets[1].run_async(raise_exception=True)

    async def create_result_value(self, *tasklets: Task) -> Any:

        result = tasklets[1].result.result_value
        return result


class InstallFreckletResult(FreckletResult):
    def __init__(self, task_result: TaskResult):

        super().__init__(task_result=task_result)

    def _create_result_value(self, task_result: TaskResult) -> Mapping[str, Any]:
        """Create the actual result value dictionary.

        This can be overwritten by specialized result types.
        """

        if not isinstance(self._task_result.result_value, collections.abc.Mapping):
            raise TypeError(
                f"Invalid result type for InstallFrecklet: {type(self._task_result.result_value)}"
            )

        return self._task_result.result_value

    def __rich_console__(
        self, console: "Console", options: "ConsoleOptions"
    ) -> "RenderResult":

        yield ("[title]Result[/title]")
        yield ""
        target = self.result["target"]
        yield f"  Package installed into: {target}"


class BringFrecklet(Frecklet):
    def __init__(self, name: str, meta: TingMeta, init_values: Mapping[str, Any]):

        self._bring: Bring = init_values["bring"]
        super().__init__(name=name, meta=meta, init_values=init_values)

    @property
    def bring(self) -> Bring:

        return self._bring  # type: ignore


class BringInstallFrecklet(BringFrecklet):
    def _invalidate(self) -> None:

        self._pkg = None

    def get_required_base_args(self) -> RecordArg:

        args = {
            "pkg_name": {"type": "string", "doc": "the package name", "required": True},
            "pkg_index": {
                "type": "string",
                "doc": "the name of the index that contains the package",
                "required": True,
            },
            "target": {"type": "string", "doc": "the target folder", "required": False},
            "target_config": {
                "type": "dict",
                "doc": "(optional) target configuration",
                # TODO: reference
                "required": False,
            },
        }
        return self._bring.arg_hive.create_record_arg(childs=args)

    async def input_received(self, **input_vars: Any) -> Any:

        if self.number_of_inputs == 1:
            return None

        pkg_name = input_vars["pkg_name"]
        pkg_index = input_vars["pkg_index"]

        pkg = await self._bring.get_pkg(pkg_name, pkg_index, raise_exception=True)

        if pkg is None:
            raise FreckletException(
                frecklet=self,
                msg="Can't assemble frecklet.",
                reason=f"No package with name '{pkg_name}' found in index '{pkg_index}'.",
            )
        self.set_processed_input("pkg", pkg)

        self._msg = f"installing package '{pkg.pkg_id}'"

        defaults = {}
        index_defaults = await pkg.bring_index.get_index_defaults()
        for k, v in index_defaults.items():
            defaults[k] = FreckletVar(v, origin="index defaults")
        bring_defaults = await self._bring.get_defaults()
        for k, v in bring_defaults.items():
            if k not in defaults.keys():
                defaults[k] = v
        pkg_defaults = await pkg.get_pkg_defaults()
        for k, v in pkg_defaults.items():
            if k not in defaults.keys():
                defaults[k] = FreckletVar(v, origin="package defaults")

        pkg_args: RecordArg = await pkg.get_pkg_args()
        return (pkg_args, defaults)

    async def _create_frecklet_task(self, **input_values: Any) -> Task:

        pkg = self.get_processed_input("pkg")

        target = input_values.pop("target", None)
        target_config = input_values.pop("target_config", None)

        frecklet_task = BringInstallTask(
            pkg=pkg,
            input_values=input_values,
            target=target,
            target_config=target_config,
            basetopic=f"{self.base_namespace}",
        )

        return frecklet_task

    def process_frecklet_result(self, result: TaskResult) -> FreckletResult:

        return InstallFreckletResult(task_result=result)


class BringInstallAssemblyFrecklet(BringFrecklet):
    async def input_received(self, **input_vars: FreckletVar) -> Optional[RecordArg]:
        return None

    def get_required_base_args(self) -> RecordArg:

        args = {
            "pkg_name": {"type": "string", "doc": "the package name", "required": True},
            "pkg_index": {
                "type": "string",
                "doc": "the name of the index that contains the package",
                "required": True,
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

    async def _create_frecklet_task(self, **input_values: Any) -> Union[Task, Any]:

        return input_values


# class BringInstallFrecklet(BringFrecklet):
#     async def get_base_args(self) -> Mapping[str, Union[str, Arg, Mapping[str, Any]]]:
#
#         return {
#             "pkg_name": {"type": "string", "doc": "the package name", "required": True},
#             "pkg_index": {
#                 "type": "string",
#                 "doc": "the name of the index that contains the package",
#                 "required": True,
#             },
#             "target": {"type": "string", "doc": "the target folder", "required": False},
#             "target_config": {
#                 "type": "dict",
#                 "doc": "(optional) target configuration",
#                 # TODO: reference
#                 "required": False,
#             }
#             # "merge_strategy": {
#             #     "type": "merge_strategy",
#             #     "doc": "the merge strategy to use",
#             #     "default": "auto",
#             #     "required": True,
#             # },
#         }
#
#     async def get_msg(self) -> str:
#
#         pkg = await self.get_pkg()
#
#         return f"installing package '{pkg.name}'"
#
#     async def get_pkg(self) -> PkgTing:
#
#         if self.input_sets.get_processed_value("pkg") is None:
#
#             _base_vars: VarSet = await self.get_base_vars()
#             base_vars = _base_vars.create_values_dict()
#
#             pkg_name = base_vars["pkg_name"]
#             pkg_index = base_vars["pkg_index"]
#
#             pkg: PkgTing = await self._bring.get_pkg(  # type: ignore
#                 name=pkg_name, index=pkg_index, raise_exception=True
#             )  # type: ignore
#             aliases = await pkg.get_aliases()
#             self.input_sets.clear_aliases()
#             self.input_sets.add_aliases(aliases)
#
#             self.input_sets.add_processed_value("pkg", pkg)
#
#         return self.input_sets.get_processed_value("pkg")
#
#     async def get_required_args(
#         self, **base_vars: Any
#     ) -> Mapping[str, Union[str, Arg, Mapping[str, Any]]]:
#
#         pkg = await self.get_pkg()
#         index_defaults = await pkg.bring_index.get_index_defaults()
#         pkg_defaults = await pkg.get_defaults()
#         self.input_sets.add_defaults(
#             _id="index_defaults", _priority=100, **index_defaults
#         )
#         self.input_sets.add_defaults(_id="pkg_defaults", _priority=0, **pkg_defaults)
#         pkg_args: RecordArg = await pkg.get_pkg_args()
#
#         result: MutableMapping[str, Union[str, Arg, Mapping[str, Any]]] = dict(
#             pkg_args.childs
#         )
#
#         return result
#
#     async def create_processing_tasks(
#         self, **input_vars: Mapping[str, Any]
#     ) -> Union[Iterable[Task], Task]:
#
#         pkg = await self.get_pkg()
#         # extra_mogrifiers = await self.get_mogrifiers(**copy.deepcopy(input_vars))
#         extra_mogrifiers = None
#
#         transmogrificator: Transmogrificator = await pkg.create_transmogrificator(
#             vars=input_vars, extra_mogrifiers=extra_mogrifiers
#         )
#
#         return transmogrificator
#
#     async def create_postprocess_task(
#         self, **input_vars: Mapping[str, Any]
#     ) -> Optional[PostprocessTask]:
#
#         target: Any = input_vars.pop("target", None)
#         target_config: Any = input_vars.pop("target_config", None)
#
#         target_details = parse_target_data(
#             target, target_config, temp_folder_prefix="install_pkg"
#         )
#
#         _target_path = target_details["target_path"]
#         _target_msg = target_details["target_msg"]
#         _merge_config = target_details["target_config"]
#         # _is_temp = target_details["is_temp"]
#
#         item_metadata = {"pkg": SortedDict(input_vars)}
#
#         async def merge_folders(*tasks: Task):
#
#             target_folder = TrackingLocalFolder(path=_target_path)
#
#             source_folders = []
#             for transmogrificator in tasks:
#                 result = transmogrificator.result.get_processed_result()
#                 folder = result["folder_path"]
#                 source_folders.append(folder)
#
#             result = await target_folder.merge_folders(
#                 *source_folders, item_metadata=item_metadata, merge_config=_merge_config
#             )
#
#             return {
#                 "target": _target_path,
#                 "merge_result": result,
#                 "item_metadata": item_metadata,
#             }
#
#         pp_desc = BringTaskDesc(
#             name=f"merge_{self.name}_pkg_files",
#             msg=f"merging prepared files into {_target_msg}",
#         )
#         task = PostprocessTask(func=merge_folders, task_desc=pp_desc)
#
#         return task
#
#
# class BringInstallAssemblyFrecklet(BringFrecklet):
#     async def create_pkg_map(
#         self, pkg_list: Iterable[Union[str, Mapping[str, Any]]]
#     ) -> Mapping[str, Mapping[str, Any]]:
#
#         pkg_map: Dict[str, Dict[str, Any]] = {}
#
#         _pkg_list: Iterable[Mapping[str, Any]] = self._explode_pkg_list(
#             pkg_list=pkg_list
#         )
#
#         async def add_pkg(_pkg_name: str):
#             _pkg: PkgTing = await self._bring.get_pkg(  # type: ignore
#                 _pkg_name, raise_exception=True
#             )  # type: ignore
#             pkg_map[_pkg_name]["pkg"] = _pkg
#             args = await _pkg.get_pkg_args()
#             pkg_map[_pkg_name]["args"] = args
#
#         async with create_task_group() as tg:
#             for pkg_data in _pkg_list:
#                 pkg_name = pkg_data["name"]
#                 pkg_map[pkg_name] = {}
#                 await tg.spawn(add_pkg, pkg_name)
#
#         self.input_sets.add_processed_value("pkg_map", pkg_map)
#         return pkg_map
#
#     def _explode_pkg_list(
#         self, pkg_list: Iterable[Union[str, Mapping[str, Any]]]
#     ) -> Iterable[Mapping[str, Any]]:
#
#         result: List[Mapping[str, Any]] = []
#         for item in pkg_list:
#             _item_dict: Mapping[str, Any]
#             if isinstance(item, str):
#                 _item_dict = {"name": item}
#             elif isinstance(item, collections.abc.Mapping):
#                 _item_dict = item
#             else:
#                 raise TypeError(
#                     f"Can't create package data, invalid type '{type(item)}': {item}"
#                 )
#             result.append(_item_dict)
#         return result
#
#     async def get_msg(self) -> str:
#
#         return f"installing bring assembly '{self.name}'"
#
#     async def get_base_args(self) -> Mapping[str, Union[str, Arg, Mapping[str, Any]]]:
#
#         return {
#             "args": {
#                 "type": "dict",
#                 "required": False,
#                 "doc": "data to describe the vars in this frecklet",
#             },
#             "pkgs": {
#                 "type": "list",
#                 "required": True,
#                 "doc": "a list of packages to install",
#             },
#             "target": {"type": "string", "doc": "the target folder", "required": False},
#             "target_config": {
#                 "type": "dict",
#                 "doc": "(optional) target configuration",
#                 # TODO: reference
#                 "required": False,
#             },
#         }
#
#     async def get_required_args(
#         self, **base_vars: Any
#     ) -> Mapping[str, Union[str, Arg, Mapping[str, Any]]]:
#
#         args_dict = base_vars.pop("args", None)
#         if args_dict is None:
#             args_dict = {}
#
#         # pkgs = base_vars["pkgs"]
#         # target = base_vars["target"]
#         # merge_strategy = base_vars["merge_strategy"]
#
#         var_names = find_var_names_in_obj(
#             base_vars, delimiter=BRING_IN_DEFAULT_DELIMITER
#         )
#
#         if not var_names:
#             return {}
#
#         result: Dict[str, Union[str, Arg, Mapping[str, Any]]] = {}
#         for var_name in var_names:
#             if var_name in args_dict.keys():
#                 result[var_name] = args_dict[var_name]
#             else:
#                 result[var_name] = {
#                     "type": "any",
#                     "required": True,
#                     "doc": f"value for '{var_name}'",
#                 }
#
#         return result
#
#     def calculate_replaced_vars(
#         self, input_vars: Mapping[str, Any]
#     ) -> Mapping[str, Any]:
#         """Replace input variables names with their values."""
#
#         value_dict = {
#             "target": input_vars.get("target", None),
#             "target_config": input_vars.get("target_config", None),
#             "pkgs": input_vars.get("pkgs", None),
#         }
#
#         value_dict_replaced = replace_var_names_in_obj(
#             value_dict, repl_dict=input_vars, delimiter=BRING_IN_DEFAULT_DELIMITER
#         )
#         return value_dict_replaced
#
#     async def create_processing_tasks(
#         self, **input_vars: Mapping[str, Any]
#     ) -> Union[Task, Iterable[Task], "Frecklet", Iterable["Frecklet"]]:
#
#         value_dict_replaced = self.calculate_replaced_vars(input_vars)
#
#         # target = value_dict_replaced["target"]
#         # merge_strategy = value_dict_replaced["merge_strategy"]
#         pkgs = value_dict_replaced["pkgs"]
#
#         pkg_map: Mapping[str, Mapping[str, Any]] = await self.create_pkg_map(
#             pkg_list=pkgs
#         )
#
#         result: List[Frecklet] = []
#         index = 0
#         for pkg_name, details in pkg_map.items():
#             index = index + 1
#             pkg: PkgTing = details["pkg"]
#             # args: RecordArg = details["args"]
#             # TODO: validate vars
#
#             frecklet: Frecklet = self._bring.tingistry.create_ting(  # type: ignore
#                 f"{self._bring.full_name}.frecklets.install_pkg",
#                 f"{self.full_name}.pkgs.pkg_{pkg.name}_{index}",
#             )
#             frecklet.input_sets.add_constants(
#                 _id="pkg_details", pkg_name=pkg.name, pkg_index=pkg.bring_index.id
#             )
#             frecklet.input_sets.add_constants(
#                 _id="target_details", target=None, merge_strategy="default"
#             )
#             result.append(frecklet)
#
#         return result
#
#     async def create_postprocess_task(
#         self, **input_vars: Mapping[str, Any]
#     ) -> Optional[PostprocessTask]:
#
#         value_dict_replaced = self.calculate_replaced_vars(input_vars)
#
#         target = value_dict_replaced["target"]
#         target_config = value_dict_replaced["target_config"]
#
#         target_details = parse_target_data(
#             target, target_config, temp_folder_prefix="install_assembly"
#         )
#
#         _target_path = target_details["target_path"]
#         _target_msg = target_details["target_msg"]
#         _merge_config = target_details["target_config"]
#
#         async def merge_folders(*tasks: Task):
#
#             target_folder = TrackingLocalFolder(path=_target_path)
#
#             merge_results = []
#
#             for task in tasks:
#
#                 result_data = task.result.data
#
#                 item_metadata = result_data["item_metadata"]
#                 source_folder = result_data["target"]
#
#                 merge_result = await target_folder.merge_folders(
#                     source_folder,
#                     item_metadata=item_metadata,
#                     merge_config=_merge_config,
#                 )
#                 merge_results.append(merge_result)
#
#             return {"target": _target_path, "merge_results": merge_results}
#
#         pp_desc = BringTaskDesc(
#             name=f"merge_{self.name}_pkg_files",
#             msg=f"merging files from all packages into {_target_msg}",
#         )
#         task = PostprocessTask(func=merge_folders, task_desc=pp_desc)
#
#         return task
