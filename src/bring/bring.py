# -*- coding: utf-8 -*-

"""Main module."""
import os
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional, Type, Union

from bring.context import BringContextTing
from bring.defaults import (
    BRINGISTRY_CONFIG,
    BRING_CONTEXTS_FOLDER,
    BRING_WORKSPACE_FOLDER,
)
from bring.interfaces.cli.task_watcher import TerminalRunWatcher
from bring.mogrify import Transmogritory
from frtls.files import ensure_folder
from frtls.tasks import FlattenParallelTasksAsync, TaskDesc
from tings.makers.file import TextFileTingMaker
from tings.ting.tings import SubscripTings
from tings.tingistry import Tingistry


DEFAULT_TRANSFORM_PROFILES = {
    "executable": [
        {"type": "file_filter", "exclude": ["*~", "~*"]},
        {"type": "set_mode", "config": {"set_executable": True, "set_readable": True}},
    ]
}


class Bring(Tingistry):
    def __init__(self, name: str, meta: Dict[str, Any] = None):

        ensure_folder(BRING_WORKSPACE_FOLDER)

        prototings: Iterable[Mapping] = BRINGISTRY_CONFIG["prototings"]  # type: ignore
        tings: Iterable[Mapping] = BRINGISTRY_CONFIG["tings"]  # type: ignore
        modules: Iterable[str] = BRINGISTRY_CONFIG["modules"]  # type: ignore
        classes: Iterable[Union[Type, str]] = BRINGISTRY_CONFIG[
            "classes"
        ]  # type: ignore

        super().__init__(
            name,
            prototings=prototings,
            tings=tings,
            modules=modules,
            classes=classes,
            meta=meta,
        )

        config: MutableMapping[str, Any] = {}
        for k, v in os.environ.items():
            k = k.lower()
            if not k.startswith("bring_"):
                continue
            config[k[6:]] = v

        config["bringistry"] = self

        self._typistry.get_plugin_manager("pkg_resolver", plugin_config=config)

        self._transmogritory = Transmogritory(self)

        self._context_maker: TextFileTingMaker = self.create_ting(
            "bring.types.config_file_context_maker", "bring.context_maker"
        )  # type: ignore

        self._context_maker.add_base_paths(BRING_CONTEXTS_FOLDER)

        self._initialized = False

        self._task_watcher = TerminalRunWatcher()

    async def init(self):
        if not self._initialized:
            await self._context_maker.sync()

    @property
    def contexts(self) -> Mapping[str, BringContextTing]:

        contexts: SubscripTings = self.get_ting("bring.contexts")  # type: ignore
        return {
            x.split(".")[-1]: ctx for x, ctx in contexts.childs.items()  # type: ignore
        }

    def get_context(self, context_name: str) -> Optional[BringContextTing]:

        return self.contexts.get(context_name)

    async def update(self):

        td = TaskDesc(name="update metadata", msg="updating metadata for all contexts")
        tasks = FlattenParallelTasksAsync(desc=td)
        for context in self.contexts.values():
            t = await context._create_update_tasks()
            tasks.add_task(t)

        await tasks.run_async()

    def install(self, pkgs):
        pass

    # async def get_all_pkgs(self) -> Dict[str, PkgTing]:
    #
    #     result = {}
    #     for context_name, context in self.contexts.items():
    #         pkgs = await context.get_pkgs()
    #         for pkg_name, pkg in pkgs.pkgs.items():
    #             result[f"{context_name}:{pkg_name}"] = pkg
    #
    #     return result
