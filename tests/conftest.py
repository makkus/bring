#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    Dummy conftest.py for bring.

    If you don't know what this is for, just leave it empty.
    Read more about conftest.py under:
    https://pytest.org/latest/plugins.html
"""
# import pytest
import pytest
from bring.bring import Bring
from bring.config.bring_config import BringConfig
from freckles.core.freckles import Freckles


@pytest.fixture
def bring_obj() -> Bring:

    # tingistry = Tingistries().create("freckles", modules=BRINGISTRY_PRELOAD_MODULES)
    freckles = Freckles.get_default()
    # tingistry_obj = freckles.tingistry

    bring_config = BringConfig(freckles=freckles)

    config = {"indexes": ["binaries"]}
    bring_config.set_config(config)

    bring = bring_config.get_bring()

    return bring
