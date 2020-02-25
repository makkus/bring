# -*- coding: utf-8 -*-
import collections
import tempfile
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Optional, Union

from bring.defaults import BRING_WORKSPACE_FOLDER
from frtls.exceptions import FrklException
from frtls.tasks import SerialTasksAsync, SingleTaskAsync
from frtls.types.utils import generate_valid_identifier
from tings.ting import SimpleTing, Ting


if TYPE_CHECKING:
    from bring.bring import Bring
    from bring.pkg import PkgTing


class Mogrifiception(FrklException):
    def __init__(self, *args, mogrifier: "Mogrifier" = None, **kwargs):

        self._mogrifier = mogrifier

        super().__init__(*args, **kwargs)


class Mogrifier(SimpleTing, SingleTaskAsync):
    def __init__(
        self, name: str, meta: Optional[Mapping[str, Any]] = None, **kwargs
    ) -> None:

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

        result = await self.mogrify(*value_names, **requirements)

        return result


class Transmogrificator(SerialTasksAsync):
    def __init__(self, *transmogrifiers: Mogrifier, **kwargs):

        super().__init__(**kwargs)
        current = None
        for tm in transmogrifiers:
            if current is not None:
                tm.set_requirements(current)

            self.add_task(tm)
            current = tm

        self._last_item = current

    async def transmogrify(self, *watchers) -> Mapping[str, Any]:

        await self.run_async(*watchers)

        return self._last_item.current_state


class Transmogritory(object):
    def __init__(self, bring: "Bring"):

        self._bring = bring
        self._plugin_manager = self._bring.get_plugin_manager(
            "bring.mogrify.Mogrifier", plugin_type="instance"
        )
        for k, v in self._plugin_manager._plugins.items():
            self._bring.register_prototing(f"bring.mogrify.plugins.{k}", v)

    def create_transmogrificator(
        self, data: Iterable[Union[Mapping, str]], pkg: "PkgTing" = None
    ):

        # import pp
        # pp(self._plugin_manager.__dict__)
        # print(data)

        pipeline_id = generate_valid_identifier(prefix="pipe_", length_without_prefix=6)

        mogrifiers = []
        for index, _mog in enumerate(data):
            if isinstance(_mog, str):
                mog: Mapping[str, Any] = {"type": _mog}
            elif isinstance(_mog, collections.Mapping):
                mog = _mog
            else:
                raise FrklException(
                    msg="Can't create transmogrifier.",
                    reason=f"Invalid configuration type '{type(_mog)}': {_mog}",
                )

            mogrify_plugin = mog.pop("type", None)
            if not mogrify_plugin:
                raise FrklException(
                    msg="Can't create transmogrifier.",
                    reason=f"No mogrifier type specified in config: {mog}",
                )

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
            ting.input.set_values(**mog)
            mogrifiers.append(ting)

        transmogrificator = Transmogrificator(
            *mogrifiers, name=pkg.name, msg=f"installing {pkg.name}..."
        )
        return transmogrificator
