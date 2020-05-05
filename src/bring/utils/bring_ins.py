# -*- coding: utf-8 -*-
from bring.bringins import BringIns


async def explain_bring_ins(bring_ins: BringIns) -> str:

    args = bring_ins.get_var_names()

    print(args)

    return "xxx"
