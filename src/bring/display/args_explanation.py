# -*- coding: utf-8 -*-
import collections
from typing import Any, Mapping, Optional, Union

from frtls.args.arg import Arg, RecordArg
from frtls.args.hive import ArgHive
from frtls.doc.explanation import Explanation
from frtls.formats.output_formats import serialize
from frtls.templating import process_string_template
from frtls.types.utils import is_instance_or_subclass
from rich.console import Console, ConsoleOptions, RenderResult


def to_value_string(value: Any):

    if value is None:
        return "-- no value --"
    elif isinstance(value, str):
        return value
    elif isinstance(value, bool):
        return "true" if value else "false"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, (collections.abc.Mapping, collections.abc.Iterable)):
        string = serialize(value, format="yaml").strip()
        return string
    else:
        return str(value)


ARGS_TEMPLATE = """[key]{{ arg_name }}[/key]: [italic]{{ short_help }}[/italic]

{% if desc %}  [key2]desc[/key2]: [italic]{{ desc | wordwrap(_terminal_width-10) | replace('\n', '\n        ') }}[/italic]

{% endif %}  [key2]type[/key2]: [italic]{{ arg.scalar_type }}[/italic]
  [key2]required[/key2]: [italic]{{ required }}[/italic]
{% if '\n' in default_string %}
  [key2]default[/key2]:[italic]
{{ default_string | indent(4, first=True) }}
{% else %}
  [key2]default[/key2]: [italic]{{ default_string }}[/italic]{% endif %}
{% if '\n' in value_string %}
  [key2]value[/key2]:[italic]
{{ value_string | indent(4, first=True) }}
{% else %}
  [key2]value[/key2]: [italic]{{ value_string }}[/italic]
{% endif %}
"""

ARGS_TEMPLATE_SHORT = """[key]{{ arg_name }}[/key]: [italic]{{ short_help }}[/italic]
  [key2]type[/key2]: [italic]{{ arg.scalar_type }}[/italic]{% if '\n' in value_string %}
  [key2]value[/key2]:[italic]
{{ value_string | indent(4, first=True) }}
{% else %}
  [key2]value[/key2]: [italic]{{ value_string }}[/italic]
{% endif %}
"""


class ArgsExplanation(Explanation):
    def __init__(
        self,
        data: Mapping[str, Any],
        args: Union[RecordArg, Mapping[str, Any]],
        arg_hive: Optional[ArgHive] = None,
    ):

        if arg_hive is None:
            arg_hive = ArgHive()
        self._arg_hive = arg_hive
        if not is_instance_or_subclass(args, RecordArg):
            if not isinstance(args, collections.abc.Mapping):
                raise TypeError(
                    f"Can't create explanation object for arguments, invalid type for childs: {type(args)}"
                )
            args = arg_hive.create_record_arg(childs=args)
        self._args: RecordArg = args  # type: ignore

        self._full: bool = False

        super().__init__(data)

    async def create_explanation_data(self) -> Mapping[str, Any]:

        validated = self._args.validate(self.data, raise_exception=False)

        result = {}

        for arg_name, arg in self._args.childs.items():
            value = validated.get(arg_name, "-- not set --")
            result[arg_name] = {
                "value": value,
                "arg": arg,
                "input": self.data.get(arg_name, "-- not set --"),
            }

        return result

    def __console__(self, console: Console, options: ConsoleOptions) -> RenderResult:

        result = []
        for arg_name, arg_data in self.explanation_data.items():

            arg: Arg = arg_data["arg"]
            doc = arg.doc

            value = arg_data["value"]
            value_string = to_value_string(value)

            value_type = arg

            default = arg.default
            if default is None:
                default = "-- no default --"

            repl_dict = {
                "arg_name": arg_name,
                "arg": arg_data["arg"],
                "doc": doc,
                "short_help": doc.get_short_help(default="No description available."),
                "desc": doc.get_help(default=None, use_short_help=False),
                "value": value,
                "value_string": value_string,
                "value_type": value_type,
                "default": default,
                "default_string": to_value_string(default),
                "required": "true" if arg.required else "false",
                "_terminal_width": console.width,
            }

            if not self._full:
                template = ARGS_TEMPLATE_SHORT
            else:
                template = ARGS_TEMPLATE
            rendered = process_string_template(template, repl_dict)

            result.append(rendered)
            result.append("")

            # result.append(f"[key]{arg_name}[/key]")
            # arg: Arg = arg_data["arg"]
            # doc: Doc = arg.doc
            # desc = doc.get_help(default="no description available", use_short_help=True).strip()
            # if "\n" in desc:
            #     lines = desc.split("\n")
            #     result.append(f"  [key2]desc[/key2]: [value]{lines[0]}[/value]")
            #     for item in lines[1:]:
            #         result.append(f"        [value]{item}[/value]")
            # else:
            #     result.append(f"  [key2]desc[/key2]: [value]{desc}[/value]")
            # result.append(f"  [key2]type[/key2]: [value]{arg.id}[/value]")
            # if "\n" in value_string:
            #     result.append("  [key2]value[/key2]")
            #     for item in value_string.split("\n"):
            #         result.append(f"    [value]{item}[/value]")
            # else:
            #     result.append(f"  [key2]value[/key2]: [value]{value}[/value]")

        return result
