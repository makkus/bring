# -*- coding: utf-8 -*-

"""Main module."""
import json
import os
import threading
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
from frtls.args.hive import ArgHive
from frtls.async_helpers import wrap_async_task
from frtls.exceptions import FrklException
from frtls.files import ensure_folder
from frtls.tasks import FlattenParallelTasksAsync
from tings.makers.file import TextFileTingMaker
from tings.ting import SimpleTing
from tings.ting.tings import SubscripTings
from tings.tingistry import Tingistry


DEFAULT_TRANSFORM_PROFILES = {
    "executable": [
        {"type": "file_filter", "exclude": ["*~", "~*"]},
        {"type": "set_mode", "config": {"set_executable": True, "set_readable": True}},
    ]
}


class Bring(SimpleTing):
    def __init__(self, name: str = None, meta: Optional[Mapping[str, Any]] = None):

        prototings: Iterable[Mapping] = BRINGISTRY_CONFIG["prototings"]  # type: ignore
        tings: Iterable[Mapping] = BRINGISTRY_CONFIG["tings"]  # type: ignore
        modules: Iterable[str] = BRINGISTRY_CONFIG["modules"]  # type: ignore
        classes: Iterable[Union[Type, str]] = BRINGISTRY_CONFIG[  # type: ignore
            "classes"
        ]

        if name is None:
            name = "bring"

        ensure_folder(BRING_WORKSPACE_FOLDER)

        if meta is None:
            raise Exception(
                "Can't create 'bring' object: 'meta' argument not provided, this is a bug"
            )

        self._tingistry_obj: Tingistry = meta["tingistry"]

        self._tingistry_obj.add_module_paths(*modules)
        self._tingistry_obj.add_classes(*classes)

        if prototings:
            for pt in prototings:
                self._tingistry_obj.register_prototing(**pt)

        if tings:
            for t in tings:
                self._tingistry_obj.create_ting(**t)

        super().__init__(name=name, meta=meta)

        config: MutableMapping[str, Any] = {}
        for k, v in os.environ.items():
            k = k.lower()
            if not k.startswith("bring_"):
                continue
            config[k[6:]] = v

        config["bringistry"] = self

        self.typistry.get_plugin_manager("pkg_resolver", plugin_config=config)

        self._transmogritory = Transmogritory(self._tingistry_obj)

        self._dynamic_context_maker: Optional[TextFileTingMaker] = None

        self._default_contexts: Dict[str, BringStaticContextTing] = {}

        self._extra_contexts: Dict[str, BringContextTing] = {}
        self._initialized = False

        self._init_lock = threading.Lock()

        # self._task_watcher = TerminalRunWatcher(base_topic=BRING_TASKS_BASE_TOPIC)
        # self._task_watcher = PrintLineRunWatcher(base_topic=BRING_TASKS_BASE_TOPIC)

    @property
    def typistry(self):

        return self._tingistry_obj.typistry

    # @property
    # def tingistry(self):
    #     print("xx")
    #     import pp
    #     pp(self.__dict__)
    #     return self._tingistry

    @property
    def arg_hive(self) -> ArgHive:

        return self._tingistry_obj.arg_hive

    @property
    def dynamic_context_maker(self) -> TextFileTingMaker:

        if self._dynamic_context_maker is not None:
            return self._dynamic_context_maker

        self._dynamic_context_maker = self._tingistry_obj.create_ting(  # type: ignore
            "bring.types.config_file_context_maker", "bring.context_maker"
        )
        self._dynamic_context_maker.add_base_paths(  # type: ignore
            BRING_CONTEXTS_FOLDER
        )  # type: ignore
        return self._dynamic_context_maker  # type: ignore

    def _init_sync(self):
        if self._initialized:
            return

        wrap_async_task(self._init, _raise_exception=True)

    def provides(self) -> Mapping[str, str]:

        return {}

    def requires(self) -> Mapping[str, str]:

        return {}

    async def retrieve(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        return {}

    async def _init(self):

        with self._init_lock:
            if self._initialized:
                return

            self._transmogritory.plugin_manager

            await self.dynamic_context_maker.sync()

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
                ctx: BringStaticContextTing = self._tingistry_obj.create_ting(  # type: ignore
                    "bring.types.contexts.default_context",
                    f"bring.contexts.default.{context_name}",
                )
                ctx.input.set_values(ting_dict=json_content)
                self._default_contexts[context_name] = ctx

                await ctx.get_values("config")

            contexts: SubscripTings = self._tingistry_obj.get_ting(  # type: ignore
                "bring.contexts.dynamic"
            )
            dynamic: Dict[str, BringContextTing] = {  # type: ignore
                x.split(".")[-1]: ctx
                for x, ctx in contexts.childs.items()  # type: ignore
            }

            async with create_task_group() as tg:
                for file_name in os.listdir(BRING_DEFAULT_CONTEXTS_FOLDER):
                    if not file_name.endswith(".context"):
                        continue
                    await tg.spawn(add_default_context, file_name)

                for context in dynamic.values():
                    await tg.spawn(context.get_values, "config")

            self._initialized = True

    def add_context(self, context_name: str, context: BringContextTing):

        self._extra_contexts[context_name] = context

    @property
    def contexts(self) -> Mapping[str, BringContextTing]:

        self._init_sync()

        contexts: SubscripTings = self._tingistry_obj.get_ting(  # type: ignore
            "bring.contexts.dynamic"
        )
        result: Dict[str, BringContextTing] = {  # type: ignore
            x.split(".")[-1]: ctx for x, ctx in contexts.childs.items()  # type: ignore
        }

        result.update(self._extra_contexts)

        result.update(self._default_contexts)

        return result

    def get_context(self, context_name: str) -> BringContextTing:

        ctx = self.contexts.get(context_name, None)
        if ctx is None:
            raise FrklException(
                msg=f"Can't access bring context '{context_name}'.",
                reason=f"No context with that name.",
                solution=f"Create context, or choose one of the existing ones: {', '.join(self.contexts.keys())}",
            )

        return ctx

    async def update(self):

        await self._init()

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
