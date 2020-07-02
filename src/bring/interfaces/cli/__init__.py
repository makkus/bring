# -*- coding: utf-8 -*-
import os
from typing import Optional

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
        "key2": Style.parse("italic"),
        "value": Style.parse(""),
    }
)

width = os.environ.get("BRING_CONSOLE_WIDTH", None)
if width is not None:
    _width: Optional[int] = int(width)
else:
    _width = None

console = Console(theme=LIGHT_THEME, width=_width)
