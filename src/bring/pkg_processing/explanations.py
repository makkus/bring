# -*- coding: utf-8 -*-
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional

from frtls.async_helpers import wrap_async_task
from frtls.doc.explanation import Explanation
from frtls.doc.explanation.steps import StepsExplanation
from frtls.doc.utils import to_value_string
from rich import box
from rich.console import Console, ConsoleOptions, RenderResult
from rich.table import Table


if TYPE_CHECKING:
    from bring.pkg_processing.processor import BringProcessor
    from bring.pkg_processing.vars import ArgsHolder


class ProcessVars(Explanation):
    def __init__(
        self,
        args_holder: "ArgsHolder",
        show_title: bool = True,
        render_as_table: bool = False,
    ):

        self._args_holder: "ArgsHolder" = args_holder
        self._arg_map: Optional[Dict[str, Dict[str, Any]]] = None
        self._render_as_table: bool = render_as_table
        self._show_title: bool = show_title

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
                result[arg_name]["is_set"] = False
                continue

            result[arg_name]["is_set"] = True

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

        result: List[Any] = []

        if self._render_as_table:

            if self._show_title:
                result.append("\n[bold]Variables[/bold]:")

            aliases: bool = False
            for arg_name, data in self.arg_map.items():
                _alias = data.get("from_alias", None)
                if _alias:
                    aliases = True
                    break

            table = Table(show_header=True, box=box.SIMPLE)
            table.add_column("Name", no_wrap=True, style="key2")
            table.add_column("Value", style="value")

            if aliases:
                table.add_column("from alias", no_wrap=True, style="value")

            table.add_column("Origin")

            for arg_name, data in self.arg_map.items():
                if aliases:
                    _alias = data.get("from_alias", "")
                is_set = data["is_set"]
                if is_set:
                    value = data["value"]
                    origin = data["origin"]
                else:
                    value = "-- not set --"
                    origin = ""

                value_string = to_value_string(value)

                if aliases:
                    table.add_row(arg_name, value_string, _alias, origin)
                else:
                    table.add_row(arg_name, value, origin)

            result.append(table)
            return result

        else:

            if self._show_title:
                result.append("\n[bold]Variables[/bold]:")
                result.append("")

            for arg_name, data in self.arg_map.items():
                _alias = data.get("from_alias", "")
                if _alias:
                    _alias = f" (from alias: [italic]{_alias}[/italic])"
                is_set = data["is_set"]
                if is_set:
                    result.append(
                        f"  {arg_name}: [italic]{data['value']}[/italic]{_alias}"
                    )

            return result


class ProcessInfo(Explanation):
    def __init__(self, processor: "BringProcessor"):

        self._processor: "BringProcessor" = processor
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
