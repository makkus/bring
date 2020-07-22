# -*- coding: utf-8 -*-
from bring.defaults import BRINGISTRY_PRELOAD_MODULES
from frkl.common.types import load_modules


project_name = "bring"
exe_name = "bring"
project_main_module = "bring"

_hi = load_modules(BRINGISTRY_PRELOAD_MODULES)  # type: ignore

pyinstaller = {"hiddenimports": [x.__name__ for x in _hi]}
# if os.name == "nt":
#     import pkgutil
#     import jinxed.terminfo
#
#     _additional_hidden_imports = [
#         mod.name
#         for mod in pkgutil.iter_modules(jinxed.terminfo.__path__, "jinxed.terminfo.")
#     ]
#     pyinstaller["hiddenimports"].extend(_additional_hidden_imports)
