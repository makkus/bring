# -*- coding: utf-8 -*-
import collections
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Union

from anyio import create_task_group
from bring.bring import Bring
from bring.defaults import BRING_RESULTS_FOLDER
from bring.mogrify import Transmogrificator
from bring.pkg_index.pkg import PkgTing
from bring.utils import BringTaskDesc
from freckles.core.frecklet import Frecklet
from freckles.core.vars import VarSet
from frtls.args.arg import Arg, RecordArg
from frtls.files import create_temp_dir
from frtls.targets.local_folder import TrackingLocalFolder
from frtls.tasks import PostprocessTask, Task
from frtls.templating.regex import (
    create_var_regex,
    find_var_names_in_obj,
    replace_var_names_in_obj,
)
from sortedcontainers import SortedDict
from tings.ting import TingMeta


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
        _target_msg = f"folder: {_target_path}"
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


class BringInstallFrecklet(Frecklet):
    def __init__(self, name: str, meta: TingMeta, init_values: Mapping[str, Any]):

        self._bring: Bring
        super().__init__(name=name, meta=meta, init_values=init_values)

    async def init_frecklet(self, init_values: Mapping[str, Any]):

        self._bring = init_values["bring"]
        bring_defaults = await self._bring.get_defaults()
        self.input_sets.add_defaults(
            _id="bring_defaults", _priority=10, **bring_defaults
        )

    @property
    def bring(self) -> Bring:

        return self._bring  # type: ignore

    async def get_base_args(self) -> Mapping[str, Union[str, Arg, Mapping[str, Any]]]:

        return {
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
            }
            # "merge_strategy": {
            #     "type": "merge_strategy",
            #     "doc": "the merge strategy to use",
            #     "default": "auto",
            #     "required": True,
            # },
        }

    async def get_msg(self) -> str:

        pkg = await self.get_pkg()

        return f"installing package '{pkg.name}'"

    async def get_pkg(self) -> PkgTing:

        if self.input_sets.get_processed_value("pkg") is None:

            _base_vars: VarSet = await self.get_base_vars()
            base_vars = _base_vars.create_values_dict()

            pkg_name = base_vars["pkg_name"]
            pkg_index = base_vars["pkg_index"]

            pkg: PkgTing = await self._bring.get_pkg(  # type: ignore
                name=pkg_name, index=pkg_index, raise_exception=True
            )  # type: ignore
            aliases = await pkg.get_aliases()
            self.input_sets.clear_aliases()
            self.input_sets.add_aliases(aliases)

            self.input_sets.add_processed_value("pkg", pkg)

        return self.input_sets.get_processed_value("pkg")

    async def get_required_args(
        self, **base_vars: Any
    ) -> Mapping[str, Union[str, Arg, Mapping[str, Any]]]:

        pkg = await self.get_pkg()
        index_defaults = await pkg.bring_index.get_index_defaults()
        pkg_defaults = await pkg.get_defaults()
        self.input_sets.add_defaults(
            _id="index_defaults", _priority=100, **index_defaults
        )
        self.input_sets.add_defaults(_id="pkg_defaults", _priority=0, **pkg_defaults)
        pkg_args: RecordArg = await pkg.get_pkg_args()

        result: MutableMapping[str, Union[str, Arg, Mapping[str, Any]]] = dict(
            pkg_args.childs
        )

        return result

    async def create_processing_tasks(
        self, **input_vars: Mapping[str, Any]
    ) -> Union[Iterable[Task], Task]:

        pkg = await self.get_pkg()
        # extra_mogrifiers = await self.get_mogrifiers(**copy.deepcopy(input_vars))
        extra_mogrifiers = None

        transmogrificator: Transmogrificator = await pkg.create_transmogrificator(
            vars=input_vars, extra_mogrifiers=extra_mogrifiers
        )

        return transmogrificator

    async def create_postprocess_task(
        self, **input_vars: Mapping[str, Any]
    ) -> Optional[PostprocessTask]:

        target: Any = input_vars.pop("target", None)
        target_config: Any = input_vars.pop("target_config", None)

        target_details = parse_target_data(
            target, target_config, temp_folder_prefix="install_pkg"
        )

        _target_path = target_details["target_path"]
        _target_msg = target_details["target_msg"]
        _merge_config = target_details["target_config"]
        # _is_temp = target_details["is_temp"]

        item_metadata = {"pkg": SortedDict(input_vars)}

        async def merge_folders(*tasks: Task):

            target_folder = TrackingLocalFolder(path=_target_path)

            source_folders = []
            for transmogrificator in tasks:
                result = transmogrificator.result.get_processed_result()
                folder = result["folder_path"]
                source_folders.append(folder)

            result = await target_folder.merge_folders(
                *source_folders, item_metadata=item_metadata, merge_config=_merge_config
            )

            return {
                "target": _target_path,
                "merge_result": result,
                "item_metadata": item_metadata,
            }

        pp_desc = BringTaskDesc(
            name=f"merge_{self.name}_pkg_files",
            msg=f"merging prepared files into {_target_msg}",
        )
        task = PostprocessTask(func=merge_folders, task_desc=pp_desc)

        return task


