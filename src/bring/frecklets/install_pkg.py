# -*- coding: utf-8 -*-

import collections
import copy
import logging
import os
import tempfile
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, MutableMapping, Optional

from bring.defaults import BRING_RESULTS_FOLDER, BRING_WORKSPACE_FOLDER
from bring.frecklets import BringFrecklet, parse_target_data
from bring.mogrify import Transmogrificator
from bring.mogrify.transform_folder import PkgContentLocalFolder
from bring.pkg import PkgTing
from bring.pkg_index.index import BringIndexTing
from bring.utils.pkg_spec import PkgSpec
from freckles.core.frecklet import FreckletException, FreckletVar
from frkl.args.arg import RecordArg
from frkl.common.formats.auto import AutoInput
from frkl.common.formats.serialize import to_value_string
from frkl.common.strings import generate_valid_identifier
from frkl.explain.explanation import Explanation
from frkl.targets.local_folder import TrackingLocalFolder
from frkl.tasks.exceptions import FrklTaskRunException
from frkl.tasks.task import Task, TaskResult
from frkl.tasks.task_desc import TaskDesc
from frkl.tasks.tasks import Tasks


if TYPE_CHECKING:
    from rich.console import ConsoleOptions, Console, RenderResult

log = logging.getLogger("frtls")


class InstallMergeResult(Explanation):
    def __init__(self, **metadata: Any):

        self._metadata: Dict[str, Any] = dict(metadata)
        self._items: Dict[str, MutableMapping[str, Any]] = {}

        super().__init__()

    def add_merge_item(self, id: str, **result_metadata: Any) -> None:

        # TODO: check if already exists?
        self._items[id] = dict(result_metadata)
        if "merged" not in self._items[id].keys():
            self._items[id]["merged"] = True
        if "msg" not in self._items[id].keys():
            self._items[id]["msg"] = "merged"

    def add_merge_result(self, result: "InstallMergeResult") -> None:

        self._items.update(result.merged_items)

    async def create_explanation_data(self) -> Mapping[str, Any]:

        return self.merged_items

    def add_metadata(self, key: str, value: Any) -> None:
        self._metadata[key] = value

    @property
    def merged_items(self):
        return self._items

    @property
    def metadata(self) -> Mapping[str, Any]:
        return self._metadata

    def __rich_console__(
        self, console: "Console", options: "ConsoleOptions"
    ) -> "RenderResult":

        if not self.merged_items:
            yield "- no items merged[/italic]'"
            return

        for id, details in self.merged_items.items():
            yield f"  [key2]{id}[/key2]: [value]{details['msg']}[/value]"

        return


class PkgContentTask(Task):
    def __init__(
        self,
        prior_task_result: TaskResult,
        pkg_spec: Any,
        item_metadata: Optional[Mapping[str, Any]] = None,
        target: Optional[str] = None,
        **kwargs,
    ):

        self._prior_task_result: TaskResult = prior_task_result
        self._pkg_spec: PkgSpec = PkgSpec.create(pkg_spec)
        if item_metadata is None:
            item_metadata = {}
        else:
            item_metadata = dict(item_metadata)
        self._item_metadata: MutableMapping[str, Any] = item_metadata

        if not target:
            target = tempfile.mkdtemp(prefix="transform_", dir=BRING_WORKSPACE_FOLDER)
        self._target: str = target

        task_desc = TaskDesc(
            name="transforming pkg content", msg="transforming package content"
        )
        super().__init__(task_desc=task_desc, **kwargs)

    @property
    def pkg_spec(self) -> PkgSpec:
        return self._pkg_spec

    async def execute_task(self) -> Any:

        if not self._prior_task_result.success:
            raise FrklTaskRunException(task=self, msg="Can't transform package files.", reason="Required previous job did not finish successfully.", parent=self._prior_task_result.error)  # type: ignore

        source_folder = self._prior_task_result.result_value["folder_path"]
        folder = PkgContentLocalFolder(path=self._target, pkg_spec=self._pkg_spec)

        merge_result = await folder.merge_folders(
            source_folder, item_metadata=self._item_metadata
        )
        merge_result.add_metadata("transform", self._pkg_spec.to_dict())

        result = {"folder_path": self._target, "merge_result": merge_result}
        return result


