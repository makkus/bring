# -*- coding: utf-8 -*-
from asyncclick import HelpFormatter


class BringHelpFormatter(HelpFormatter):
    def __init__(self, **kwargs):

        # ignore width/max_width
        super().__init__(width=10, max_width=10)
