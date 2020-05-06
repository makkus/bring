# -*- coding: utf-8 -*-
from rich.console import Console
from rich.style import Style
from rich.theme import Theme


LIGHT_THEME = Theme(
    {
        "title": Style.parse("bold bright_black"),
        "key": Style.parse("bold grey35"),
        "key2": Style.parse("grey42"),
    }
)
console = Console(theme=LIGHT_THEME)