class MoveToTargetTask(Task):
    def __init__(
        self,
        prior_task_result: TaskResult,
        target: Optional[str] = None,
        target_config: Optional[Mapping[str, Any]] = None,
        item_metadata: Optional[Mapping[str, Any]] = None,
    ):

        self._prior_task_result: TaskResult = prior_task_result

        self._target: Optional[str] = target
        self._target_config: Optional[Mapping[str, Any]] = target_config
        if item_metadata is None:
            item_metadata = {}
        elif not isinstance(item_metadata, collections.abc.Mapping):
            raise TypeError(
                f"Can't create target task: invalid type for metadata '{type(item_metadata)}'"
            )
        self._item_metadata: Mapping[str, Any] = item_metadata

        self._target_details = parse_target_data(
            self._target, self._target_config, temp_folder_prefix="install_"
        )

        task_desc = TaskDesc(
            name="merge files",
            msg=f"merging files into {self._target_details['target_msg']}",
        )

        super().__init__(task_desc=task_desc)

    async def execute_task(self) -> Any:

        if not self._prior_task_result.success:
            raise FrklTaskRunException(task=self, msg="Can't move files to target folder.", reason="Required previous job did not finish successfully.", parent=self._prior_task_result.error)  # type: ignore

        source_folder = self._prior_task_result.result_value["folder_path"]

        _target_path = self._target_details["target_path"]
        # _target_msg = self._target_details["target_msg"]
        _merge_config = self._target_details["target_config"]

        if self._item_metadata is None:
            _item_metadata: Mapping[str, Any] = {}
        else:
            _item_metadata = self._item_metadata

        target_folder = TrackingLocalFolder(path=_target_path)
        merge_result = await target_folder.merge_folders(
            source_folder, item_metadata=_item_metadata, merge_config=_merge_config
        )

        merge_result.add_metadata("item_metadata", _item_metadata)

        return {
            "folder_path": _target_path,
            "item_metadata": _item_metadata,
            "merge_result": merge_result,
        }


class BringInstallTask(Tasks):
    def __init__(
        self,
        pkg: PkgTing,
        input_values: Mapping[str, Any],
        item_metadata: Mapping[str, Any],
        target: Optional[str] = None,
        target_config: Optional[Mapping[str, Any]] = None,
        transform_pkg: Optional[Mapping[str, Any]] = None,
    ):

        self._pkg: PkgTing = pkg
        self._input_values: Mapping[str, Any] = input_values
        self._item_metadata: Mapping[str, Any] = item_metadata
        self._target: Optional[str] = target
        self._target_config: Optional[Mapping[str, Any]] = target_config
        self._transform_pkg: Optional[Mapping[str, Any]] = transform_pkg

        task_desc = TaskDesc(
            name=self._pkg.name, msg=f"installing pkg '{self._pkg.name}'",
        )

        super().__init__(task_desc=task_desc)

    async def initialize_tasklets(self) -> None:

        self._tasklets: List[Task] = []
        extra_mogrifiers = None
        transmogrificator: Transmogrificator = await self._pkg.create_transmogrificator(
            vars=self._input_values, extra_mogrifiers=extra_mogrifiers,
        )

        await self.add_tasklet(transmogrificator)

        prior_task: Task = transmogrificator

        item_metadata: Dict[str, Any] = copy.deepcopy(dict(self._item_metadata))
        # vars: Dict[str, Any] = dict(self._input_values)
        # item_metadata["pkg"] = {
        #     "name": vars.pop("pkg_name"),
        #     "index": vars.pop("pkg_index"),
        # }
        # item_metadata["vars"] = vars

        if self._transform_pkg:

            pct = PkgContentTask(
                prior_task_result=transmogrificator.result,
                pkg_spec=self._transform_pkg,
                item_metadata=item_metadata,
            )
            await self.add_tasklet(pct)
            prior_task = pct
            item_metadata["transform"] = pct.pkg_spec.to_dict()

        if self._target:
            _target = self._target
        else:
            _target = tempfile.mkdtemp(prefix="install_", dir=BRING_RESULTS_FOLDER)

        mttt = MoveToTargetTask(
            prior_task_result=prior_task.result,
            target=_target,
            target_config=self._target_config,
            item_metadata=item_metadata,
        )
        await self.add_tasklet(mttt)

        # result = await mttt.run_async(raise_exception=True)
        # return result

    async def execute_tasklets(self, *tasklets: Task) -> None:

        for t in tasklets:
            await t.run_async(raise_exception=True)

    async def create_result_value(self, *tasklets: Task) -> Any:

        result = tasklets[-1].result.result_value
        return result


