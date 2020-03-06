# -*- coding: utf-8 -*-
from bring.defaults import BRINGISTRY_CONFIG
from frtls.types.utils import load_modules


_hi = load_modules(BRINGISTRY_CONFIG["modules"])  # type: ignore
hiddenimports = [x.__name__ for x in _hi]
