# -*- coding: utf-8 -*-
import os

from bring.defaults import BRINGISTRY_PRELOAD_MODULES
from frtls.types.utils import load_modules


app_name = "bring"

_hi = load_modules(BRINGISTRY_PRELOAD_MODULES)  # type: ignore

pyinstaller = {"hiddenimports": [x.__name__ for x in _hi]}
if os.name != "nt":
    import pkgutil
    import jinxed.terminfo

    _additional_hidden_imports = [
        mod.name
        for mod in pkgutil.iter_modules(jinxed.terminfo.__path__, "jinxed.terminfo.")
    ]
    pyinstaller["hiddenimports"].extend(_additional_hidden_imports)
