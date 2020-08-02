# -*- coding: utf-8 -*-

import io
import logging
import os
from typing import Iterable, Mapping, Type, Union

from pkg_resources import DistributionNotFound, get_distribution

from bring.defaults import BRING_TEMP_CACHE
from frkl.common.filesystem import ensure_folder
from frkl.project_meta.app_environment import AppEnvironment


log = logging.getLogger("bring")

"""Top-level package for bring."""

__author__ = """Markus Binsteiner"""
__email__ = "markus@frkl.io"

try:
    # Change here if project is renamed and does not equal the package name
    dist_name = __name__
    __version__ = get_distribution(dist_name).version
except DistributionNotFound:

    try:
        version_file = os.path.join(os.path.dirname(__file__), "version.txt")

        if os.path.exists(version_file):
            with io.open(version_file, encoding="utf-8") as vf:
                __version__ = vf.read()
        else:
            __version__ = "unknown"

    except (Exception):
        pass

    if __version__ is None:
        __version__ = "unknown"

finally:
    del get_distribution, DistributionNotFound

BRING: AppEnvironment = AppEnvironment(main_module="bring")

ensure_folder(BRING_TEMP_CACHE)


def set_globals():

    import bring.interfaces.cli  # noqa

    global BRING

    from frkl.types.typistry import Typistry
    from bring.defaults import BRINGISTRY_INIT
    from freckles.core.freckles import Freckles
    from tings.tingistry import Tingistries

    if not BRING.get_singleton("typistry"):

        typistry: Typistry = Typistry()
        BRING.register_singleton(typistry)

        prototings: Iterable[Mapping] = BRINGISTRY_INIT["prototings"]  # type: ignore
        tings: Iterable[Mapping] = BRINGISTRY_INIT["tings"]  # type: ignore
        modules: Iterable[str] = BRINGISTRY_INIT["modules"]  # type: ignore
        classes: Iterable[Union[Type, str]] = BRINGISTRY_INIT["classes"]  # type: ignore

        tingistry = Tingistries.create("bring", typistry=typistry)
        tingistry.add_module_paths(*modules)
        tingistry.add_classes(*classes)
        for pt in prototings:
            pt_name = pt["prototing_name"]
            existing = tingistry.get_ting(pt_name)
            if existing is None:
                tingistry.register_prototing(**pt)

        for t in tings:
            tingistry.create_ting(**t)
        BRING.register_singleton(tingistry)

        freckles = Freckles.get_freckles_ting(
            tingistry=tingistry, name="bring.freckles"
        )
        BRING.register_singleton(freckles)


set_globals()
