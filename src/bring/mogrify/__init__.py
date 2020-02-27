# -*- coding: utf-8 -*-
import collections
import tempfile
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Optional, Union

from bring.defaults import BRING_WORKSPACE_FOLDER
from frtls.exceptions import FrklException
from frtls.tasks import SerialTasksAsync, SingleTaskAsync
from frtls.templating import replace_strings_in_obj
from frtls.types.utils import generate_valid_identifier
from tings.ting import SimpleTing, Ting


if TYPE_CHECKING:
    from bring.bring import Bring


def assemble_mogrifiers(
    mogrifier_list: Iterable[Union[Mapping, str]],
    vars: Mapping[str, Any],
    args: Mapping[str, Any],
    task_desc: Mapping[str, Any] = None,
) -> Iterable[Mapping]:

    # TODO: validate vars
    if not vars or not args:
        _data: Iterable[Union[Mapping, str]] = mogrifier_list
    else:
        relevant_vars = {}
        for k, v in vars.items():
            if k in args.keys():
                relevant_vars[k] = v

        _data = replace_strings_in_obj(
            source_obj=mogrifier_list, replacement_dict=relevant_vars
        )

    mog_data = []
    for index, _mog in enumerate(_data):
        if isinstance(_mog, str):
            mog: Mapping[str, Any] = {"type": _mog, "_task_desc": task_desc}
        elif isinstance(_mog, collections.Mapping):
            mog = _mog
            if "_task_desc" not in mog.keys():
                mog["_task_desc"] = task_desc
        elif isinstance(_mog, collections.Iterable):
            mog = assemble_mogrifiers(
                mogrifier_list=_mog, vars=vars, args=args, task_desc=task_desc
            )
        else:
            raise FrklException(
                msg="Can't create transmogrifier.",
                reason=f"Invalid configuration type '{type(_mog)}': {_mog}",
            )
        mog_data.append(mog)

    return mog_data


class Mogrifiception(FrklException):
    def __init__(self, *args, mogrifier: "Mogrifier" = None, **kwargs):

        self._mogrifier = mogrifier

        super().__init__(*args, **kwargs)


