# -*- coding: utf-8 -*-
from bring.defaults import BRINGISTRY_CONFIG as _bc
from frtls.types.utils import load_modules


app_name = "bring"

_hi = load_modules(_bc["modules"])  # type: ignore
pyinstaller = {"hiddenimports": [x.__name__ for x in _hi]}
