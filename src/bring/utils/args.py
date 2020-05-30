# -*- coding: utf-8 -*-
from typing import Any, Dict, List, Mapping, Optional

from frtls.doc.doc import Doc
from rich import box
from rich.table import Table


def create_table_from_pkg_args(
    args: Mapping[str, Any],
    aliases: Mapping[str, Any],
    limit_allowed: Optional[int] = None,
) -> Table:

    table = Table(box=box.SIMPLE)
    table.add_column("Name", no_wrap=True, style="bold dark_orange")
    table.add_column("Description", no_wrap=False, style="italic")
    table.add_column("Type", no_wrap=True)
    table.add_column("Required", no_wrap=True)
    table.add_column("Default", no_wrap=True, style="deep_sky_blue4")
    table.add_column("Allowed", no_wrap=True)
    table.add_column("Alias", no_wrap=True)

    for k, v in sorted(args.items()):

        arg_aliases = aliases.get(k, {})
        aliases_reverse: Dict[str, List[str]] = {}
        allowed_no_alias = []

        allowed = v.get("allowed", [])
        if limit_allowed is not None and len(allowed) > limit_allowed:
            allowed = allowed[0:limit_allowed] + ["..."]

        if k != "version":
            allowed = sorted(allowed)
        for a in allowed:
            if a in arg_aliases.keys():
                aliases_reverse.setdefault(arg_aliases[a], []).append(a)
            else:
                allowed_no_alias.append(a)

        if v["default"] is not None:
            default = v["default"]
        else:
            default = ""

        if allowed_no_alias:
            allowed_first = allowed_no_alias[0]
        else:
            allowed_first = ""
        doc = Doc(v.get("doc", {}))
        if v.get("required", True):
            req = "yes"
        else:
            req = "no"

        if allowed_first in aliases_reverse.keys() and aliases_reverse[allowed_first]:
            alias = aliases_reverse[allowed_first][0]
        else:
            alias = ""

        table.add_row(
            k, doc.get_short_help(), v["type"], req, default, allowed_first, alias
        )
        if (
            allowed_first in aliases_reverse.keys()
            and len(aliases_reverse[allowed_first]) > 1
        ):
            for alias in aliases_reverse[allowed_first][1:]:
                table.add_row("", "", "", "", "", "", alias)

        if len(allowed_no_alias) > 1:
            for item in allowed_no_alias[1:]:
                if item in aliases_reverse.keys() and aliases_reverse[item]:
                    alias = aliases_reverse[item][0]
                else:
                    alias = ""
                table.add_row("", "", "", "", "", item, alias)

                if item in aliases_reverse.keys() and len(aliases_reverse[item]) > 1:
                    for alias in aliases_reverse[item][1:]:
                        table.add_row("", "", "", "", "", "", alias)

        table.add_row("", "", "", "", "", "", "")

    return table