class BringInstallFrecklet(BringFrecklet):
    def _invalidate(self) -> None:

        self._pkg = None

    def get_required_base_args(self) -> RecordArg:

        args = {
            "pkg": {"type": "any", "doc": "the package name or data", "required": True},
            # "pkg_index": {
            #     "type": "string",
            #     "doc": "the name of the index that contains the package",
            #     "required": False,
            # },
            "target": {"type": "string", "doc": "the target folder", "required": False},
            "target_config": {
                "type": "dict",
                "doc": "(optional) target configuration",
                # TODO: reference
                "required": False,
            },
            "transform": {
                "type": "dict",
                "doc": "(optional) transform instructions for the package folder",
                "required": False,
            },
        }
        return self._bring.arg_hive.create_record_arg(childs=args)

    async def input_received(self, **input_vars: FreckletVar) -> Any:

        if self.current_amount_of_inputs == 0:

            defaults = {}

            pkg_input = input_vars["pkg"].value
            pkg_index: Optional[BringIndexTing] = None
            pkg: Optional[PkgTing] = None
            pkg_metadata: Dict[str, Any] = {}

            if isinstance(pkg_input, str):
                _result = await self._bring.get_pkg_and_index(pkg_input)
                if _result is not None:
                    pkg_metadata = {"name": _result[0].name, "index": _result[1].id}  # type: ignore
                    pkg = _result[0]
                    pkg_index = _result[1]

                else:
                    full_path = os.path.abspath(os.path.expanduser(pkg_input))
                    ai = AutoInput(full_path)
                    content = await ai.get_content_async()
                    if "source" in content.keys():
                        defaults["pkg"] = content["source"]
                        ting_name = content.get("info", {}).get("name", None)
                        if ting_name is None:
                            ting_name = generate_valid_identifier(pkg_input)
                        pkg = self.tingistry.create_ting(  # type: ignore
                            "bring.types.dynamic_pkg",
                            ting_name=f"{self.full_name}.{ting_name}",
                        )
                        pkg.set_input(**content)  # type: ignore
                        pkg_metadata = {"source": content["source"]}
            elif isinstance(pkg_input, Mapping):

                if "source" in pkg_input.keys():
                    _data = pkg_input["source"]
                    defaults["pkg"] = _data
                elif "type" not in pkg_input:
                    # TODO: references
                    _r = to_value_string(pkg_input, reindent=4)
                    raise FreckletException(
                        frecklet=self,
                        msg="Can't create package from provided input dict.",
                        reason=f"Input data does not contain a 'type' key:\n\n{_r}",
                    )
                else:
                    _data = pkg_input

                ting_name = pkg_input.get("info", {}).get("name", None)

                if ting_name is None:
                    ting_name = generate_valid_identifier()
                pkg = self.tingistry.create_ting(  # type: ignore
                    "bring.types.dynamic_pkg", ting_name=f"{self.full_name}.{ting_name}"
                )
                pkg.set_input(**pkg_input)  # type: ignore
                pkg_metadata = {"source": pkg_input["source"]}

            if pkg is None:
                input_str = to_value_string(pkg_input, reindent=4)

                reason = f"Invalid input:\n\n{input_str}"
                raise FreckletException(
                    frecklet=self,
                    msg="Can't create package from provided input.",
                    reason=reason,
                    solution="Either provide a valid package name string, a pkg description map, or a path to a file containing one.",
                )

            self.set_processed_input("pkg", pkg)
            self.set_processed_input("pkg_metadata", pkg_metadata)

            self._msg = f"installing package '{pkg.name}'"

            if pkg_index:

                index_defaults = await pkg_index.get_index_defaults()
                # index_defaults = await pkg.bring_index.get_index_defaults()
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

            # we don't want defaults overwrite inputs in this case
            for k in input_vars.keys():
                if k in defaults.keys() and not k == "pkg":
                    defaults.pop(k)

            pkg_args: RecordArg = await pkg.get_pkg_args()

            return (pkg_args, defaults)

        elif self.current_amount_of_inputs == 1:
            pkg_input = self.get_processed_input("pkg")
            if pkg_input is None:
                raise Exception(
                    "No 'pkg' object saved in processed input, this is a bug."
                )
            pkg_aliases: Mapping[str, Mapping[Any, Any]] = await pkg_input.get_aliases()

            replacements: Dict[str, FreckletVar] = {}
            for k, v in input_vars.items():
                if k not in pkg_aliases.keys():
                    continue

                alias_set = pkg_aliases[k]
                if v.value not in alias_set.keys():
                    continue

                replacment_value = alias_set[v.value]
                new_metadata = dict(v.metadata)
                new_metadata["from_alias"] = v.value
                fv = FreckletVar(replacment_value, **new_metadata)
                replacements[k] = fv
            return (None, replacements)

        else:
            return None

    async def _create_frecklet_task(self, **input_values: Any) -> Task:

        pkg = self.get_processed_input("pkg")
        pkg_metadata = self.get_processed_input("pkg_metadata")

        target = input_values.pop("target", None)
        target_config = input_values.pop("target_config", None)
        transform_pkg = input_values.pop("transform", None)

        input_values.pop("pkg")

        item_metadata: Dict[str, Any] = {
            "install": {"pkg": pkg_metadata, "vars": input_values}
        }

        frecklet_task = BringInstallTask(
            pkg=pkg,
            input_values=input_values,
            item_metadata=item_metadata,
            target=target,
            target_config=target_config,
            transform_pkg=transform_pkg,
        )

        return frecklet_task
