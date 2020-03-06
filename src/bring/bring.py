# -*- coding: utf-8 -*-

"""Main module."""
import json
import os
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional, Type, Union

from anyio import aopen, create_task_group
from bring.context import BringContextTing, BringStaticContextTing
from bring.defaults import (
    BRINGISTRY_CONFIG,
    BRING_CONTEXTS_FOLDER,
    BRING_DEFAULT_CONTEXTS_FOLDER,
    BRING_WORKSPACE_FOLDER,
)
from bring.mogrify import Transmogritory
from bring.utils import BringTaskDesc
from frtls.exceptions import FrklException
from frtls.files import ensure_folder
from frtls.tasks import FlattenParallelTasksAsync
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
    def __init__(self, name: str = None, meta: Dict[str, Any] = None):

        if name is None:
            name = "bring"

        ensure_folder(BRING_WORKSPACE_FOLDER)

        prototings: Iterable[Mapping] = BRINGISTRY_CONFIG["prototings"]  # type: ignore
        tings: Iterable[Mapping] = BRINGISTRY_CONFIG["tings"]  # type: ignore
        modules: Iterable[str] = BRINGISTRY_CONFIG["modules"]  # type: ignore
        classes: Iterable[Union[Type, str]] = BRINGISTRY_CONFIG[  # type: ignore
            "classes"
        ]

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

        self._dynamic_context_maker: TextFileTingMaker = self.create_ting(  # type: ignore
            "bring.types.config_file_context_maker", "bring.context_maker"
        )
        self._dynamic_context_maker.add_base_paths(BRING_CONTEXTS_FOLDER)

        self._default_contexts: Dict[str, BringStaticContextTing] = {}

        self._extra_contexts: Dict[str, BringContextTing] = {}
        self._initialized = False

        # self._task_watcher = TerminalRunWatcher(base_topic=BRING_TASKS_BASE_TOPIC)
        # self._task_watcher = PrintLineRunWatcher(base_topic=BRING_TASKS_BASE_TOPIC)

    async def init(self):
        if self._initialized:
            return

        await self._dynamic_context_maker.sync()

        async def add_default_context(fn: str):

            path = os.path.join(BRING_DEFAULT_CONTEXTS_FOLDER, fn)
            async with await aopen(path) as f:
                content = await f.read()

            context_name = fn.split(".")[0]
            if context_name in self._default_contexts:
                raise FrklException(
                    msg=f"Can't add context '{context_name}'.",
                    reason="Default context with that name already exists.",
                )

            json_content: Mapping[str, Any] = json.loads(content)
            ctx: BringStaticContextTing = self.create_ting(  # type: ignore
                "bring.types.contexts.default_context",
                f"bring.contexts.default.{context_name}",
            )
            ctx.input.set_values(ting_dict=json_content)
            self._default_contexts[context_name] = ctx

        async with create_task_group() as tg:
            for file_name in os.listdir(BRING_DEFAULT_CONTEXTS_FOLDER):
                if not file_name.endswith(".context"):
                    continue
                await tg.spawn(add_default_context, file_name)

            for context in self.contexts.values():
                await tg.spawn(context.get_values, "config")

        self._initialized = True

    def add_context(self, context_name: str, context: BringContextTing):

        self._extra_contexts[context_name] = context

    @property
    def contexts(self) -> Mapping[str, BringContextTing]:

        contexts: SubscripTings = self.get_ting(  # type: ignore
            "bring.contexts.dynamic"
        )
        result: Dict[str, BringContextTing] = {  # type: ignore
            x.split(".")[-1]: ctx for x, ctx in contexts.childs.items()  # type: ignore
        }

        result.update(self._extra_contexts)

        result.update(self._default_contexts)

        return result

    def get_context(self, context_name: str) -> Optional[BringContextTing]:

        return self.contexts.get(context_name)

    async def update(self):

        td = BringTaskDesc(
            name="update metadata", msg="updating metadata for all contexts"
        )
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
