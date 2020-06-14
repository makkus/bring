# -*- coding: utf-8 -*-
from typing import TYPE_CHECKING, Any, Mapping

from freckles.core.vars import FreckletInputSet
from frtls.doc.explanation import Explanation, to_value_string
from frtls.tasks import TaskExplanation
from rich import box
from rich.console import Console, ConsoleOptions, RenderResult
from rich.table import Table


if TYPE_CHECKING:
    from freckles.core.frecklet import Frecklet, FreckletInput


class FreckletInputExplanation(Explanation):
    def __init__(self, data: "FreckletInput", **kwargs):

        super().__init__(data=data, **kwargs)

    async def create_explanation_data(self) -> Mapping[str, Any]:

        frecklet_input: "FreckletInput" = self.data

        merged_values = frecklet_input.get_merged_values()

        values = {}
        for k, v in sorted(merged_values.items()):
            raw_value = v["raw_value"]
            origin: FreckletInputSet = v["origin"]
            values[k] = {"value": raw_value, "origin": origin.id}
            if "from_alias" in v.keys():
                values[k]["from_alias"] = v["from_alias"]

        return values

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:

        value_dict: Mapping[str, Any] = self.explanation_data

        table = Table(show_header=False, box=box.SIMPLE)
        table.add_column("Name", no_wrap=True, style="key2")
        table.add_column("Value", style="value")

        # use_alias = False
        # for data in value_dict.values():
        #
        #     if "from_alias" in data.keys():
        #         use_alias = True
        #         break
        #
        # if use_alias:
        #     table.add_column("from Alias", style="value")

        table.add_column("Origin", style="value")

        for arg_name, data in value_dict.items():
            value = data["value"]
            origin = data["origin"]

            value_string = to_value_string(value)

            # if not use_alias:
            table.add_row(arg_name, value_string, f"origin: {origin}")
            # else:
            #     alias = data.get("from_alias", "")
            #     table.add_row(arg_name, value_string, alias, f"origin: {origin}")

        yield table


class FreckletExplanation(Explanation):
    def __init__(self, frecklet: "Frecklet", **kwargs):

        super().__init__(data=frecklet, **kwargs)

    async def create_explanation_data(self) -> Mapping[str, Any]:

        frecklet: Frecklet = self.data

        task = await frecklet._create_task()
        if task is None:
            raise NotImplementedError()
        task_expl = TaskExplanation(task)

        frecklet_input = frecklet.input_sets.explain()
        frecklet_input_dict = frecklet_input.explanation_data

        args = await frecklet._get_required_args()

        vars = await frecklet.get_vars()

        vars_dict = {}
        for k, v in sorted(vars.items()):

            metadata = frecklet_input_dict.get(k, None)

            if metadata is None:
                origin = "-- n/a --"
            else:
                origin = metadata["origin"]

            is_set = v is not None

            arg = args.get_child_arg(k)
            if arg is None:
                raise NotImplementedError()
            vars_dict[k] = {
                "value": v,
                "desc": arg.doc.get_short_help("-- no description --"),
                "origin": origin,
                "is_set": is_set,
            }
            if metadata and "from_alias" in metadata.keys():
                vars_dict[k]["from_alias"] = metadata["from_alias"]

        result = {
            "task": task_expl,
            "input": frecklet_input,
            "vars": vars_dict,
            "args": args,
        }
        return result

    def render_vars_table(self, vars_dict: Mapping[str, Mapping[str, Any]]) -> Table:

        aliases: bool = False
        for arg_name, data in vars_dict.items():
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

        for arg_name, data in vars_dict.items():
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
                table.add_row(arg_name, value_string, origin)

        return table

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:

        _vars: Mapping[str, Any] = self.explain("vars")
        _tasks = self.explain("task.subtasks")

        _postprocess_task = self.explain("task.postprocess")

        msg = self.explain("task.meta.msg")
        yield f"[title]Task:[/title] {msg}"
        yield ""
        yield "[title]Variables:[/title]"
        vars = self.render_vars_table(_vars)
        yield vars

        yield ""
        yield "[title]Steps:[/title]"
        yield ""

        if len(_tasks) == 1:
            task = _tasks[0]
            for st in task["subtasks"]:
                yield f"  - [value]{st['meta']['msg']}[/value]"

            yield f"  - [value]{_postprocess_task['meta']['msg']}[/value]"
        else:

            for task in _tasks:
                yield f"  - [key2]{task['meta']['msg']}[/key2]"
                yield ""
                for st in task["subtasks"]:
                    yield f"      - [value]{st['meta']['msg']}[/value]"

            if _postprocess_task is not None:
                yield f"      - [value]{_postprocess_task['meta']['msg']}[/value]"
