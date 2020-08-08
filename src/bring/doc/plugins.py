# -*- coding: utf-8 -*-

import logging
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional

from anyio import create_task_group
from bring.bring import Bring
from bring.pkg_types import get_pkg_type_plugin_factory
from frkl.common.doc import Doc
from frkl.explain.explanation import Explanation


# class PluginDocManagement(object):
#     def __init__(self, plugin_manager: PluginManager):
#
#         self._plugin_manager: PluginManager = plugin_manager
#
#     def plugin_doc(self, plugin_name) -> Doc:
#
#         return self._plugin_manager.get_plugin_doc(plugin_name=plugin_name)

log = logging.getLogger("bring")


async def get_example_pkgs(
    bring: Bring, examples: Iterable[str]
) -> Mapping[str, Mapping[str, Any]]:

    pkgs: Dict[str, Mapping[str, Any]] = {}

    async def add_example(_pkg_name: str):
        pkg = await bring.get_pkg(_pkg_name)
        if pkg is None:
            log.warning(f"Can't retrieve package '{_pkg_name}")

        vals: Mapping[str, Any] = await pkg.get_values(resolve=True)  # type: ignore
        pkgs[_pkg_name] = vals

    async with create_task_group() as tg:

        for example in examples:
            await tg.spawn(add_example, example)

    return pkgs


class PluginExplanation(Explanation):
    def __init__(self, bring: Bring, plugin_name: str):

        self._bring: Bring = bring
        self._plugin_factory = get_pkg_type_plugin_factory(self._bring.arg_hive)

        self._plugin_name: str = plugin_name
        super().__init__()

    async def augment_metadata(self, current: MutableMapping[str, Any]) -> None:

        pass

    async def create_explanation_data(self) -> Mapping[str, Any]:

        plugin_doc: Doc = self._plugin_factory.get_plugin_doc(self._plugin_name)

        plugin_doc.extract_metadata("examples")

        result = {
            "name": self._plugin_name,
            "doc": plugin_doc,
        }

        await self.augment_metadata(result)

        return result


class PkgTypeExplanation(PluginExplanation):
    async def augment_metadata(self, current: MutableMapping[str, Any]) -> None:

        plugin = self._plugin_factory.get_singleton(self._plugin_name)

        args = plugin.get_args()
        record_arg = self._bring.arg_hive.create_record_arg(childs=args)
        current["args"] = record_arg

        examples: Optional[Iterable[str]] = current["doc"].get_metadata_value(
            "examples"
        )
        if examples:
            pkgs = await get_example_pkgs(bring=self._bring, examples=examples)
            current["examples"] = pkgs
        else:
            current["examples"] = {}


def get_all_pkg_type_explanations(bring: Bring) -> Mapping[str, PkgTypeExplanation]:

    f = get_pkg_type_plugin_factory(bring.arg_hive)

    explanations = {}
    for pn in sorted(f.plugin_names, key=lambda d: f"{d} "):
        expl = PkgTypeExplanation(bring, pn)
        explanations[pn] = expl

    return explanations
