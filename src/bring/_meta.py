# -*- coding: utf-8 -*-
from bring.defaults import BRINGISTRY_PRELOAD_MODULES
from frtls.types.utils import load_modules


app_name = "bring"

_hi = load_modules(BRINGISTRY_PRELOAD_MODULES)  # type: ignore
pyinstaller = {"hiddenimports": [x.__name__ for x in _hi]}