class BringInstallAssemblyFrecklet(Frecklet):
    def __init__(self, name: str, meta: TingMeta, init_values: Mapping[str, Any]):

        self._bring: Bring
        super().__init__(name=name, meta=meta, init_values=init_values)

    async def init_frecklet(self, init_values: Mapping[str, Any]):

        self._bring = init_values["bring"]
        bring_defaults = await self._bring.get_defaults()
        self.input_sets.add_defaults(
            _id="bring_defaults", _priority=10, **bring_defaults
        )

    async def create_pkg_map(
        self, pkg_list: Iterable[Union[str, Mapping[str, Any]]]
    ) -> Mapping[str, Mapping[str, Any]]:

        pkg_map: Dict[str, Dict[str, Any]] = {}

        _pkg_list: Iterable[Mapping[str, Any]] = self._explode_pkg_list(
            pkg_list=pkg_list
        )

        async def add_pkg(_pkg_name: str):
            _pkg: PkgTing = await self._bring.get_pkg(  # type: ignore
                _pkg_name, raise_exception=True
            )  # type: ignore
            pkg_map[_pkg_name]["pkg"] = _pkg
            args = await _pkg.get_pkg_args()
            pkg_map[_pkg_name]["args"] = args

        async with create_task_group() as tg:
            for pkg_data in _pkg_list:
                pkg_name = pkg_data["name"]
                pkg_map[pkg_name] = {}
                await tg.spawn(add_pkg, pkg_name)

        self.input_sets.add_processed_value("pkg_map", pkg_map)
        return pkg_map

    def _explode_pkg_list(
        self, pkg_list: Iterable[Union[str, Mapping[str, Any]]]
    ) -> Iterable[Mapping[str, Any]]:

        result: List[Mapping[str, Any]] = []
        for item in pkg_list:
            _item_dict: Mapping[str, Any]
            if isinstance(item, str):
                _item_dict = {"name": item}
            elif isinstance(item, collections.abc.Mapping):
                _item_dict = item
            else:
                raise TypeError(
                    f"Can't create package data, invalid type '{type(item)}': {item}"
                )
            result.append(_item_dict)
        return result

    async def get_msg(self) -> str:

        return f"installing bring assembly '{self.name}'"

    async def get_base_args(self) -> Mapping[str, Union[str, Arg, Mapping[str, Any]]]:

        return {
            "args": {
                "type": "dict",
                "required": False,
                "doc": "data to describe the vars in this frecklet",
            },
            "pkgs": {
                "type": "list",
                "required": True,
                "doc": "a list of packages to install",
            },
            "target": {"type": "string", "doc": "the target folder", "required": False},
            "target_config": {
                "type": "dict",
                "doc": "(optional) target configuration",
                # TODO: reference
                "required": False,
            },
        }

    async def get_required_args(
        self, **base_vars: Any
    ) -> Mapping[str, Union[str, Arg, Mapping[str, Any]]]:

        args_dict = base_vars.pop("args", None)
        if args_dict is None:
            args_dict = {}

        # pkgs = base_vars["pkgs"]
        # target = base_vars["target"]
        # merge_strategy = base_vars["merge_strategy"]

        var_names = find_var_names_in_obj(
            base_vars, delimiter=BRING_IN_DEFAULT_DELIMITER
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

    def calculate_replaced_vars(
        self, input_vars: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Replace input variables names with their values."""

        value_dict = {
            "target": input_vars.get("target", None),
            "target_config": input_vars.get("target_config", None),
            "pkgs": input_vars.get("pkgs", None),
        }

        value_dict_replaced = replace_var_names_in_obj(
            value_dict, repl_dict=input_vars, delimiter=BRING_IN_DEFAULT_DELIMITER
        )
        return value_dict_replaced

    async def create_processing_tasks(
        self, **input_vars: Mapping[str, Any]
    ) -> Union[Task, Iterable[Task], "Frecklet", Iterable["Frecklet"]]:

        value_dict_replaced = self.calculate_replaced_vars(input_vars)

        # target = value_dict_replaced["target"]
        # merge_strategy = value_dict_replaced["merge_strategy"]
        pkgs = value_dict_replaced["pkgs"]

        pkg_map: Mapping[str, Mapping[str, Any]] = await self.create_pkg_map(
            pkg_list=pkgs
        )

        result: List[Frecklet] = []
        index = 0
        for pkg_name, details in pkg_map.items():
            index = index + 1
            pkg: PkgTing = details["pkg"]
            # args: RecordArg = details["args"]
            # TODO: validate vars

            frecklet: Frecklet = self._bring.tingistry.create_ting(  # type: ignore
                f"{self._bring.full_name}.frecklets.install_pkg",
                f"{self.full_name}.pkgs.pkg_{pkg.name}_{index}",
            )
            frecklet.input_sets.add_constants(
                _id="pkg_details", pkg_name=pkg.name, pkg_index=pkg.bring_index.id
            )
            frecklet.input_sets.add_constants(
                _id="target_details", target=None, merge_strategy="default"
            )
            result.append(frecklet)

        return result

    async def create_postprocess_task(
        self, **input_vars: Mapping[str, Any]
    ) -> Optional[PostprocessTask]:

        value_dict_replaced = self.calculate_replaced_vars(input_vars)

        target = value_dict_replaced["target"]
        target_config = value_dict_replaced["target_config"]

        target_details = parse_target_data(
            target, target_config, temp_folder_prefix="install_assembly"
        )

        _target_path = target_details["target_path"]
        _target_msg = target_details["target_msg"]
        _merge_config = target_details["target_config"]

        async def merge_folders(*tasks: Task):

            target_folder = TrackingLocalFolder(path=_target_path)

            merge_results = []

            for task in tasks:

                result_data = task.result.data

                item_metadata = result_data["item_metadata"]
                source_folder = result_data["target"]

                merge_result = await target_folder.merge_folders(
                    source_folder,
                    item_metadata=item_metadata,
                    merge_config=_merge_config,
                )
                merge_results.append(merge_result)

            return {"target": _target_path, "merge_results": merge_results}

        pp_desc = BringTaskDesc(
            name=f"merge_{self.name}_pkg_files",
            msg=f"merging files from all packages into {_target_msg}",
        )
        task = PostprocessTask(func=merge_folders, task_desc=pp_desc)

        return task
