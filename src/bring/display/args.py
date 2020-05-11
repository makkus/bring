# -*- coding: utf-8 -*-
from typing import Any, List, Mapping, MutableMapping, Optional

from frtls.doc import Doc
from rich import box
from rich.table import Table


def prepare_table_items(
    args: Mapping[str, Any], aliases: Mapping[str, Any]
) -> List[MutableMapping[str, Any]]:

    items: List[MutableMapping] = []
    for k, v in sorted(args.items()):

        arg_aliases = aliases.get(k, {})
        # aliases_reverse: Dict[str, List[str]] = {}
        # allowed_no_alias = []

        allowed = v.get("allowed", [])

        if k != "version":
            allowed = sorted(allowed)
        # for a in allowed:
        #     if a in arg_aliases.keys():
        #         aliases_reverse.setdefault(arg_aliases[a], []).append(a)
        #     else:
        #         allowed_no_alias.append(a)

        # if v["default"] is not None:
        #     default = v["default"]
        # else:
        #     default = ""

        # if allowed_no_alias:
        #     allowed_first = allowed_no_alias[0]
        # else:
        #     allowed_first = ""
        # if v.get("required", True):
        #     req = "yes"
        # else:
        #     req = "no"

        # if allowed_first in aliases_reverse.keys() and aliases_reverse[allowed_first]:
        #     alias = aliases_reverse[allowed_first][0]
        # else:
        #     alias = ""

        doc = Doc(v.get("doc", {}))

        item = {
            "name": k,
            "desc": doc.get_short_help(use_help=True),
            "type": v["type"],
            "required": v.get("required", True),
            "default": v["default"],
            "allowed": allowed,
            "aliases": arg_aliases,
        }
        items.append(item)

    return items


def create_table_from_pkg_args(
    args: Mapping[str, Any],
    aliases: Mapping[str, Any],
    limit_allowed: Optional[int] = None,
) -> Table:

    items = prepare_table_items(args=args, aliases=aliases)

    table = Table(box=box.SIMPLE)
    table.add_column("Name", style="dark_orange")
    table.add_column("  Details")

    for details in items:

        default = details["default"]
        if default is None:
            default = ""
        else:
            default = f"[green]{default}[/green]"

        if details["required"]:
            required = "yes"
        else:
            required = "no"

        allowed = details["allowed"]
        aliases = details["aliases"]

        table.add_row(details["name"], f"  [italic]{details['desc']}[/italic]")
        arg_table = Table(show_header=False, box=box.SIMPLE)
        arg_table.add_column("key")
        arg_table.add_column("value", style="italic")
        arg_table.add_row("default", default)
        arg_table.add_row("required", required)
        arg_table.add_row("type", details["type"])

        if allowed and limit_allowed:
            _allowed: MutableMapping[str, List[str]] = {}

            for a in allowed:
                if a in aliases.keys():
                    _allowed.setdefault(aliases[a], []).append(a)
                    # _allowed.append(f"{a} (aliases: {', '.join(aliases[a])}")
                else:
                    _allowed.setdefault(a, [])

            _allowed_strings = []
            for _arg, _aliases in _allowed.items():
                if not _aliases:
                    a = _arg
                elif len(_aliases) == 1:
                    a = f"{_arg} (alias: {_aliases[0]})"
                else:
                    a = f"{_arg} (aliases: {', '.join(_aliases)})"
                _allowed_strings.append(a)
            arg_table.add_row("allowed", _allowed_strings[0])
            if limit_allowed and len(_allowed_strings) > limit_allowed:
                _allowed_strings = _allowed_strings[0:limit_allowed] + ["...", "..."]
            for a in _allowed_strings[1:]:
                arg_table.add_row("", a)

        table.add_row("", arg_table)

    return table


# def create_table_from_pkg_args_old(
#             args: Mapping[str, Any],
#             aliases: Mapping[str, Any],
#             limit_allowed: Optional[int] = None,
#     ) -> Table:
#
#     table = Table(box=box.SIMPLE)
#     table.add_column("Name", no_wrap=True, style="bold dark_orange")
#     table.add_column("Description", no_wrap=False, style="italic")
#     table.add_column("Type", no_wrap=True)
#     table.add_column("Required", no_wrap=True)
#     table.add_column("Default", no_wrap=True, style="deep_sky_blue4")
#     table.add_column("Allowed", no_wrap=True)
#     table.add_column("Alias", no_wrap=True)
#
#     for k, v in sorted(args.items()):
#
#         arg_aliases = aliases.get(k, {})
#         aliases_reverse: Dict[str, List[str]] = {}
#         allowed_no_alias = []
#
#         allowed = v.get("allowed", [])
#         if limit_allowed is not None and len(allowed) > limit_allowed:
#             allowed = allowed[0:limit_allowed] + ["..."]
#
#         if k != "version":
#             allowed = sorted(allowed)
#         for a in allowed:
#             if a in arg_aliases.keys():
#                 aliases_reverse.setdefault(arg_aliases[a], []).append(a)
#             else:
#                 allowed_no_alias.append(a)
#
#         if v["default"] is not None:
#             default = v["default"]
#         else:
#             default = ""
#
#         if allowed_no_alias:
#             allowed_first = allowed_no_alias[0]
#         else:
#             allowed_first = ""
#         if v.get("required", True):
#             req = "yes"
#         else:
#             req = "no"
#
#         if allowed_first in aliases_reverse.keys() and aliases_reverse[allowed_first]:
#             alias = aliases_reverse[allowed_first][0]
#         else:
#             alias = ""
#
#         doc = Doc(v.get("doc", {}))
#         table.add_row(
#             k,
#             doc.get_short_help(use_help=True),
#             v["type"],
#             req,
#             default,
#             allowed_first,
#             alias,
#         )
#         if (
#             allowed_first in aliases_reverse.keys()
#             and len(aliases_reverse[allowed_first]) > 1
#         ):
#             for alias in aliases_reverse[allowed_first][1:]:
#                 table.add_row("", "", "", "", "", "", alias)
#
#         if len(allowed_no_alias) > 1:
#             for item in allowed_no_alias[1:]:
#                 if item in aliases_reverse.keys() and aliases_reverse[item]:
#                     alias = aliases_reverse[item][0]
#                 else:
#                     alias = ""
#                 table.add_row("", "", "", "", "", item, alias)
#
#                 if item in aliases_reverse.keys() and len(aliases_reverse[item]) > 1:
#                     for alias in aliases_reverse[item][1:]:
#                         table.add_row("", "", "", "", "", "", alias)
#
#         table.add_row("", "", "", "", "", "", "")
#
#     return table