class Mogrifier(SimpleTing, SingleTaskAsync):
    def __init__(
        self, name: str, meta: Optional[Mapping[str, Any]] = None, **kwargs
    ) -> None:

        self._mogrify_result: Optional[Mapping[str, Any]] = None

        Ting.__init__(self, name=name, meta=meta)
        SingleTaskAsync.__init__(self, self.get_values, **kwargs)

    @abstractmethod
    async def cleanup(self, result: Mapping[str, Any], *value_names, **requirements):

        pass

    def create_temp_dir(self, prefix=None):
        if prefix is None:
            prefix = self._name
        tempdir = tempfile.mkdtemp(prefix=f"{prefix}_", dir=BRING_WORKSPACE_FOLDER)
        return tempdir

    @abstractmethod
    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:
        pass

    async def retrieve(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        if self._mogrify_result is None:
            self._mogrify_result = await self.mogrify(*value_names, **requirements)

        return self._mogrify_result


class Transmogrificator(SerialTasksAsync):
    def __init__(self, bring: "Bring", *transmogrifiers: Mogrifier, **kwargs):

        self._bring = bring

        super().__init__(**kwargs)

        self._current: Optional[Mogrifier] = None
        self._last_item: Optional[Mogrifier] = None

        self._mogrify_result: Optional[Mapping[str, Any]] = None

        for tm in transmogrifiers:
            self.add_mogrifier(tm)

    def add_mogrifier(self, mogrifier: Mogrifier) -> None:

        if self._current is not None:
            mogrifier.set_requirements(self._current)

        mogrifier._parent_task = self

        self.add_task(mogrifier)
        self._current = mogrifier

        self._last_item = self._current

    async def transmogrify(self) -> Mapping[str, Any]:

        await self.run_async(*self._bring.watchers)

        self._mogrify_result = self._last_item.current_state

        return self._mogrify_result

    def retrieve_result(self):

        return self._mogrify_result


class Transmogritory(object):
    def __init__(self, bring: "Bring"):

        self._bring = bring
        self._plugin_manager = self._bring.get_plugin_manager(
            "bring.mogrify.Mogrifier", plugin_type="instance"
        )
        for k, v in self._plugin_manager._plugins.items():
            self._bring.register_prototing(f"bring.mogrify.plugins.{k}", v)

    def create_mogrifier_ting(
        self,
        mogrify_plugin: str,
        pipeline_id: str,
        index: str,
        input_vals: Mapping[str, Any],
    ):

        plugin = self._plugin_manager.get_plugin(mogrify_plugin)
        if not plugin:
            raise FrklException(
                msg="Can't create transmogrifier.",
                reason=f"No mogrify plugin '{mogrify_plugin}' available.",
            )

        ting: Mogrifier = self._bring.create_ting(
            prototing=f"bring.mogrify.plugins.{mogrify_plugin}",
            ting_name=f"bring.mogrify.pipelines.{pipeline_id}.{mogrify_plugin}_{index}",
        )
        ting.input.set_values(**input_vals)

        return ting

    def create_transmogrificator(
        self,
        data: Iterable[Union[Mapping, str]],
        vars: Mapping[str, Any],
        args: Mapping[str, Any],
        **kwargs,
    ) -> Transmogrificator:

        mogrifier_list = assemble_mogrifiers(mogrifier_list=data, vars=vars, args=args)

        pipeline_id = generate_valid_identifier(prefix="pipe_", length_without_prefix=6)

        transmogrificator = Transmogrificator(self._bring, **kwargs)

        for index, _mog in enumerate(mogrifier_list):

            if isinstance(_mog, collections.Mapping):

                mogrify_plugin = _mog.pop("type", None)
                if not mogrify_plugin:
                    raise FrklException(
                        msg="Can't create transmogrificator.",
                        reason=f"No mogrifier type specified in config: {mogrifier_list}",
                    )

                ting = self.create_mogrifier_ting(
                    mogrify_plugin=mogrify_plugin,
                    pipeline_id=pipeline_id,
                    index=str(index),
                    input_vals=_mog,
                )
                transmogrificator.add_mogrifier(ting)
            elif isinstance(_mog, collections.Iterable):

                tms = []
                for j, child_list in enumerate(_mog):

                    tings = []
                    for k, m in enumerate(child_list):
                        mogrify_plugin = m.pop("type", None)
                        task_desc = m.pop("_task_desc", {})
                        if not mogrify_plugin:
                            raise FrklException(
                                msg="Can't create transmogrificator.",
                                reason=f"No mogrifier type specified in config: {mogrifier_list}",
                            )
                        t = self.create_mogrifier_ting(
                            mogrify_plugin=mogrify_plugin,
                            pipeline_id=pipeline_id,
                            index=f"{index}_{j}_{k}",
                            input_vals=m,
                        )
                        tings.append(t)

                    tm = Transmogrificator(self._bring, *tings, **task_desc)
                    tms.append(tm)

                merge = self.create_mogrifier_ting(
                    mogrify_plugin="merge",
                    pipeline_id=pipeline_id,
                    index=f"{index}_merge",
                    input_vals={},
                )
                ting = self.create_mogrifier_ting(
                    mogrify_plugin="parallel_pkg_merge",
                    pipeline_id=pipeline_id,
                    index=str(index),
                    input_vals={
                        "transmogrificators": tms,
                        "watchers": self._bring.watchers,
                        "merge": merge,
                    },
                )
                transmogrificator.add_mogrifier(ting)
            else:
                raise FrklException(
                    msg="Can't create transmogrificator.",
                    reason=f"Invalid configuration type '{type(_mog.__class__)}': {_mog}",
                )

        return transmogrificator
