# -*- coding: utf-8 -*-
import logging
from typing import Any, Iterable, Mapping, Union

from freckles.core.frecklet import Frecklet


log = logging.getLogger("freckles")


class FreckletList(object):
    def __init__(self, *frecklets: Iterable[Union[str, Mapping[str, Any], Frecklet]]):

        self._frecklets = frecklets
