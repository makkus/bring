# -*- coding: utf-8 -*-
from rich.console import Console
from rich.style import Style
from rich.theme import Theme


bring_style = Style(color="black", blink=False, bold=False, bgcolor=None)

bring_code_theme = "friendly"
bring_code_theme = "solarized-light"

LIGHT_THEME = Theme(
    {
        "title": Style.parse("bold bright_black"),
        "key": Style.parse("bold grey35"),
        "key2": Style.parse("grey42"),
    }
)
console = Console(theme=LIGHT_THEME)
