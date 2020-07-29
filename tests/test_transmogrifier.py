# -*- coding: utf-8 -*-
import collections

import pytest
from bring.bring import Bring
from bring.mogrify import Transmogrificator
from bring.pkg_index.pkg import PkgTing


@pytest.mark.anyio
async def test_transmogrifier(bring_obj: Bring):

    # m = await bring_obj.config.get_config_dict()
    await bring_obj.add_all_config_indexes()

    pkg = await bring_obj.get_pkg("fd")
    assert isinstance(pkg, PkgTing)

    vars = {}
    vars["version"] = "latest"
    vars["os"] = "linux"
    vars["arch"] = "x86_64"

    tm: Transmogrificator = await pkg.create_transmogrificator(vars=vars)

    assert isinstance(tm, Transmogrificator)

    result = await tm.run_async()
    rv = result.result_value
    assert isinstance(rv, collections.abc.Mapping)
    assert "folder_path" in rv.keys()
